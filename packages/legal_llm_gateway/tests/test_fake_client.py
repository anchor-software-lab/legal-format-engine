"""Tests for the FakeLLMClient and the gateway contract types.

These tests pin the v0 contract that v1's LiteLLM-backed client will
also satisfy. If FakeLLMClient changes shape, the same change must
land in the real client.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from legal_llm_gateway import (
    CacheMode,
    FakeLLMClient,
    LLMClient,
    LLMError,
    LLMResult,
    Routing,
)


class NormalizedCite(BaseModel):
    canonical: str
    confidence: float


def test_fake_client_conforms_to_llmclient_protocol():
    assert isinstance(FakeLLMClient(), LLMClient)


def test_fake_client_returns_canned_response():
    canned = NormalizedCite(canonical="2010 WI 137", confidence=0.95)
    client = FakeLLMClient(responses={"bluebook.normalize_case@v1": canned})

    result: LLMResult[NormalizedCite] = asyncio.run(
        client.complete(
            prompt_id="bluebook.normalize_case@v1",
            variables={"raw": "Tews, 2010 WI 137"},
            output_schema=NormalizedCite,
            routing=Routing.AUTO,
            cache=CacheMode.PROMPT_PREFIX,
        )
    )

    assert result.output == canned
    assert result.provider == "fake"
    assert result.usage.input_tokens == 0
    assert len(client.calls) == 1
    assert client.calls[0][0] == "bluebook.normalize_case@v1"


def test_fake_client_falls_back_to_default():
    default = NormalizedCite(canonical="unknown", confidence=0.0)
    client = FakeLLMClient(default_output=default)

    result = asyncio.run(
        client.complete(
            prompt_id="some.unknown.prompt",
            variables={},
            output_schema=NormalizedCite,
        )
    )
    assert result.output == default


def test_fake_client_raises_when_no_response_configured():
    client = FakeLLMClient()
    with pytest.raises(LLMError) as exc_info:
        asyncio.run(
            client.complete(
                prompt_id="missing",
                variables={},
                output_schema=NormalizedCite,
            )
        )
    assert exc_info.value.prompt_id == "missing"
    assert "fake" in exc_info.value.providers_tried


def test_freeze_key_lets_test_distinguish_by_variables():
    cite_a = NormalizedCite(canonical="A", confidence=0.9)
    cite_b = NormalizedCite(canonical="B", confidence=0.9)
    client = FakeLLMClient(
        responses={"p:A": cite_a, "p:B": cite_b},
        freeze_key=lambda pid, vs: f"{pid}:{vs['raw']}",
    )

    result_a = asyncio.run(
        client.complete(
            prompt_id="p", variables={"raw": "A"}, output_schema=NormalizedCite
        )
    )
    result_b = asyncio.run(
        client.complete(
            prompt_id="p", variables={"raw": "B"}, output_schema=NormalizedCite
        )
    )

    assert result_a.output.canonical == "A"
    assert result_b.output.canonical == "B"


def test_prompt_spec_renders_variables():
    from legal_llm_gateway import PromptSpec

    spec = PromptSpec(
        id="test@v1",
        system_template="Be helpful.",
        user_template="Normalize: {raw}",
    )
    system, user = spec.render({"raw": "Tews, 2010 WI 137"})
    assert system == "Be helpful."
    assert user == "Normalize: Tews, 2010 WI 137"
