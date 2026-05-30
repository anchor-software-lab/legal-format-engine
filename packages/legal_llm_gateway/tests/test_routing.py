"""Tests for the Router."""

from __future__ import annotations

import textwrap

from legal_llm_gateway import (
    DEFAULT_ROUTING,
    ModelClass,
    PromptSpec,
    Router,
    Routing,
)


def _spec(model_class: ModelClass = ModelClass.BALANCED, pinned: str | None = None) -> PromptSpec:
    return PromptSpec(
        id="test@v1",
        user_template="...",
        model_class=model_class,
        pinned_model=pinned,
    )


def test_resolve_uses_prompt_model_class_under_auto():
    router = Router()
    models = router.resolve(_spec(ModelClass.CHEAP_FAST), Routing.AUTO)
    assert models == DEFAULT_ROUTING[ModelClass.CHEAP_FAST]


def test_resolve_cost_sensitive_overrides_class():
    router = Router()
    models = router.resolve(_spec(ModelClass.TOP_QUALITY), Routing.COST_SENSITIVE)
    assert models == DEFAULT_ROUTING[ModelClass.CHEAP_FAST]


def test_resolve_quality_sensitive_overrides_class():
    router = Router()
    models = router.resolve(_spec(ModelClass.CHEAP_FAST), Routing.QUALITY_SENSITIVE)
    assert models == DEFAULT_ROUTING[ModelClass.TOP_QUALITY]


def test_pinned_model_wins_under_pinned_routing():
    router = Router()
    spec = _spec(pinned="anthropic/claude-opus-4-7")
    models = router.resolve(spec, Routing.PINNED)
    assert models == ["anthropic/claude-opus-4-7"]


def test_pinned_model_floats_to_front_under_auto():
    router = Router()
    spec = _spec(ModelClass.BALANCED, pinned="anthropic/claude-opus-4-7")
    models = router.resolve(spec, Routing.AUTO)
    assert models[0] == "anthropic/claude-opus-4-7"
    assert len(models) > 1  # rest still tried as fallbacks


def test_from_yaml_merges_with_defaults(tmp_path):
    path = tmp_path / "routing.yaml"
    path.write_text(
        textwrap.dedent(
            """
            cheap_fast:
              - openai/gpt-4o-mini
            """
        )
    )
    router = Router.from_yaml(path)
    # Override applied to cheap_fast …
    assert router.resolve(_spec(ModelClass.CHEAP_FAST)) == ["openai/gpt-4o-mini"]
    # … but other classes inherit defaults.
    assert router.resolve(_spec(ModelClass.TOP_QUALITY)) == DEFAULT_ROUTING[
        ModelClass.TOP_QUALITY
    ]


def test_from_yaml_ignores_unknown_classes(tmp_path):
    path = tmp_path / "routing.yaml"
    path.write_text("not_a_class:\n  - foo\n")
    router = Router.from_yaml(path)
    # Defaults intact.
    assert router.resolve(_spec(ModelClass.BALANCED)) == DEFAULT_ROUTING[
        ModelClass.BALANCED
    ]
