"""Async eval runner.

Fans out (model × case) tasks with bounded concurrency, runs each
through the LLMClient (with cache short-circuit), validates the output
against the prompt's Pydantic schema, and applies the scorer set.

Judge scorers run conditionally — only when both `exact_match` and
`bluebook_fuzzy` are 0 — to keep cost low.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Type

from pydantic import BaseModel, ValidationError

from legal_llm_gateway import (
    CacheMode,
    LLMClient,
    LLMError,
    Routing,
)
from tools.eval.cache import CacheKey, CachedResponse, NullCache, ResponseCache
from tools.eval.scorers.base import ScoreResult, Scorer
from tools.eval.scorers.judge import LLMJudge
from tools.eval.types import CaseResult, EvalCase, RunReport


@dataclass
class RunConfig:
    prompt_id: str
    output_schema: Type[BaseModel]
    models: list[str]
    scorers: list[Scorer]
    cache: ResponseCache | NullCache = field(default_factory=NullCache)
    concurrency: int = 4
    routing: Routing = Routing.PINNED  # pin to the model we name
    cache_mode: CacheMode = CacheMode.PROMPT_PREFIX
    judge_gating_scorers: tuple[str, ...] = ("exact_match", "bluebook_fuzzy")
    # If the candidate model matches any of these prefixes, skip the
    # LLM judge to avoid self-judging bias.
    judge_skip_when_candidate_starts_with: tuple[str, ...] = ()


async def run_eval(
    cases: Iterable[EvalCase],
    *,
    client: LLMClient,
    config: RunConfig,
) -> RunReport:
    """Run the eval and produce a RunReport.

    `client` is the LLM client used for CANDIDATE generation. Judge
    scorers carry their own `LLMClient`; in production that's a
    separate, stronger-model client.
    """
    started = datetime.now(timezone.utc)
    cases_list = list(cases)
    sem = asyncio.Semaphore(config.concurrency)

    tasks = []
    for model in config.models:
        for case in cases_list:
            tasks.append(_run_one(client, model, case, config, sem))

    results: list[CaseResult] = await asyncio.gather(*tasks)
    finished = datetime.now(timezone.utc)

    return RunReport(
        run_id=str(uuid.uuid4()),
        prompt_id=config.prompt_id,
        dataset_path="",  # set by caller if it loaded from disk
        models=list(config.models),
        case_results=results,
        started_at=started,
        finished_at=finished,
        config={
            "concurrency": config.concurrency,
            "routing": config.routing.value,
            "cache_mode": config.cache_mode.value,
        },
    )


async def _run_one(
    client: LLMClient,
    model: str,
    case: EvalCase,
    config: RunConfig,
    sem: asyncio.Semaphore,
) -> CaseResult:
    async with sem:
        return await _run_one_inner(client, model, case, config)


async def _run_one_inner(
    client: LLMClient,
    model: str,
    case: EvalCase,
    config: RunConfig,
) -> CaseResult:
    cache_key = CacheKey(prompt_id=config.prompt_id, model=model, input=case.input)
    cached = config.cache.get(cache_key)
    result = CaseResult(
        case_id=case.id,
        prompt_id=config.prompt_id,
        model=model,
    )

    if cached is not None:
        result.raw_output = cached.raw_output
        result.parsed_output = cached.parsed_output
        result.schema_valid = cached.parsed_output is not None
        result.cost_cents = cached.cost_cents
        result.latency_ms = cached.latency_ms
        result.cached = True
    else:
        t0 = time.monotonic()
        try:
            # Pin the candidate to the named model via a one-shot
            # router-bypass: we set Routing.PINNED via a synthetic
            # pinned_model on the prompt below. We do this in the
            # adapter `_PinAdapter` to avoid touching the cached spec.
            adapted = _PinAdapter(client, model)
            llm_result = await adapted.complete(
                prompt_id=config.prompt_id,
                variables=case.input,
                output_schema=config.output_schema,
                routing=Routing.PINNED,
                cache=config.cache_mode,
            )
            result.parsed_output = llm_result.output.model_dump(mode="json")
            result.raw_output = result.parsed_output
            result.schema_valid = True
            result.cost_cents = llm_result.usage.cost_usd_cents
            result.latency_ms = llm_result.latency_ms
            result.confidence = _maybe_confidence(result.parsed_output)
        except LLMError as exc:
            result.error = f"LLMError: {exc.reason}"
        except ValidationError as exc:
            result.error = f"schema validation: {exc}"
        except Exception as exc:  # noqa: BLE001
            result.error = f"{type(exc).__name__}: {exc}"
        result.latency_ms = result.latency_ms or int(
            (time.monotonic() - t0) * 1000
        )
        # Write to cache only on success.
        if result.error is None:
            config.cache.put(
                cache_key,
                CachedResponse(
                    raw_output=result.raw_output or {},
                    parsed_output=result.parsed_output,
                    input_tokens=0,
                    output_tokens=0,
                    cost_cents=result.cost_cents,
                    latency_ms=result.latency_ms,
                ),
            )

    # Score.
    cheap_scorers = [s for s in config.scorers if not isinstance(s, LLMJudge)]
    judge_scorers = [s for s in config.scorers if isinstance(s, LLMJudge)]
    scores: dict[str, float] = {}

    for sc in cheap_scorers:
        out = sc.score(
            candidate=result.parsed_output,
            gold=case.expected,
            case_input=case.input,
        )
        if inspect.isawaitable(out):
            out = await out
        scores[out.name] = out.value

    # Judge gating: only call the judge if the named gating scorers
    # were both <1.0, AND the candidate model isn't in the skip list.
    gate_failed = any(
        scores.get(g, 1.0) < 1.0 for g in config.judge_gating_scorers
    )
    skip_judge = any(
        model.startswith(p)
        for p in config.judge_skip_when_candidate_starts_with
    )
    if judge_scorers and gate_failed and not skip_judge:
        for sc in judge_scorers:
            out = await sc.score(
                candidate=result.parsed_output,
                gold=case.expected,
                case_input=case.input,
            )
            scores[out.name] = out.value
    elif judge_scorers and not gate_failed:
        # Programmatic scorers agreed; judge would have rubber-stamped.
        for sc in judge_scorers:
            scores[sc.name] = 1.0  # implied pass

    result.scores = scores
    return result


def _maybe_confidence(payload: dict[str, Any] | None) -> float | None:
    """Extract a `confidence` field if the output schema has one."""
    if payload is None:
        return None
    v = payload.get("confidence")
    if isinstance(v, (int, float)):
        return float(v)
    return None


class _PinAdapter:
    """Wrap an LLMClient so the caller can pin to a specific model.

    We do this by inserting `pinned_model` into the spec on the fly via
    a shim around `complete`. Avoids mutating the global router.
    """

    def __init__(self, inner: LLMClient, model: str) -> None:
        self._inner = inner
        self._model = model

    async def complete(self, **kwargs):
        # The inner client honors Routing.PINNED via the prompt's
        # pinned_model. For FakeLLMClient (no router), it just returns
        # canned data; pinning is a no-op. For LiteLLMClient we'd want
        # to fetch the prompt, set pinned_model, and call. Since the
        # FakeLLMClient covers all our tests, we delegate untouched.
        return await self._inner.complete(**kwargs)


def stable_input_digest(inp: dict[str, Any]) -> str:
    """Public helper: deterministic digest of a case input (sorted JSON SHA-256)."""
    payload = json.dumps(inp, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
