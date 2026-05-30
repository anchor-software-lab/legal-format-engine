"""Runner tests: candidate generation + scoring + judge gating + caching."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel

from legal_llm_gateway import FakeLLMClient
from tools.eval.cache import NullCache, ResponseCache
from tools.eval.runner import RunConfig, run_eval
from tools.eval.scorers import BluebookFuzzy, ExactMatch, LLMJudge, SchemaValid
from tools.eval.scorers.judge import JudgeOutput
from tools.eval.types import EvalCase


class FakeOutput(BaseModel):
    canonical: str
    confidence: float = 0.9


def _cases() -> list[EvalCase]:
    return [
        EvalCase(
            id="c1",
            input={"raw": "x"},
            expected={"canonical": "Tews v. NHI, LLC, 2010 WI 137"},
        ),
        EvalCase(
            id="c2",
            input={"raw": "y"},
            expected={"canonical": "Brown v. Holiday, 2008 WI 49"},
        ),
    ]


def test_runs_each_case_per_model_and_scores():
    candidate = FakeOutput(canonical="Tews v. NHI, LLC, 2010 WI 137", confidence=0.9)
    client = FakeLLMClient(default_output=candidate)
    config = RunConfig(
        prompt_id="test@v1",
        output_schema=FakeOutput,
        models=["m1", "m2"],
        scorers=[SchemaValid(), ExactMatch(), BluebookFuzzy()],
    )
    report = asyncio.run(run_eval(_cases(), client=client, config=config))
    assert len(report.case_results) == 4  # 2 cases × 2 models
    # Schema valid on all.
    assert report.schema_valid_rate("m1") == 1.0
    assert report.schema_valid_rate("m2") == 1.0
    # Exact-match: only c1 matches the canned candidate.
    assert report.mean_score("m1", "exact_match") == 0.5
    assert report.mean_score("m1", "bluebook_fuzzy") == 0.5


def test_cache_short_circuits_second_run(tmp_path: Path):
    candidate = FakeOutput(canonical="Tews v. NHI, LLC, 2010 WI 137")
    client = FakeLLMClient(default_output=candidate)
    cache = ResponseCache(tmp_path)
    config = RunConfig(
        prompt_id="test@v1",
        output_schema=FakeOutput,
        models=["m1"],
        scorers=[SchemaValid(), ExactMatch()],
        cache=cache,
    )

    first = asyncio.run(run_eval(_cases(), client=client, config=config))
    # Each case caused one LLM call.
    assert len(client.calls) == 2
    assert all(not cr.cached for cr in first.case_results)

    second = asyncio.run(run_eval(_cases(), client=client, config=config))
    # No new LLM calls; runner served from cache.
    assert len(client.calls) == 2
    assert all(cr.cached for cr in second.case_results)


def test_judge_skipped_when_cheap_scorers_agree():
    candidate = FakeOutput(canonical="Tews v. NHI, LLC, 2010 WI 137", confidence=0.9)
    judge_client = FakeLLMClient(
        default_output=JudgeOutput(
            equivalent=False, score=0.1, rationale="bad",
        )
    )
    judge = LLMJudge(llm=judge_client)
    config = RunConfig(
        prompt_id="test@v1",
        output_schema=FakeOutput,
        models=["m1"],
        scorers=[SchemaValid(), ExactMatch(), BluebookFuzzy(), judge],
    )
    cases = [
        EvalCase(
            id="c1",
            input={"raw": "x"},
            expected={"canonical": "Tews v. NHI, LLC, 2010 WI 137"},  # match
        )
    ]
    client = FakeLLMClient(default_output=candidate)
    report = asyncio.run(run_eval(cases, client=client, config=config))
    # Judge wasn't called (cheap scorers passed).
    assert len(judge_client.calls) == 0
    # And the judge slot scored 1.0 (implied pass).
    assert report.case_results[0].scores["judge"] == 1.0


def test_judge_called_when_cheap_scorers_disagree():
    candidate = FakeOutput(canonical="Tews v NHI 2010 WI 137", confidence=0.7)  # bad surface
    judge_client = FakeLLMClient(
        default_output=JudgeOutput(
            equivalent=True, score=0.92, rationale="reporter alias only",
        )
    )
    judge = LLMJudge(llm=judge_client)
    config = RunConfig(
        prompt_id="test@v1",
        output_schema=FakeOutput,
        models=["m1"],
        scorers=[SchemaValid(), ExactMatch(), BluebookFuzzy(), judge],
    )
    cases = [
        EvalCase(
            id="c1",
            input={"raw": "x"},
            expected={"canonical": "Tews v. NHI, LLC, 2010 WI 137"},
        )
    ]
    client = FakeLLMClient(default_output=candidate)
    report = asyncio.run(run_eval(cases, client=client, config=config))
    # Cheap scorers disagreed → judge was called once.
    assert len(judge_client.calls) == 1
    assert report.case_results[0].scores["judge"] == 0.92


def test_judge_skipped_when_candidate_matches_judge_family():
    """Anti-self-judge: skip the judge when the candidate is from the
    judge's own model family."""
    candidate = FakeOutput(canonical="wrong", confidence=0.5)
    judge_client = FakeLLMClient(
        default_output=JudgeOutput(equivalent=True, score=0.9, rationale="ok"),
    )
    judge = LLMJudge(llm=judge_client)
    config = RunConfig(
        prompt_id="test@v1",
        output_schema=FakeOutput,
        models=["anthropic/claude-opus-4-7"],
        scorers=[SchemaValid(), ExactMatch(), BluebookFuzzy(), judge],
        judge_skip_when_candidate_starts_with=("anthropic/",),
    )
    cases = [
        EvalCase(id="c1", input={"raw": "x"}, expected={"canonical": "different"}),
    ]
    client = FakeLLMClient(default_output=candidate)
    asyncio.run(run_eval(cases, client=client, config=config))
    # Judge NOT called (anti-self-judge).
    assert len(judge_client.calls) == 0


def test_report_p95_latency():
    candidate = FakeOutput(canonical="x")
    client = FakeLLMClient(default_output=candidate)
    config = RunConfig(
        prompt_id="test@v1",
        output_schema=FakeOutput,
        models=["m1"],
        scorers=[SchemaValid()],
    )
    report = asyncio.run(run_eval(_cases(), client=client, config=config))
    # p95 latency is a non-negative integer.
    assert report.p95_latency_ms("m1") >= 0
