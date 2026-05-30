"""Tests for LiteLLMClient with litellm.acompletion fully mocked.

These tests pin the LiteLLMClient behavior — provider fallback, cost
recording, prompt caching headers, retry classification, JSON parsing
— without making network calls. Real-network smoke tests live in a
separate `test_litellm_client_live.py` (skipped unless ANCHOR_LLM_LIVE
is set), which we'll add when v1 needs a green-build signal against
real providers.
"""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from legal_llm_gateway import (
    CacheMode,
    InMemoryCostRecorder,
    LLMError,
    PromptSpec,
    Router,
    Routing,
    load_prompt,
)
from legal_llm_gateway.litellm_client import LiteLLMClient


class NormalizeOut(BaseModel):
    canonical: str
    confidence: float


def _make_response(content: str, *, prompt_tokens: int = 10, completion_tokens: int = 5):
    """Build the minimal duck-typed object LiteLLMClient pulls fields off of."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=content))
        ],
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    )


@pytest.fixture
def prompt_dir(tmp_path: Path) -> Path:
    """A throwaway prompts dir with a single, well-formed prompt."""
    (tmp_path / "test.norm.md").write_text(
        textwrap.dedent(
            """
            ---
            id: test.norm@v1
            model_class: balanced
            cache_segments: [SYSTEM]
            ---

            SYSTEM:

            Normalize Bluebook case cites.

            USER:

            Cite: {raw}
            """
        ).lstrip()
    )
    return tmp_path


@pytest.fixture
def client_with_prompt_dir(prompt_dir):
    client = LiteLLMClient(cost_recorder=InMemoryCostRecorder())
    client.prompt_loader = lambda pid: load_prompt(pid, search_dirs=[prompt_dir])
    return client


def test_successful_call_returns_parsed_output(client_with_prompt_dir):
    response = _make_response('{"canonical": "2010 WI 137", "confidence": 0.95}')

    async def fake_acompletion(**kwargs):
        return response

    with patch("legal_llm_gateway.litellm_client.litellm.acompletion", side_effect=fake_acompletion):
        result = asyncio.run(
            client_with_prompt_dir.complete(
                prompt_id="test.norm@v1",
                variables={"raw": "Tews, 2010 WI 137"},
                output_schema=NormalizeOut,
            )
        )
    assert result.output.canonical == "2010 WI 137"
    assert result.output.confidence == 0.95
    assert result.provider in {"anthropic", "openai"}
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 5


def test_falls_through_to_next_model_on_failure(client_with_prompt_dir):
    calls: list[str] = []

    async def fake_acompletion(*, model, **kwargs):
        calls.append(model)
        if model == client_with_prompt_dir.router.resolve(
            PromptSpec(id="test.norm@v1", user_template="x")
        )[0]:
            raise RuntimeError("first model down")
        return _make_response('{"canonical": "ok", "confidence": 0.8}')

    # The default router returns multiple models; the second one should succeed.
    with patch("legal_llm_gateway.litellm_client.litellm.acompletion", side_effect=fake_acompletion):
        result = asyncio.run(
            client_with_prompt_dir.complete(
                prompt_id="test.norm@v1",
                variables={"raw": "x"},
                output_schema=NormalizeOut,
            )
        )
    assert len(calls) >= 2  # tried first, then fell through
    assert result.output.canonical == "ok"


def test_raises_llmerror_when_all_models_fail(client_with_prompt_dir):
    async def fake_acompletion(**kwargs):
        raise RuntimeError("nope")

    with patch("legal_llm_gateway.litellm_client.litellm.acompletion", side_effect=fake_acompletion):
        with pytest.raises(LLMError) as exc_info:
            asyncio.run(
                client_with_prompt_dir.complete(
                    prompt_id="test.norm@v1",
                    variables={"raw": "x"},
                    output_schema=NormalizeOut,
                )
            )
    assert exc_info.value.prompt_id == "test.norm@v1"
    assert len(exc_info.value.providers_tried) >= 1
    assert "nope" in exc_info.value.reason


def test_schema_validation_failure_falls_through(client_with_prompt_dir):
    """Bad JSON shape from one provider → try the next."""
    responses = iter(
        [
            _make_response('{"wrong_field": "no canonical"}'),
            _make_response('{"canonical": "fixed", "confidence": 0.9}'),
        ]
    )

    async def fake_acompletion(**kwargs):
        return next(responses)

    with patch("legal_llm_gateway.litellm_client.litellm.acompletion", side_effect=fake_acompletion):
        result = asyncio.run(
            client_with_prompt_dir.complete(
                prompt_id="test.norm@v1",
                variables={"raw": "x"},
                output_schema=NormalizeOut,
            )
        )
    assert result.output.canonical == "fixed"


def test_json_fenced_in_markdown_is_unwrapped(client_with_prompt_dir):
    """Some models wrap JSON in ```json ... ``` fences."""
    response = _make_response(
        '```json\n{"canonical": "fenced", "confidence": 0.8}\n```'
    )

    async def fake_acompletion(**kwargs):
        return response

    with patch("legal_llm_gateway.litellm_client.litellm.acompletion", side_effect=fake_acompletion):
        result = asyncio.run(
            client_with_prompt_dir.complete(
                prompt_id="test.norm@v1",
                variables={"raw": "x"},
                output_schema=NormalizeOut,
            )
        )
    assert result.output.canonical == "fenced"


def test_cost_recorder_captures_calls(client_with_prompt_dir):
    response = _make_response(
        '{"canonical": "x", "confidence": 0.9}',
        prompt_tokens=42, completion_tokens=7,
    )

    async def fake_acompletion(**kwargs):
        return response

    recorder: InMemoryCostRecorder = client_with_prompt_dir.cost_recorder
    with patch("legal_llm_gateway.litellm_client.litellm.acompletion", side_effect=fake_acompletion):
        asyncio.run(
            client_with_prompt_dir.complete(
                prompt_id="test.norm@v1",
                variables={"raw": "x"},
                output_schema=NormalizeOut,
            )
        )
    assert len(recorder.records) == 1
    assert recorder.records[0].usage.input_tokens == 42
    assert recorder.records[0].usage.output_tokens == 7
    assert recorder.records[0].prompt_id == "test.norm@v1"


def test_prompt_prefix_cache_wraps_system_message(client_with_prompt_dir):
    captured: dict[str, Any] = {}

    async def fake_acompletion(*, messages, **kwargs):
        captured["messages"] = messages
        return _make_response('{"canonical": "x", "confidence": 0.9}')

    with patch("legal_llm_gateway.litellm_client.litellm.acompletion", side_effect=fake_acompletion):
        asyncio.run(
            client_with_prompt_dir.complete(
                prompt_id="test.norm@v1",
                variables={"raw": "x"},
                output_schema=NormalizeOut,
                cache=CacheMode.PROMPT_PREFIX,
            )
        )
    system_msg = captured["messages"][0]
    assert system_msg["role"] == "system"
    # The content is the structured list form with cache_control.
    assert isinstance(system_msg["content"], list)
    assert system_msg["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_prompt_no_cache_uses_plain_string_system(client_with_prompt_dir):
    captured: dict[str, Any] = {}

    async def fake_acompletion(*, messages, **kwargs):
        captured["messages"] = messages
        return _make_response('{"canonical": "x", "confidence": 0.9}')

    with patch("legal_llm_gateway.litellm_client.litellm.acompletion", side_effect=fake_acompletion):
        asyncio.run(
            client_with_prompt_dir.complete(
                prompt_id="test.norm@v1",
                variables={"raw": "x"},
                output_schema=NormalizeOut,
                cache=CacheMode.NONE,
            )
        )
    system_msg = captured["messages"][0]
    assert isinstance(system_msg["content"], str)


def test_empty_model_list_raises_immediately(prompt_dir):
    # Build a Router whose balanced class is empty.
    router = Router(table={})
    client = LiteLLMClient(router=router, cost_recorder=InMemoryCostRecorder())
    client.prompt_loader = lambda pid: load_prompt(pid, search_dirs=[prompt_dir])

    with pytest.raises(LLMError, match="no models configured"):
        asyncio.run(
            client.complete(
                prompt_id="test.norm@v1",
                variables={"raw": "x"},
                output_schema=NormalizeOut,
            )
        )
