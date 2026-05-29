"""Checker registry.

Checkers register themselves at import time. The Pipeline asks the
registry for the enabled set given a Policy.
"""

from __future__ import annotations

from legal_quality_gate.checker import Checker


class CheckerRegistry:
    def __init__(self) -> None:
        self._by_id: dict[str, Checker] = {}

    def register(self, checker: Checker) -> Checker:
        if checker.id in self._by_id:
            raise ValueError(f"checker id already registered: {checker.id}")
        self._by_id[checker.id] = checker
        return checker

    def get(self, checker_id: str) -> Checker | None:
        return self._by_id.get(checker_id)

    def all(self) -> list[Checker]:
        return list(self._by_id.values())

    def enabled(self, policy_enabled: list[str] | None = None) -> list[Checker]:
        if policy_enabled is None:
            return self.all()
        return [self._by_id[i] for i in policy_enabled if i in self._by_id]


default_registry = CheckerRegistry()
