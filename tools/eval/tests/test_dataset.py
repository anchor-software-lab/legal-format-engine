"""Tests for the JSONL dataset loader / writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.eval.dataset import iter_dataset, load_dataset, write_dataset
from tools.eval.types import EvalCase


def _write(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n")
    return path


def test_load_round_trip(tmp_path: Path):
    case = EvalCase(
        id="c-1",
        input={"raw": "Tews v NHI 2010 WI 137"},
        expected={"canonical": "Tews v. NHI, LLC, 2010 WI 137"},
        tags=("wi", "neutral"),
        difficulty="easy",
        source="human",
    )
    out = write_dataset(tmp_path / "ds.jsonl", [case])
    loaded = load_dataset(out)
    assert loaded == [case]


def test_load_skips_blank_and_comments(tmp_path: Path):
    raw = [
        '{"id":"c","input":{"x":1},"expected":{"y":2}}',
        "",
        "# a comment",
        '{"id":"d","input":{"x":1},"expected":{"y":2}}',
    ]
    cases = load_dataset(_write(tmp_path / "ds.jsonl", raw))
    assert {c.id for c in cases} == {"c", "d"}


def test_iter_dataset_streams(tmp_path: Path):
    raw = [
        '{"id":"c","input":{"x":1},"expected":{"y":2}}',
        '{"id":"d","input":{"x":1},"expected":{"y":2}}',
    ]
    it = iter_dataset(_write(tmp_path / "ds.jsonl", raw))
    first = next(it)
    second = next(it)
    with pytest.raises(StopIteration):
        next(it)
    assert first.id == "c"
    assert second.id == "d"


def test_load_rejects_missing_required_fields(tmp_path: Path):
    raw = ['{"id":"c","input":{"x":1}}']  # missing `expected`
    with pytest.raises(ValueError, match="expected"):
        load_dataset(_write(tmp_path / "bad.jsonl", raw))


def test_load_rejects_malformed_json(tmp_path: Path):
    raw = ["{not json"]
    with pytest.raises(ValueError, match="invalid JSON"):
        load_dataset(_write(tmp_path / "bad.jsonl", raw))
