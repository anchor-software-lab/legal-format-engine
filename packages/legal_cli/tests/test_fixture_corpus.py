"""Regression suite over the v0 fixture corpus.

For each fixture in `legal_docx.testing.FIXTURE_BUILDERS`:
  1. Build the docx in tmp_path.
  2. Load `fixtures/docs/<name>.expected.json`.
  3. Run the default v0 registry against it with the fixture's rules.
  4. Assert that every `must_contain` finding shows up and no
     `must_not_contain` finding appears.

Adding a new fixture means: write a builder in `legal_docx.testing`,
register it in `FIXTURE_BUILDERS`, add an `expected.json`, and this
test picks it up automatically.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from legal_docx import parse_docx
from legal_docx.testing import FIXTURE_BUILDERS
from legal_quality_gate import CheckContext, Pipeline

from legal_cli._registry import build_default_registry


FIXTURES_DIR = (
    Path(__file__).resolve().parents[3] / "fixtures" / "docs"
)


def _load_expected(name: str) -> dict:
    path = FIXTURES_DIR / f"{name}.expected.json"
    return json.loads(path.read_text())


def _matches(finding, expectation: dict, segment_id_by_ordinal: dict[int, str]) -> bool:
    if "rule_id" in expectation and finding.rule_id != expectation["rule_id"]:
        return False
    if "severity" in expectation and finding.severity.value != expectation["severity"]:
        return False
    if "segment_ordinal" in expectation:
        expected_segment_id = segment_id_by_ordinal.get(expectation["segment_ordinal"])
        if expected_segment_id is None or finding.segment_id != expected_segment_id:
            return False
    return True


@pytest.mark.parametrize("name", sorted(FIXTURE_BUILDERS.keys()))
def test_fixture(name: str, tmp_path: Path) -> None:
    builder = FIXTURE_BUILDERS[name]
    expected = _load_expected(name)

    docx_path = builder(tmp_path / f"{name}.docx")
    result = parse_docx(docx_path)
    segment_id_by_ordinal = {
        seg.ordinal: seg.id for seg in result.document.segments
    }

    registry = build_default_registry(rules=expected.get("rules", {}))
    ctx = CheckContext(text_loader=result.text_loader)
    report = asyncio.run(Pipeline(registry).run(result.document, ctx))

    for exp in expected.get("must_contain", []):
        assert any(
            _matches(f, exp, segment_id_by_ordinal) for f in report.findings
        ), (
            f"fixture {name!r}: expected a finding matching {exp!r} but got "
            f"{[(f.rule_id, f.segment_id, f.severity.value) for f in report.findings]}"
        )

    for forbidden in expected.get("must_not_contain", []):
        assert not any(
            _matches(f, forbidden, segment_id_by_ordinal) for f in report.findings
        ), (
            f"fixture {name!r}: forbidden finding {forbidden!r} appeared in "
            f"{[(f.rule_id, f.segment_id, f.severity.value) for f in report.findings]}"
        )
