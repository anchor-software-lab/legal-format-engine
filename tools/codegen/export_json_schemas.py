"""Export Pydantic models in `legal_quality_gate.types` to JSON schemas.

Run from the repo root:

    python tools/codegen/export_json_schemas.py

Writes one schema file per public model to `schemas/json-schema/`.
Re-run after changing any type so the TS / C# code generators (in v1)
pick up the new shape. The output is the source of truth for the
SaaS REST contract, the Office Add-in TypeScript client, and the VSTO
C# client.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]

# Make every package importable without installing the workspace.
for pkg in [
    "legal_quality_gate",
    "legal_format_engine",
    "legal_docx",
    "legal_citations",
    "legal_llm_gateway",
]:
    sys.path.insert(0, str(REPO_ROOT / "packages" / pkg / "src"))


def _models_to_export() -> Iterable[tuple[str, type]]:
    """Return (filename_stem, model_class) pairs."""
    from legal_quality_gate import (
        Authority,
        Citation,
        Document,
        Finding,
        ObservedStyle,
        ParsedCitation,
        QualityReport,
        Segment,
        Suggestion,
        Treatment,
    )
    from legal_llm_gateway import LLMResult, LLMUsage, PromptSpec

    yield "document", Document
    yield "segment", Segment
    yield "observed_style", ObservedStyle
    yield "finding", Finding
    yield "suggestion", Suggestion
    yield "citation", Citation
    yield "parsed_citation", ParsedCitation
    yield "quality_report", QualityReport
    yield "authority", Authority
    yield "treatment", Treatment
    yield "llm_usage", LLMUsage
    yield "llm_result", LLMResult
    yield "prompt_spec", PromptSpec


def main() -> int:
    out_dir = REPO_ROOT / "schemas" / "json-schema"
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for stem, model in _models_to_export():
        path = out_dir / f"{stem}.schema.json"
        try:
            schema = model.model_json_schema(mode="serialization")
        except Exception as exc:  # noqa: BLE001 - codegen script, tolerate
            print(f"  ! skipping {stem}: {exc}", file=sys.stderr)
            continue
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        written.append(stem)

    print(f"Wrote {len(written)} schemas to {out_dir}:")
    for w in written:
        print(f"  - {w}.schema.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
