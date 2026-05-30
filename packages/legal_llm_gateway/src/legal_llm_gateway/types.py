"""Public types for the LLM gateway.

These are stable contract types; the LiteLLM-backed client implementation
lands in v1. Checkers depend on the gateway through these types so tests
can substitute a fake gateway and stay offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class ModelClass(str, Enum):
    """Quality / cost tier requested by the caller.

    The gateway's Routing maps each class to an ordered provider list
    (e.g. CHEAP_FAST → ["gpt-4o-mini", "haiku", …]).
    """

    CHEAP_FAST = "cheap_fast"
    BALANCED = "balanced"
    TOP_QUALITY = "top_quality"
    LOCAL_ONLY = "local_only"


class Routing(str, Enum):
    AUTO = "auto"
    COST_SENSITIVE = "cost_sensitive"
    QUALITY_SENSITIVE = "quality_sensitive"
    PINNED = "pinned"  # use only the model named in the prompt frontmatter


class CacheMode(str, Enum):
    NONE = "none"
    PROMPT_PREFIX = "prompt_prefix"  # Anthropic prompt caching, OpenAI prefix


class LLMUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cost_usd_cents: int = 0  # integer cents to avoid float drift


T = TypeVar("T", bound=BaseModel)


class LLMResult(BaseModel, Generic[T]):
    """A successful LLM call, parsed into the requested output schema."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    prompt_id: str
    provider: str
    model: str
    output: T
    usage: LLMUsage = Field(default_factory=LLMUsage)
    latency_ms: int = 0
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class LLMError(Exception):
    """Raised when the gateway exhausts retries / fallbacks."""

    def __init__(
        self, prompt_id: str, providers_tried: list[str], reason: str
    ) -> None:
        super().__init__(
            f"LLM call for {prompt_id!r} failed across "
            f"{providers_tried}: {reason}"
        )
        self.prompt_id = prompt_id
        self.providers_tried = providers_tried
        self.reason = reason


class PromptSpec(BaseModel):
    """A loaded prompt template, including frontmatter routing hints."""

    id: str  # e.g. "bluebook.normalize_case@v3"
    template: str
    model_class: ModelClass = ModelClass.BALANCED
    temperature: float = 0.0
    max_tokens: int = 1024
    pinned_model: str | None = None
    cache_segments: list[str] = Field(default_factory=list)
    output_schema_ref: str | None = None  # path relative to schemas/json-schema/

    def render(self, variables: dict[str, Any]) -> str:
        """Render variables into the template using `{name}` substitution.

        Simple by design — the prompt files in `schemas/prompts/` are
        plain text with Python-style `{}` placeholders. No Jinja, no
        conditionals; complex prompts can be assembled in-code.
        """
        return self.template.format(**variables)
