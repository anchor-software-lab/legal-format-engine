"""LLM-as-judge scorer.

Calls a stronger model (typically Anthropic Opus) with a calibrated
Bluebook rubric prompt to score `(candidate, gold)` pairs that the
programmatic and Bluebook-fuzzy scorers couldn't agree on.

Design discipline:
- The judge runs through our existing `LLMClient` Protocol; tests use
  `FakeLLMClient` so the suite stays offline.
- The judge prompt MUST score from a precise rubric, not vibes. The
  rubric is in `tools/eval/prompts/judge.bluebook_normalize.md`.
- The judge runs ONLY on cases where exact_match=0 AND
  bluebook_fuzzy=0. We don't pay to confirm what the cheap scorers
  already agreed on.
- Self-judging is a bias: if the candidate model is `claude-opus`, we
  should NOT use claude-opus as the judge. The runner enforces this
  by skipping LLMJudge for candidate.startswith(judge_model_family).

Bias check (run quarterly): hand-label 50 disagreement cases, compare
human gold vs judge gold; if they diverge >10%, recalibrate the rubric.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from legal_llm_gateway import CacheMode, LLMClient, LLMError, Routing
from tools.eval.scorers.base import ScoreResult


class JudgeOutput(BaseModel):
    """Schema the judge prompt produces."""

    equivalent: bool = Field(
        ..., description="True iff the two strings are the same Bluebook citation."
    )
    score: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., min_length=1)


JUDGE_PROMPT_ID = "judge.bluebook_normalize@v1"


@dataclass
class LLMJudge:
    """Score `(candidate, gold)` via a judge LLM call.

    The cost only kicks in when both deterministic scorers (exact_match
    + bluebook_fuzzy) returned 0; the runner gates this.
    """

    llm: LLMClient
    name: str = "judge"
    field_name: str = "canonical"
    prompt_id: str = JUDGE_PROMPT_ID
    routing: Routing = Routing.QUALITY_SENSITIVE  # use the best model
    cache: CacheMode = CacheMode.PROMPT_PREFIX

    async def score(
        self,
        *,
        candidate: dict[str, Any] | None,
        gold: dict[str, Any],
        case_input: dict[str, Any],
    ) -> ScoreResult:
        if candidate is None:
            return ScoreResult(self.name, 0.0, {"reason": "no candidate"})
        c = str(candidate.get(self.field_name, ""))
        g = str(gold.get(self.field_name, ""))
        try:
            result = await self.llm.complete(
                prompt_id=self.prompt_id,
                variables={
                    "candidate": c,
                    "gold": g,
                    "context": case_input.get("context", "") or "",
                },
                output_schema=JudgeOutput,
                routing=self.routing,
                cache=self.cache,
            )
        except LLMError as exc:
            return ScoreResult(
                self.name,
                0.0,
                {"error": str(exc), "providers_tried": exc.providers_tried},
            )
        out = result.output
        return ScoreResult(
            self.name,
            out.score if out.equivalent else min(out.score, 0.5),
            {
                "equivalent": out.equivalent,
                "rationale": out.rationale,
                "judge_provider": result.provider,
                "judge_model": result.model,
            },
        )
