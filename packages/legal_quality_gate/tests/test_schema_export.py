"""CI guard against schema drift.

If a Pydantic type in `legal_quality_gate.types` (or related) changes
without re-running `tools/codegen/export_json_schemas.py`, this test
fails and points the developer at the stale file. Keeps the
cross-language contracts (TS / C# / Python clients) honest.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "schemas" / "json-schema"
CODEGEN_PATH = REPO_ROOT / "tools" / "codegen" / "export_json_schemas.py"


def _import_codegen():
    """Import the codegen script as a module without executing main()."""
    import importlib.util

    sys.path.insert(0, str(CODEGEN_PATH.parent))
    spec = importlib.util.spec_from_file_location(
        "_export_json_schemas", CODEGEN_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checked_in_schemas_match_current_models() -> None:
    """Each (stem, model) pair from the codegen must match disk."""
    codegen = _import_codegen()

    drift: list[str] = []
    for stem, model in codegen._models_to_export():
        path = SCHEMA_DIR / f"{stem}.schema.json"
        if not path.exists():
            pytest.fail(
                f"schema {path.name} is missing; run "
                f"`python {CODEGEN_PATH.relative_to(REPO_ROOT)}` and commit."
            )
        on_disk = json.loads(path.read_text())
        in_memory = model.model_json_schema(mode="serialization")
        if on_disk != in_memory:
            drift.append(stem)

    assert not drift, (
        f"checked-in schemas are stale: {drift}. Run "
        f"`python {CODEGEN_PATH.relative_to(REPO_ROOT)}` and commit."
    )
