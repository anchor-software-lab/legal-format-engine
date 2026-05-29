"""Policy: which checkers run, what severity, what auto-fix is allowed.

A Policy is a small YAML document. Example:

    name: wi_appellate
    enabled:
      - formatting.spec_diff
      - bluebook.case_form
      - citations.exists
    severity_overrides:
      bluebook.case_form: warning
    auto_fix:
      allow:
        - FORMAT.FONT.*
        - BB.SIGNAL.*
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Policy:
    name: str = "default"
    enabled: list[str] = field(default_factory=list)
    severity_overrides: dict[str, str] = field(default_factory=dict)
    auto_fix_allow: list[str] = field(default_factory=list)

    def auto_fix_allowed(self, rule_id: str) -> bool:
        return any(fnmatch.fnmatch(rule_id, pat) for pat in self.auto_fix_allow)


def load_policy(path: str | Path) -> Policy:
    data = yaml.safe_load(Path(path).read_text())
    return Policy(
        name=data.get("name", "default"),
        enabled=list(data.get("enabled", [])),
        severity_overrides=dict(data.get("severity_overrides", {})),
        auto_fix_allow=list(data.get("auto_fix", {}).get("allow", [])),
    )
