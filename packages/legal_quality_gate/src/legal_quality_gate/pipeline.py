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
import logging
import uuid
from datetime import datetime, timezone

from legal_quality_gate.checker import CheckContext, Checker
from legal_quality_gate.policy import Policy
from legal_quality_gate.registry import CheckerRegistry, default_registry
from legal_quality_gate.scoring import dedupe, score_findings
from legal_quality_gate.types import (
    Capability,
    Document,
    Finding,
    Provenance,
    QualityReport,
    Severity,
)

logger = logging.getLogger(__name__)


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
        started = datetime.now(timezone.utc)

        enabled = self.registry.enabled(self.policy.enabled or None)
        deterministic = [c for c in enabled if _is_deterministic(c)]
        heavy = [c for c in enabled if not _is_deterministic(c)]

        findings: list[Finding] = []
        for group in (deterministic, heavy):
            results = await asyncio.gather(
                *(_invoke(c, document, ctx) for c in group),
                return_exceptions=True,
            )
            for checker, r in zip(group, results):
                if isinstance(r, Exception):
                    logger.exception(
                        "checker %s raised; emitting synthetic finding", checker.id
                    )
                    findings.append(_checker_failed_finding(checker, document, r))
                    continue
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
            finished_at=datetime.now(timezone.utc),
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


def _checker_failed_finding(
    checker: Checker, document: Document, exc: BaseException
) -> Finding:
    """Synthetic finding emitted when a checker crashes mid-run.

    Keeps the rest of the pipeline running and gives ops visibility into
    the failure without leaking exception detail into user-facing
    surfaces unless the checker's severity policy says it should.
    """
    return Finding(
        id=str(uuid.uuid4()),
        segment_id=document.segments[0].id if document.segments else "",
        checker_id=checker.id,
        rule_id="QG.CHECKER.FAILED",
        severity=Severity.WARNING,
        message=f"Checker {checker.id} failed: {type(exc).__name__}",
        evidence={"exception_type": type(exc).__name__, "message": str(exc)},
        provenance=Provenance.RULE,
        confidence=0.0,
    )
