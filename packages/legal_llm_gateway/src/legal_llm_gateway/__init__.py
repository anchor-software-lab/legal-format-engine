"""Provider-agnostic LLM gateway built on LiteLLM.

v1 surface (planned):
- `client.LLMClient.complete(prompt_id, vars, output_schema, ...)` —
  versioned prompts, Pydantic schema validation, prompt caching, cost
  tracking, per-class provider routing.
- `prompts.load_prompt(prompt_id)` — load + parse a versioned prompt
  template from `schemas/prompts/<id>.md` with YAML frontmatter.
- `routing.Router` — maps `model_class` to provider preference order.
- `cost.CostRecorder` — persists `llm_calls` records for billing.
"""
