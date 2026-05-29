"""Smoke tests for the Pipeline + Checker protocol + registry."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from legal_quality_gate import (
    Capability,
    CheckContext,
    Checker,
    CheckerRegistry,
    Document,
    Finding,
    ObservedStyle,
    Pipeline,
    Policy,
    Provenance,
    Segment,
    SegmentKind,
    Severity,
)


class _FakeChecker:
    id = "test.fake"
    rule_prefix = "TEST.FAKE"
    severity_default = Severity.WARNING
    requires: tuple = ()

    def __init__(self, finding_count: int = 1):
        self.finding_count = finding_count
        self.invoked = 0

    def check(self, document: Document, ctx: CheckContext) -> list[Finding]:
        self.invoked += 1
        return [
            Finding(
                id=str(uuid.uuid4()),
                segment_id=document.segments[0].id,
                checker_id=self.id,
                rule_id=f"{self.rule_prefix}.{i}",
                severity=self.severity_default,
                message=f"{self.id} finding {i}",
                provenance=Provenance.RULE,
            )
            for i in range(self.finding_count)
        ]


class _AsyncFakeChecker(_FakeChecker):
    id = "test.async"
    rule_prefix = "TEST.ASYNC"
    requires: tuple = (Capability.LLM,)

    async def check(self, document, ctx):
        await asyncio.sleep(0)
        return super().check(document, ctx)


def _doc() -> Document:
    return Document(
        id="doc-1",
        sha256="0" * 64,
        segments=[
            Segment(
                id="seg-1",
                kind=SegmentKind.PARAGRAPH,
                ordinal=0,
                text_hash="abc",
                char_length=10,
                style_observed=ObservedStyle(),
            )
        ],
    )


def _ctx() -> CheckContext:
    return CheckContext(text_loader=lambda seg: "x" * seg.char_length)


def test_fake_checker_conforms_to_protocol():
    assert isinstance(_FakeChecker(), Checker)
    assert isinstance(_AsyncFakeChecker(), Checker)


def test_pipeline_runs_sync_and_async_checkers():
    registry = CheckerRegistry()
    sync = _FakeChecker(finding_count=2)
    async_ = _AsyncFakeChecker(finding_count=1)
    registry.register(sync)
    registry.register(async_)

    pipeline = Pipeline(registry)
    report = asyncio.run(pipeline.run(_doc(), _ctx()))

    assert sync.invoked == 1
    assert async_.invoked == 1
    assert len(report.findings) == 3
    assert report.document_id == "doc-1"
    assert 0 <= report.score <= 100


def test_pipeline_runs_deterministic_before_heavy():
    order: list[str] = []

    class _Recorder(_FakeChecker):
        id = "test.recorder"

        def check(self, document, ctx):
            order.append(self.id)
            return []

    class _RecorderLLM(_Recorder):
        id = "test.recorder.llm"
        requires = (Capability.LLM,)

    registry = CheckerRegistry()
    registry.register(_RecorderLLM())
    registry.register(_Recorder())

    asyncio.run(Pipeline(registry).run(_doc(), _ctx()))

    assert order == ["test.recorder", "test.recorder.llm"]


def test_policy_filters_enabled_checkers():
    registry = CheckerRegistry()
    a = _FakeChecker()
    a.id = "a"
    b = _FakeChecker()
    b.id = "b"
    registry.register(a)
    registry.register(b)

    pipeline = Pipeline(registry, policy=Policy(enabled=["a"]))
    report = asyncio.run(pipeline.run(_doc(), _ctx()))

    assert a.invoked == 1
    assert b.invoked == 0
    assert len(report.findings) == 1


def test_policy_severity_override():
    registry = CheckerRegistry()
    checker = _FakeChecker()
    checker.id = "override.me"
    registry.register(checker)

    pipeline = Pipeline(
        registry,
        policy=Policy(severity_overrides={"override.me": "error"}),
    )
    report = asyncio.run(pipeline.run(_doc(), _ctx()))

    assert all(f.severity is Severity.ERROR for f in report.findings)


def test_registry_rejects_duplicate_ids():
    registry = CheckerRegistry()
    a = _FakeChecker()
    a.id = "dupe"
    b = _FakeChecker()
    b.id = "dupe"
    registry.register(a)
    with pytest.raises(ValueError):
        registry.register(b)
