"""Map `ModelClass` to an ordered list of LiteLLM model identifiers.

Configurable via `routing.yaml` (per-org / per-env) or the in-code
defaults. The `LiteLLMClient` walks the list left-to-right: if the
first provider fails (rate limit, 5xx, schema validation), it tries
the next. The right-most provider should be a local fallback when
possible so the system degrades gracefully under outage.

Example routing.yaml:

    cheap_fast:
      - openai/gpt-4o-mini
      - anthropic/claude-haiku-4-5
    balanced:
      - anthropic/claude-sonnet-4-6
      - openai/gpt-4o
    top_quality:
      - anthropic/claude-opus-4-7
    local_only:
      - ollama/llama-3.1-70b
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from legal_llm_gateway.types import ModelClass, PromptSpec, Routing


# Default routing table used when no `routing.yaml` is supplied.
# Conservative model choices — callers can override per deployment.
DEFAULT_ROUTING: dict[ModelClass, list[str]] = {
    ModelClass.CHEAP_FAST: [
        "anthropic/claude-haiku-4-5",
        "openai/gpt-4o-mini",
    ],
    ModelClass.BALANCED: [
        "anthropic/claude-sonnet-4-6",
        "openai/gpt-4o",
    ],
    ModelClass.TOP_QUALITY: [
        "anthropic/claude-opus-4-7",
    ],
    ModelClass.LOCAL_ONLY: [
        "ollama/llama3.1:70b",
    ],
}


@dataclass
class Router:
    """Resolves a PromptSpec + Routing into an ordered model list.

    The first model in the returned list is tried first; on failure the
    client falls through to the next. The list is non-empty when the
    routing config has at least one entry for the prompt's
    `model_class`; an empty list is a configuration error.
    """

    table: dict[ModelClass, list[str]] = field(
        default_factory=lambda: dict(DEFAULT_ROUTING)
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Router":
        data = yaml.safe_load(Path(path).read_text()) or {}
        table: dict[ModelClass, list[str]] = {}
        for key, models in data.items():
            try:
                cls_key = ModelClass(key)
            except ValueError:
                continue
            table[cls_key] = list(models or [])
        # Backfill missing classes from defaults so partial configs
        # still work end-to-end.
        merged = dict(DEFAULT_ROUTING)
        merged.update(table)
        return cls(table=merged)

    def resolve(self, spec: PromptSpec, routing: Routing = Routing.AUTO) -> list[str]:
        """Return the ordered model identifiers to try for this prompt."""
        if routing is Routing.PINNED and spec.pinned_model:
            return [spec.pinned_model]

        if routing is Routing.COST_SENSITIVE:
            cls = ModelClass.CHEAP_FAST
        elif routing is Routing.QUALITY_SENSITIVE:
            cls = ModelClass.TOP_QUALITY
        else:
            cls = spec.model_class

        models = list(self.table.get(cls, []))
        # If pinned_model is set, try it first under AUTO too — the
        # prompt author's preference wins over the class default.
        if (
            routing is Routing.AUTO
            and spec.pinned_model
            and spec.pinned_model not in models
        ):
            models.insert(0, spec.pinned_model)
        return models
