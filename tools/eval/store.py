"""DuckDB-backed results store.

Three tables:

    runs           — one row per `RunReport`.
    case_results   — one row per (run, case, model).
    scores         — one row per (run, case, model, scorer).

The schema is intentionally flat + normalized so historical queries
like "p95 accuracy of prompt X on model Y over the last 30 days" are
one-liners. Migration: add new columns with `ALTER TABLE` and bump
`SCHEMA_VERSION`. The schema_version row in `runs.config_json` tells
us how to interpret older rows.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import duckdb

from tools.eval.types import RunReport


SCHEMA_VERSION = 1


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    dataset_path TEXT,
    models JSON,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    config JSON,
    schema_version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS case_results (
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    prompt_id TEXT NOT NULL,
    model TEXT NOT NULL,
    schema_valid BOOLEAN NOT NULL,
    confidence DOUBLE,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    cached BOOLEAN NOT NULL DEFAULT FALSE,
    error TEXT,
    raw_output JSON,
    parsed_output JSON,
    expected JSON,
    ran_at TIMESTAMP NOT NULL,
    PRIMARY KEY (run_id, case_id, model)
);

CREATE TABLE IF NOT EXISTS scores (
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    model TEXT NOT NULL,
    scorer TEXT NOT NULL,
    score DOUBLE NOT NULL,
    PRIMARY KEY (run_id, case_id, model, scorer)
);
"""


@contextmanager
def open_store(path: str | Path) -> Iterator[duckdb.DuckDBPyConnection]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    try:
        con.execute(_SCHEMA_SQL)
        yield con
    finally:
        con.close()


def write_report(con: duckdb.DuckDBPyConnection, report: RunReport, *, expected_by_case: dict[str, dict] | None = None) -> None:
    expected_by_case = expected_by_case or {}
    con.execute(
        """
        INSERT INTO runs (run_id, prompt_id, dataset_path, models, started_at,
                          finished_at, config, schema_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report.run_id,
            report.prompt_id,
            report.dataset_path,
            json.dumps(report.models),
            report.started_at,
            report.finished_at,
            json.dumps(report.config),
            SCHEMA_VERSION,
        ),
    )

    for cr in report.case_results:
        con.execute(
            """
            INSERT INTO case_results
                (run_id, case_id, prompt_id, model, schema_valid, confidence,
                 cost_cents, latency_ms, cached, error, raw_output,
                 parsed_output, expected, ran_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.run_id,
                cr.case_id,
                cr.prompt_id,
                cr.model,
                cr.schema_valid,
                cr.confidence,
                cr.cost_cents,
                cr.latency_ms,
                cr.cached,
                cr.error,
                json.dumps(cr.raw_output) if cr.raw_output else None,
                json.dumps(cr.parsed_output) if cr.parsed_output else None,
                json.dumps(expected_by_case.get(cr.case_id, {})),
                cr.ran_at,
            ),
        )
        for scorer, value in cr.scores.items():
            con.execute(
                """
                INSERT INTO scores (run_id, case_id, model, scorer, score)
                VALUES (?, ?, ?, ?, ?)
                """,
                (report.run_id, cr.case_id, cr.model, scorer, float(value)),
            )


def latest_run_ids(
    con: duckdb.DuckDBPyConnection, prompt_id: str, *, limit: int = 30
) -> list[str]:
    rows = con.execute(
        """
        SELECT run_id FROM runs
        WHERE prompt_id = ?
        ORDER BY started_at DESC
        LIMIT ?
        """,
        (prompt_id, limit),
    ).fetchall()
    return [r[0] for r in rows]


def mean_score_for_run(
    con: duckdb.DuckDBPyConnection, run_id: str, *, model: str, scorer: str
) -> float:
    row = con.execute(
        """
        SELECT AVG(score) FROM scores
        WHERE run_id = ? AND model = ? AND scorer = ?
        """,
        (run_id, model, scorer),
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0
