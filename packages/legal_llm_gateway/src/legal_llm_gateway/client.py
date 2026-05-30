"""The LLMClient Protocol — the surface every checker depends on.

Two concrete implementations are planned:

- `LiteLLMClient` (v1): real implementation backed by LiteLLM, with
  provider routing, prompt caching, retry/fallback, and cost recording.
- `FakeLLMClient` (already here): a deterministic stub for tests.
  Maps `prompt_id` → canned `output` so checkers can be exercised
  without network or model dependencies.
"""

from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable, Protocol, Type, TypeVar, runtime_checkable

from pydantic import BaseModel

from legal_llm_gateway.types import (
    CacheMode,
    LLMError,
    LLMResult,
    LLMUsage,
    Routing,
)

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMClient(Protocol):
    """Unified interface for LLM access.

    `complete` is the single entry point. Callers pass:
      - `prompt_id`: versioned prompt identifier loaded from
        `schemas/prompts/<id>.md` (with YAML frontmatter routing hints).
      - `variables`: dict substituted into the prompt template.
      - `output_schema`: Pydantic model the LLM output is validated
        against. Schema failures get one retry, then raise `LLMError`.
      - `routing`: routing strategy. AUTO follows the prompt's
        frontmatter; COST_SENSITIVE / QUALITY_SENSITIVE override it.
      - `cache`: prompt caching mode. PROMPT_PREFIX uses the provider's
        prefix-caching feature for the long system prompt segments
        declared in the frontmatter.
    """

    async def complete(
        self,
        *,
        prompt_id: str,
        variables: dict[str, Any],
        output_schema: Type[T],
        routing: Routing = Routing.AUTO,
        cache: CacheMode = CacheMode.PROMPT_PREFIX,
    ) -> LLMResult[T]: ...


class FakeLLMClient:
    """Deterministic stub: maps `(prompt_id, freeze_key)` → canned output.

    Used by tests to drive LLM-bound checkers without standing up a real
    provider. Falls back to a `default_output` (if provided) when no
    canned response matches.
    """

    def __init__(
        self,
        *,
        responses: dict[str, BaseModel] | None = None,
        default_output: BaseModel | None = None,
        freeze_key: Callable[[str, dict[str, Any]], str] | None = None,
    ) -> None:
        self._responses = responses or {}
        self._default = default_output
        self._freeze_key = freeze_key or (lambda pid, vs: pid)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def complete(
        self,
        *,
        prompt_id: str,
        variables: dict[str, Any],
        output_schema: Type[T],
        routing: Routing = Routing.AUTO,
        cache: CacheMode = CacheMode.PROMPT_PREFIX,
    ) -> LLMResult[T]:
        self.calls.append((prompt_id, dict(variables)))
        key = self._freeze_key(prompt_id, variables)
        canned = self._responses.get(key) or self._default
        if canned is None:
            raise LLMError(prompt_id, ["fake"], f"no canned response for key {key!r}")
        if not isinstance(canned, output_schema):
            # Allow callers to pass a dict-shaped canned response.
            try:
                canned = output_schema.model_validate(
                    canned.model_dump() if isinstance(canned, BaseModel) else canned
                )
            except Exception as exc:
                raise LLMError(prompt_id, ["fake"], f"schema mismatch: {exc}") from exc
        return LLMResult[T](
            prompt_id=prompt_id,
            provider="fake",
            model="fake-1",
            output=canned,
            usage=LLMUsage(input_tokens=0, output_tokens=0, cost_usd_cents=0),
            latency_ms=0,
        )
