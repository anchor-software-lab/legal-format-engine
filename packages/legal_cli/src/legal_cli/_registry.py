"""Build a default Pipeline registry for `lqg` runs.

Centralizes the v0 + v1 checker set and the wiring of rules + LLM
client. Used by `lqg check`/`lqg fix`; tests can build the registry
directly without going through the CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from legal_citations import (
    build_case_form_checker,
    build_pinpoint_checker,
    build_signal_checker,
)
from legal_format_engine import build_formatting_checker
from legal_quality_gate import CheckerRegistry

if TYPE_CHECKING:
    from legal_llm_gateway import LLMClient


def load_rules(path: str | Path | None) -> dict:
    """Load mandatory formatting rules from a YAML file.

    Returns an empty dict if `path` is None. The expected shape mirrors
    what `legal_format_engine.merge_with_rules` consumes:

        page_format:
          font_size_pt: 13.0
          line_spacing: 2.0
    """
    if path is None:
        return {}
    data = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"rules file {path} must contain a mapping at the top level")
    return data


def build_default_registry(
    rules: dict | None = None,
    *,
    llm_client: "LLMClient | None" = None,
) -> CheckerRegistry:
    """Register every default checker.

    - Deterministic checkers always register: `formatting.spec_diff`,
      `bluebook.signal`, `bluebook.pinpoint`.
    - LLM-bound checkers register only when `llm_client` is supplied:
      `bluebook.case_form`. This keeps the offline CLI path free of
      LLM dependencies; pass a `LiteLLMClient` or a `FakeLLMClient` to
      enable them.

    The Pipeline's Policy filters this down further to the enabled set
    if one is supplied; otherwise every registered checker runs.
    """
    registry = CheckerRegistry()
    registry.register(build_formatting_checker(rules=rules or {}))
    registry.register(build_signal_checker())
    registry.register(build_pinpoint_checker())
    if llm_client is not None:
        registry.register(build_case_form_checker(llm=llm_client))
    return registry
