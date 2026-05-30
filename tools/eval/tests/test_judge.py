"""Tests for the LLM-judge scorer via FakeLLMClient."""

from __future__ import annotations

import asyncio

from legal_llm_gateway import FakeLLMClient
from tools.eval.scorers import LLMJudge
from tools.eval.scorers.judge import JudgeOutput


def _input() -> dict:
    return {"raw": "x", "context": "the court reviewed"}


def test_judge_equivalent_returns_high_score():
    canned = JudgeOutput(
        equivalent=True,
        score=0.95,
        rationale="reporter alias only",
    )
    judge = LLMJudge(llm=FakeLLMClient(default_output=canned))
    result = asyncio.run(judge.score(
        candidate={"canonical": "x"},
        gold={"canonical": "y"},
        case_input=_input(),
    ))
    assert result.value == 0.95
    assert result.detail["equivalent"] is True


def test_judge_non_equivalent_clamps_at_half():
    canned = JudgeOutput(
        equivalent=False,
        score=0.9,
        rationale="different year",
    )
    judge = LLMJudge(llm=FakeLLMClient(default_output=canned))
    result = asyncio.run(judge.score(
        candidate={"canonical": "x"},
        gold={"canonical": "y"},
        case_input=_input(),
    ))
    # non-equivalent ⇒ score capped at 0.5 even when LLM said 0.9.
    assert result.value == 0.5


def test_judge_with_no_candidate_returns_zero():
    canned = JudgeOutput(equivalent=False, score=0.0, rationale="n/a")
    judge = LLMJudge(llm=FakeLLMClient(default_output=canned))
    result = asyncio.run(judge.score(
        candidate=None,
        gold={"canonical": "x"},
        case_input=_input(),
    ))
    assert result.value == 0.0
