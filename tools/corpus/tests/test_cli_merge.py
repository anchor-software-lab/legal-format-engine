"""Tests for the `corpus merge` command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from tools.corpus.cli import app


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def test_merge_concatenates_and_dedupes(tmp_path: Path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    out = tmp_path / "merged.jsonl"
    _write_jsonl(a, [
        {"id": "c1", "input": {"raw": "x"}, "expected": {"canonical": "X"}},
        {"id": "c2", "input": {"raw": "y"}, "expected": {"canonical": "Y"}},
    ])
    _write_jsonl(b, [
        {"id": "c2", "input": {"raw": "y'"}, "expected": {"canonical": "Y'"}},  # dup id
        {"id": "c3", "input": {"raw": "z"}, "expected": {"canonical": "Z"}},
    ])

    runner = CliRunner()
    result = runner.invoke(app, ["merge", str(a), str(b), "--out", str(out)])
    assert result.exit_code == 0

    records = [json.loads(line) for line in out.read_text().splitlines() if line]
    ids = [r["id"] for r in records]
    assert ids == ["c1", "c2", "c3"]
    # First-wins on dup: c2 keeps its original canonical = "Y".
    c2 = next(r for r in records if r["id"] == "c2")
    assert c2["expected"]["canonical"] == "Y"


def test_merge_skips_blank_and_comment_lines(tmp_path: Path):
    a = tmp_path / "a.jsonl"
    a.write_text(
        '# comment\n'
        '\n'
        '{"id":"c1","input":{"x":1},"expected":{"y":2}}\n'
    )
    out = tmp_path / "out.jsonl"
    runner = CliRunner()
    runner.invoke(app, ["merge", str(a), "--out", str(out)])
    lines = [l for l in out.read_text().splitlines() if l.strip()]
    assert len(lines) == 1


def test_extract_text_command_produces_candidates(tmp_path: Path):
    src = tmp_path / "brief.txt"
    src.write_text(
        "We review summary judgment de novo. See Tews v. NHI, LLC, "
        "2010 WI 137, ¶ 4. The trial court erred."
    )
    out = tmp_path / "candidates.jsonl"
    runner = CliRunner()
    result = runner.invoke(
        app, ["extract", str(src), "--out", str(out), "--text"]
    )
    assert result.exit_code == 0
    records = [json.loads(line) for line in out.read_text().splitlines() if line]
    assert any(
        "Tews" in (r.get("expected", {}).get("canonical") or "")
        for r in records
    )
