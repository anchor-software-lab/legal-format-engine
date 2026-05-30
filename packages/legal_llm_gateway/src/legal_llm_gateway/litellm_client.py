"""LiteLLM-backed `LLMClient`.

Walks the Router's model list, calls each via `litellm.acompletion`,
validates the response against the caller's Pydantic `output_schema`,
and records cost via `CostRecorder`. On failure (rate limit, 5xx,
schema validation), falls through to the next model in the list. If
every model fails, raises `LLMError` with the list of providers tried.

Prompt caching: when `cache=CacheMode.PROMPT_PREFIX` and the prompt's
`cache_segments` list mentions "SYSTEM", the system message is wrapped
in Anthropic-style `cache_control: {type: "ephemeral"}`. LiteLLM
relays this to providers that support it; others ignore it silently.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Type, TypeVar

import litellm
from pydantic import BaseModel, ValidationError

from legal_llm_gateway.cost import CostRecorder, InMemoryCostRecorder
from legal_llm_gateway.prompts import load_prompt
from legal_llm_gateway.routing import Router
from legal_llm_gateway.types import (
    CacheMode,
    LLMError,
    LLMResult,
    LLMUsage,
    PromptSpec,
    Routing,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class LiteLLMClient:
    """Production `LLMClient` implementation.

    Construct with:

        client = LiteLLMClient(
            router=Router.from_yaml("infra/routing.yaml"),
            cost_recorder=InMemoryCostRecorder(),  # or a DB-backed impl
        )

    Then in a checker:

        result = await client.complete(
            prompt_id="bluebook.normalize_case@v1",
            variables={"raw": "...", "context": "...", "jurisdiction": "WI"},
            output_schema=NormalizeCaseOutput,
        )
    """

    router: Router = None  # type: ignore[assignment]  # set in __post_init__
    cost_recorder: CostRecorder = None  # type: ignore[assignment]
    prompt_loader = staticmethod(load_prompt)
    max_attempts_per_model: int = 2

    def __post_init__(self) -> None:
        if self.router is None:
            self.router = Router()
        if self.cost_recorder is None:
            self.cost_recorder = InMemoryCostRecorder()

    async def complete(
        self,
        *,
        prompt_id: str,
        variables: dict[str, Any],
        output_schema: Type[T],
        routing: Routing = Routing.AUTO,
        cache: CacheMode = CacheMode.PROMPT_PREFIX,
    ) -> LLMResult[T]:
        spec = self.prompt_loader(prompt_id)
        models = self.router.resolve(spec, routing)
        if not models:
            raise LLMError(
                prompt_id, [], f"no models configured for {spec.model_class.value}"
            )

        system, user = spec.render(variables)
        messages = _build_messages(system, user, spec, cache)

        tried: list[str] = []
        last_reason: str = "no attempts made"
        for model in models:
            tried.append(model)
            try:
                raw, usage_dict, latency_ms = await self._call_with_retries(
                    model=model,
                    messages=messages,
                    spec=spec,
                )
            except Exception as exc:  # noqa: BLE001 - we want to fall through
                last_reason = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "litellm call to %s failed for %s: %s",
                    model, prompt_id, last_reason,
                )
                continue

            try:
                output = _parse_output(raw, output_schema)
            except ValidationError as exc:
                last_reason = f"schema validation: {exc}"
                logger.warning(
                    "schema validation failed on %s for %s; trying next model",
                    model, prompt_id,
                )
                continue

            usage = _usage_from_dict(usage_dict)
            self.cost_recorder.record(
                prompt_id=prompt_id,
                provider=_provider_of(model),
                model=model,
                usage=usage,
            )
            return LLMResult[T](
                prompt_id=prompt_id,
                provider=_provider_of(model),
                model=model,
                output=output,
                usage=usage,
                latency_ms=latency_ms,
            )

        raise LLMError(prompt_id, tried, last_reason)

    async def _call_with_retries(
        self, *, model: str, messages: list[dict], spec: PromptSpec
    ) -> tuple[str, dict, int]:
        attempt = 0
        last_exc: Exception | None = None
        while attempt < self.max_attempts_per_model:
            attempt += 1
            t0 = time.monotonic()
            try:
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    temperature=spec.temperature,
                    max_tokens=spec.max_tokens,
                    response_format={"type": "json_object"}
                    if spec.output_schema_ref
                    else None,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if not _is_retryable(exc):
                    raise
                continue
            latency_ms = int((time.monotonic() - t0) * 1000)
            content = response.choices[0].message.content or ""
            usage = (response.usage or {}).model_dump() if hasattr(
                response.usage, "model_dump"
            ) else dict(response.usage or {})
            return content, usage, latency_ms
        # Exhausted retries.
        assert last_exc is not None
        raise last_exc


def _build_messages(
    system: str, user: str, spec: PromptSpec, cache: CacheMode
) -> list[dict]:
    messages: list[dict] = []
    if system:
        if cache is CacheMode.PROMPT_PREFIX and "SYSTEM" in spec.cache_segments:
            # Anthropic-flavored cache_control. LiteLLM relays this to
            # providers that support it; others ignore the field.
            messages.append(
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            )
        else:
            messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    return messages


def _parse_output(raw: str, schema: Type[T]) -> T:
    # Some providers wrap JSON in markdown fences. Strip them.
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    payload = json.loads(text)
    return schema.model_validate(payload)


def _usage_from_dict(usage: dict) -> LLMUsage:
    return LLMUsage(
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        cached_input_tokens=int(
            usage.get("cache_read_input_tokens")
            or usage.get("prompt_tokens_details", {}).get("cached_tokens")
            or 0
        ),
        cost_usd_cents=0,  # filled by CostRecorder
    )


def _provider_of(model: str) -> str:
    """`openai/gpt-4o` → `openai`. Models without a slash are treated
    as bare model names; LiteLLM resolves them via env vars."""
    return model.split("/", 1)[0] if "/" in model else "unknown"


# Errors worth retrying once before falling through to the next model.
# We're deliberately conservative — schema validation failures and
# auth errors are NOT retried.
_RETRYABLE_NAMES = {
    "Timeout",
    "APIConnectionError",
    "RateLimitError",
    "ServiceUnavailableError",
    "InternalServerError",
}


def _is_retryable(exc: Exception) -> bool:
    return type(exc).__name__ in _RETRYABLE_NAMES
