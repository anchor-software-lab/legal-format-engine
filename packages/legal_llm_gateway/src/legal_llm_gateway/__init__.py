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
from legal_llm_gateway.cost import CostRecord, CostRecorder, InMemoryCostRecorder
from legal_llm_gateway.prompts import PromptNotFound, PromptParseError, load_prompt
from legal_llm_gateway.routing import DEFAULT_ROUTING, Router
from legal_llm_gateway.types import (
    CacheMode,
    LLMError,
    LLMResult,
    LLMUsage,
    ModelClass,
    PromptSpec,
    Routing,
)

# LiteLLMClient is imported lazily so that importing this package
# doesn't drag in litellm (which has a heavy dep tree) unless the
# real client is actually used. Tests and the FakeLLMClient path never
# need it.
def __getattr__(name: str):
    if name == "LiteLLMClient":
        from legal_llm_gateway.litellm_client import LiteLLMClient as _C
        return _C
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CacheMode",
    "CostRecord",
    "CostRecorder",
    "DEFAULT_ROUTING",
    "FakeLLMClient",
    "InMemoryCostRecorder",
    "LLMClient",
    "LLMError",
    "LLMResult",
    "LLMUsage",
    "LiteLLMClient",
    "ModelClass",
    "PromptNotFound",
    "PromptParseError",
    "PromptSpec",
    "Router",
    "Routing",
    "load_prompt",
]
