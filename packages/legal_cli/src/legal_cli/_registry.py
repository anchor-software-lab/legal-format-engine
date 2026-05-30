"""Build a default Pipeline registry for `lqg` runs.

Centralizes the list of v0 checkers and the wiring of rules into the
formatting checker. Used by `lqg check`; tests can also build the
registry directly without going through the CLI.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from legal_citations import build_pinpoint_checker, build_signal_checker
from legal_format_engine import build_formatting_checker
from legal_quality_gate import CheckerRegistry


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


def build_default_registry(rules: dict | None = None) -> CheckerRegistry:
    """Register every v0 checker.

    The Policy in the Pipeline filters this down to the enabled set; if
    no Policy is supplied, every registered checker runs.
    """
    registry = CheckerRegistry()
    registry.register(build_formatting_checker(rules=rules or {}))
    registry.register(build_signal_checker())
    registry.register(build_pinpoint_checker())
    return registry
