"""Provider-agnostic LLM gateway built on LiteLLM.

v0 ships the contract types and a FakeLLMClient. The LiteLLM-backed
real client lands in v1.

Stable surface:
- `LLMClient` Protocol — `await client.complete(prompt_id, variables,
  output_schema, routing, cache)` returning `LLMResult[T]`.
- `FakeLLMClient` — deterministic stub for tests.
- `ModelClass`, `Routing`, `CacheMode`, `LLMResult`, `LLMUsage`,
  `LLMError`, `PromptSpec` — wire types.

v1 will add:
- `LiteLLMClient` — real implementation with provider fallback, prompt
  caching, cost recording.
- `prompts.load_prompt(prompt_id)` — load + parse a versioned prompt
  template from `schemas/prompts/<id>.md` with YAML frontmatter.
- `routing.Router` — maps `model_class` to provider preference order.
- `cost.CostRecorder` — persists `llm_calls` records for billing.
"""

from legal_llm_gateway.client import FakeLLMClient, LLMClient
from legal_llm_gateway.types import (
    CacheMode,
    LLMError,
    LLMResult,
    LLMUsage,
    ModelClass,
    PromptSpec,
    Routing,
)

__all__ = [
    "CacheMode",
    "FakeLLMClient",
    "LLMClient",
    "LLMError",
    "LLMResult",
    "LLMUsage",
    "ModelClass",
    "PromptSpec",
    "Routing",
]
