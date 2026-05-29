"""The Pipeline orchestrator.

Runs the enabled checkers from the registry against a Document, scoring
and deduplicating the findings, and returns a QualityReport. Checkers
may be sync or async (returning a list[Finding] either directly or as a
coroutine). Deterministic checkers run first; checkers that require
network or LLM capability run after, so cheap fast findings surface
before expensive ones.
"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from datetime import datetime

from legal_quality_gate.checker import CheckContext, Checker
from legal_quality_gate.policy import Policy
from legal_quality_gate.registry import CheckerRegistry, default_registry
from legal_quality_gate.scoring import dedupe, score_findings
from legal_quality_gate.types import (
    Capability,
    Document,
    Finding,
    QualityReport,
    Severity,
)


class Pipeline:
    def __init__(
        self,
        registry: CheckerRegistry | None = None,
        *,
        policy: Policy | None = None,
    ) -> None:
        self.registry = registry or default_registry
        self.policy = policy or Policy()

    async def run(self, document: Document, ctx: CheckContext) -> QualityReport:
        run_id = str(uuid.uuid4())
        started = datetime.utcnow()

        enabled = self.registry.enabled(self.policy.enabled or None)
        deterministic = [c for c in enabled if _is_deterministic(c)]
        heavy = [c for c in enabled if not _is_deterministic(c)]

        findings: list[Finding] = []
        for group in (deterministic, heavy):
            results = await asyncio.gather(
                *(_invoke(c, document, ctx) for c in group), return_exceptions=False
            )
            for r in results:
                findings.extend(r)

        # Severity overrides from policy
        for f in findings:
            override = self.policy.severity_overrides.get(f.checker_id)
            if override:
                f.severity = Severity(override)

        findings = dedupe(findings)
        score = score_findings(findings)

        return QualityReport(
            document_id=document.id,
            run_id=run_id,
            findings=findings,
            score=score,
            remaining_findings=[f.id for f in findings],
            started_at=started,
            finished_at=datetime.utcnow(),
        )


def _is_deterministic(checker: Checker) -> bool:
    reqs = set(checker.requires)
    return Capability.LLM not in reqs and Capability.NETWORK not in reqs


async def _invoke(
    checker: Checker, document: Document, ctx: CheckContext
) -> list[Finding]:
    result = checker.check(document, ctx)
    if inspect.isawaitable(result):
        return await result
    return result
