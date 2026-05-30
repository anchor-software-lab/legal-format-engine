"""Structural validation for `apps/office-addin/`.

The Office Add-in is a TypeScript project I can't compile in CI without
Node, but I can at least guard against my hand-edits to the manifest
+ config files introducing the obvious mistakes (malformed XML,
invalid JSON, wrong paths, missing dependencies).

Real type-checking + bundling lands when a Node-equipped CI runner is
wired up.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.etree import ElementTree

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ADDIN_DIR = REPO_ROOT / "apps" / "office-addin"


def test_addin_directory_exists():
    assert ADDIN_DIR.is_dir()


def test_package_json_is_valid_json_and_has_required_scripts():
    data = json.loads((ADDIN_DIR / "package.json").read_text())
    assert data["name"] == "@anchor/office-addin"
    scripts = data.get("scripts") or {}
    for required in ("dev", "build", "typecheck"):
        assert required in scripts, f"package.json missing script: {required}"
    deps = data.get("dependencies") or {}
    # Taskpane needs React + Fluent UI; sanity-check both are pinned.
    assert "react" in deps
    assert "@fluentui/react-components" in deps


def test_tsconfig_is_valid_json_with_strict_mode():
    data = json.loads((ADDIN_DIR / "tsconfig.json").read_text())
    compiler = data["compilerOptions"]
    assert compiler["strict"] is True
    assert "office-js" in compiler["types"]
    # The hand-written TS uses jsx; must be enabled.
    assert compiler["jsx"] == "react-jsx"


def test_manifest_is_valid_xml_with_required_elements():
    tree = ElementTree.parse(ADDIN_DIR / "manifest.xml")
    root = tree.getroot()
    ns = "{http://schemas.microsoft.com/office/appforoffice/1.1}"
    # OfficeApp root
    assert root.tag == f"{ns}OfficeApp"
    # Id + Version + DisplayName are mandatory.
    assert root.find(f"{ns}Id") is not None
    assert root.find(f"{ns}Version") is not None
    assert root.find(f"{ns}DisplayName") is not None
    # Hosts must include "Document" (Word).
    hosts = root.findall(f"{ns}Hosts/{ns}Host")
    assert any(h.get("Name") == "Document" for h in hosts)


def test_taskpane_html_loads_office_js_and_taskpane_entry():
    html = (ADDIN_DIR / "src" / "taskpane" / "index.html").read_text()
    assert "appsforoffice.microsoft.com/lib/1/hosted/office.js" in html
    assert "/src/taskpane/index.tsx" in html


def test_api_types_mirror_finding_schema():
    """The hand-written TS Finding interface must list the same fields
    as the Python Finding model (we hand-mirror until the codegen lands)."""
    types_src = (ADDIN_DIR / "src" / "api" / "types.ts").read_text()
    for field in (
        "rule_id",
        "segment_id",
        "checker_id",
        "severity",
        "message",
        "evidence",
        "suggestion",
        "confidence",
        "provenance",
    ):
        assert f"{field}" in types_src, f"types.ts missing Finding field: {field}"


def test_client_calls_expected_endpoints():
    src = (ADDIN_DIR / "src" / "api" / "client.ts").read_text()
    for path in (
        "/v1/health",
        "/v1/orgs/me/public-key",
        "/v1/documents",
        "/v1/documents/encrypted",
        "/v1/runs",
        "/v1/runs/${runId}",
        "/v1/runs/${runId}/annotated.docx",
    ):
        assert path in src, f"client.ts missing endpoint: {path}"


def test_crypto_uses_aes_gcm_and_rsa_oaep():
    src = (ADDIN_DIR / "src" / "api" / "crypto.ts").read_text()
    # Match the server's `legal_api.envelope` algorithm choices.
    assert "AES-GCM" in src
    assert "RSA-OAEP" in src
    assert 'hash: "SHA-256"' in src or '"SHA-256"' in src


def test_app_tsx_imports_client_and_renders_findings():
    src = (ADDIN_DIR / "src" / "taskpane" / "App.tsx").read_text()
    assert 'from "../api/client"' in src
    assert "AnchorClient" in src
    # Renders at least one of the report fields users care about.
    assert "score" in src.lower()
    assert "findings" in src.lower()


def test_no_trailing_template_artifacts():
    """A common Jinja-confusion bug: leaving `{{` in the output. None
    of the TS/JSON/XML files should ever contain Jinja placeholders."""
    for path in (
        "package.json",
        "tsconfig.json",
        "manifest.xml",
        "src/taskpane/index.html",
        "src/taskpane/index.tsx",
        "src/taskpane/App.tsx",
        "src/api/types.ts",
        "src/api/client.ts",
        "src/api/crypto.ts",
    ):
        contents = (ADDIN_DIR / path).read_text()
        # Match Jinja-style `{{ identifier }}` only — React inline
        # styles like `style={{ padding: 16 }}` are JSX, not Jinja,
        # and contain a colon which Jinja identifier expressions don't.
        leftovers = re.findall(r"\{\{\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\}\}", contents)
        assert not leftovers, f"{path}: stray Jinja placeholders: {leftovers}"
