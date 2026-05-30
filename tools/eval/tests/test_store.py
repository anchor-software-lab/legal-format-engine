"""Tests for the DuckDB results store."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.eval.store import (
    latest_run_ids,
    mean_score_for_run,
    open_store,
    write_report,
)
from tools.eval.types import CaseResult, RunReport


def _report(run_id: str, *, prompt_id: str = "p@1", model: str = "m1") -> RunReport:
    now = datetime.now(timezone.utc)
    return RunReport(
        run_id=run_id,
        prompt_id=prompt_id,
        dataset_path="ds.jsonl",
        models=[model],
        case_results=[
            CaseResult(
                case_id="c1", prompt_id=prompt_id, model=model,
                raw_output={"canonical": "x"},
                parsed_output={"canonical": "x", "confidence": 0.9},
                schema_valid=True, confidence=0.9,
                cost_cents=2, latency_ms=500,
                scores={"bluebook_fuzzy": 1.0, "exact_match": 1.0},
                ran_at=now,
            ),
            CaseResult(
                case_id="c2", prompt_id=prompt_id, model=model,
                schema_valid=False, error="bad json",
                cost_cents=1, latency_ms=200,
                scores={"bluebook_fuzzy": 0.0, "exact_match": 0.0},
                ran_at=now,
            ),
        ],
        started_at=now,
        finished_at=now + timedelta(seconds=2),
    )


def test_write_and_read_back(tmp_path: Path):
    db = tmp_path / "results.duckdb"
    with open_store(db) as con:
        write_report(con, _report("run-A"))
        # runs table has one row.
        n = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        assert n == 1
        # case_results has two.
        n = con.execute("SELECT COUNT(*) FROM case_results").fetchone()[0]
        assert n == 2
        # scores has four (2 cases × 2 scorers).
        n = con.execute("SELECT COUNT(*) FROM scores").fetchone()[0]
        assert n == 4


def test_latest_run_ids_orders_by_started_at(tmp_path: Path):
    db = tmp_path / "results.duckdb"
    with open_store(db) as con:
        # Write three runs with offsetted start times.
        for i in range(3):
            report = _report(f"run-{i}")
            # Stagger started_at so ordering is deterministic.
            report.started_at = datetime.now(timezone.utc) + timedelta(seconds=i)
            write_report(con, report)
        ids = latest_run_ids(con, "p@1", limit=2)
    assert ids == ["run-2", "run-1"]


def test_mean_score_for_run(tmp_path: Path):
    db = tmp_path / "results.duckdb"
    with open_store(db) as con:
        write_report(con, _report("run-A"))
        score = mean_score_for_run(con, "run-A", model="m1", scorer="bluebook_fuzzy")
    assert score == 0.5  # 1 right + 1 wrong


def test_store_reopen_preserves_data(tmp_path: Path):
    db = tmp_path / "results.duckdb"
    with open_store(db) as con:
        write_report(con, _report("run-A"))
    with open_store(db) as con2:
        n = con2.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        assert n == 1
