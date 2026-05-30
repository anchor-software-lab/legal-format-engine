"""End-to-end tests for the FastAPI surface via TestClient.

These tests stand the app up with in-memory stores, drive the upload →
run → fetch → download cycle against a synthesized brief, and assert
both the on-the-wire response shape and the persisted state.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal_api import (
    AppDeps,
    InMemoryApiKeyResolver,
    InMemoryStore,
    RequestPrincipal,
    create_app,
)
from legal_api.blobs import FilesystemBlobStore
from legal_docx.testing import make_sample_brief


@pytest.fixture
def api_key() -> str:
    return "test-key-12345"


@pytest.fixture
def org_id() -> str:
    return "org-test"


@pytest.fixture
def app(tmp_path: Path, api_key: str, org_id: str):
    deps = AppDeps(
        store=InMemoryStore(),
        blobs=FilesystemBlobStore(root=tmp_path / "blobs"),
        api_key_resolver=InMemoryApiKeyResolver(
            by_key={
                api_key: RequestPrincipal(
                    org_id=org_id, api_key_id="k1", scopes=frozenset(["runs:write"])
                )
            }
        ),
    )
    return create_app(deps)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def brief_bytes(tmp_path: Path) -> bytes:
    path = make_sample_brief(tmp_path / "brief.docx")
    return path.read_bytes()


@pytest.fixture
def headers(api_key: str) -> dict:
    return {"X-Anchor-API-Key": api_key}


def test_health_endpoint_open(client):
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_requires_api_key(client, brief_bytes):
    response = client.post(
        "/v1/documents",
        files={
            "file": (
                "brief.docx",
                brief_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 401


def test_upload_rejects_invalid_api_key(client, brief_bytes):
    response = client.post(
        "/v1/documents",
        files={"file": ("brief.docx", brief_bytes, "application/octet-stream")},
        headers={"X-Anchor-API-Key": "bogus"},
    )
    assert response.status_code == 401


def test_upload_rejects_non_docx(client, headers):
    response = client.post(
        "/v1/documents",
        files={"file": ("brief.pdf", b"%PDF-fake", "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 400


def test_upload_returns_document_id(client, headers, brief_bytes):
    response = client.post(
        "/v1/documents",
        files={"file": ("brief.docx", brief_bytes, "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 201
    payload = response.json()
    assert "document_id" in payload
    assert len(payload["document_id"]) > 10


def test_create_run_404s_on_unknown_document(client, headers):
    response = client.post(
        "/v1/runs",
        json={"document_id": "does-not-exist", "mode": "report"},
        headers=headers,
    )
    assert response.status_code == 404


def test_full_upload_and_run_cycle(client, headers, brief_bytes):
    """Upload a brief → start a run → fetch the report → expect real findings."""
    # 1. Upload.
    up = client.post(
        "/v1/documents",
        files={"file": ("brief.docx", brief_bytes, "application/octet-stream")},
        headers=headers,
    )
    assert up.status_code == 201
    document_id = up.json()["document_id"]

    # 2. Create a run.
    run_resp = client.post(
        "/v1/runs",
        json={"document_id": document_id, "mode": "report"},
        headers=headers,
    )
    assert run_resp.status_code == 202
    run_payload = run_resp.json()
    assert run_payload["status"] == "done"
    run_id = run_payload["run_id"]

    # 3. Fetch the report.
    report_resp = client.get(f"/v1/runs/{run_id}", headers=headers)
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert report["document_id"] == document_id
    assert 0 <= report["score"] <= 100
    # The fixture has at least one BB.PINPOINT.MISSING (Brown without pinpoint).
    rule_ids = {f["rule_id"] for f in report["findings"]}
    assert "BB.PINPOINT.MISSING" in rule_ids


def test_run_isolation_across_orgs(tmp_path):
    """Two orgs with separate keys see only their own runs."""
    deps = AppDeps(
        store=InMemoryStore(),
        blobs=FilesystemBlobStore(root=tmp_path / "blobs"),
        api_key_resolver=InMemoryApiKeyResolver(
            by_key={
                "key-a": RequestPrincipal(org_id="org-A", api_key_id="ka"),
                "key-b": RequestPrincipal(org_id="org-B", api_key_id="kb"),
            }
        ),
    )
    app = create_app(deps)
    client = TestClient(app)

    brief = make_sample_brief(tmp_path / "brief.docx").read_bytes()

    # Org A uploads + runs.
    up_a = client.post(
        "/v1/documents",
        files={"file": ("brief.docx", brief, "application/octet-stream")},
        headers={"X-Anchor-API-Key": "key-a"},
    )
    doc_a = up_a.json()["document_id"]
    run_a = client.post(
        "/v1/runs",
        json={"document_id": doc_a, "mode": "report"},
        headers={"X-Anchor-API-Key": "key-a"},
    )
    run_a_id = run_a.json()["run_id"]

    # Org B asks for org A's run → 404, not 200.
    cross = client.get(
        f"/v1/runs/{run_a_id}",
        headers={"X-Anchor-API-Key": "key-b"},
    )
    assert cross.status_code == 404

    # Org B asks for org A's document via create_run → 404.
    cross_doc = client.post(
        "/v1/runs",
        json={"document_id": doc_a, "mode": "report"},
        headers={"X-Anchor-API-Key": "key-b"},
    )
    assert cross_doc.status_code == 404


def test_autofix_mode_produces_annotated_blob(client, headers, brief_bytes):
    """A run with mode=autofix and a font-size rule produces a downloadable
    annotated.docx with the 12pt body raised to the rule's 13pt."""
    from legal_api.main import _default_registry_builder
    from legal_format_engine import build_formatting_checker
    from legal_quality_gate import CheckerRegistry

    # Override the registry to require 13pt — otherwise no auto-safe
    # suggestions exist and nothing gets fixed.
    def registry_builder(rules=None, **kwargs):
        registry = CheckerRegistry()
        registry.register(
            build_formatting_checker(rules={"page_format": {"font_size_pt": 13.0}})
        )
        return registry

    client.app.state.deps.registry_builder = registry_builder

    up = client.post(
        "/v1/documents",
        files={"file": ("brief.docx", brief_bytes, "application/octet-stream")},
        headers=headers,
    )
    document_id = up.json()["document_id"]

    run_resp = client.post(
        "/v1/runs",
        json={"document_id": document_id, "mode": "autofix"},
        headers=headers,
    )
    run_id = run_resp.json()["run_id"]
    assert run_resp.status_code == 202

    download = client.get(f"/v1/runs/{run_id}/annotated.docx", headers=headers)
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    assert len(download.content) > 1000  # actually got a docx back


def test_download_annotated_404_when_no_fix_was_applied(client, headers, brief_bytes):
    """Report-mode run has no annotated blob; download returns 404."""
    up = client.post(
        "/v1/documents",
        files={"file": ("brief.docx", brief_bytes, "application/octet-stream")},
        headers=headers,
    )
    run = client.post(
        "/v1/runs",
        json={"document_id": up.json()["document_id"], "mode": "report"},
        headers=headers,
    )
    download = client.get(f"/v1/runs/{run.json()['run_id']}/annotated.docx", headers=headers)
    assert download.status_code == 404
