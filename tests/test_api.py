"""Tests for api/server.py - FastAPI endpoints."""

from __future__ import annotations

import json
import base64
import pytest

from fastapi.testclient import TestClient

from legal_format_engine.api.server import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_status_ok(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_has_version(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert "version" in data


class TestFormatEndpoint:
    def test_format_markdown(self, client):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nThe court should reverse.",
            "output_format": "markdown",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "markdown" in data
        assert len(data["markdown"]) > 0

    def test_format_docx(self, client):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nThe court should reverse.",
            "output_format": "docx",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "docx_base64" in data
        assert "size_bytes" in data
        docx_bytes = base64.b64decode(data["docx_base64"])
        assert docx_bytes[:2] == b"PK"

    def test_format_with_case_meta(self, client):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nTest content.",
            "case_name": "Smith v. Jones",
            "case_number": "2025AP001234",
            "district": "1",
            "parties": [
                {"name": "John Smith", "role": "appellant"},
                {"name": "Jane Jones", "role": "respondent"},
            ],
            "output_format": "markdown",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "2025AP001234" in data["markdown"]

    def test_format_with_attorney(self, client):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nTest.",
            "attorney": {
                "name": "Alice Advocate",
                "bar_number": "123",
                "firm": "Test LLP",
            },
            "output_format": "markdown",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "Alice Advocate" in data["markdown"]

    def test_format_default_jurisdiction(self, client):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nTest.",
            "output_format": "markdown",
        })
        assert resp.status_code == 200

    def test_format_with_word_count(self, client):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nTest.",
            "attorney": {"name": "Jane"},
            "word_count": 9500,
            "output_format": "markdown",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "9500" in data["markdown"]


class TestValidateEndpoint:
    def test_validate_returns_200(self, client):
        resp = client.post("/api/validate", json={
            "text": "ARGUMENT\n\nThe court should reverse.\n\nCONCLUSION\n\nFor the foregoing reasons.",
        })
        assert resp.status_code == 200

    def test_validate_returns_issues(self, client):
        resp = client.post("/api/validate", json={"text": ""})
        data = resp.json()
        assert "issues" in data
        assert "count" in data
        assert data["count"] >= 0

    def test_validate_missing_sections(self, client):
        resp = client.post("/api/validate", json={"text": "ARGUMENT\n\nTest."})
        data = resp.json()
        assert data["count"] >= 1

    def test_validate_issue_structure(self, client):
        resp = client.post("/api/validate", json={"text": "ARGUMENT\n\nTest."})
        data = resp.json()
        if data["issues"]:
            issue = data["issues"][0]
            assert "code" in issue
            assert "severity" in issue
            assert "message" in issue


class TestCitationsEndpoint:
    def test_citations_returns_200(self, client):
        resp = client.post("/api/citations", json={
            "text": "In Smith v. Jones, 100 Wis. 2d 200, the court held."
        })
        assert resp.status_code == 200

    def test_citations_stats(self, client):
        resp = client.post("/api/citations", json={
            "text": "Smith v. Jones, 100 Wis. 2d 200. Id. at 205."
        })
        data = resp.json()
        assert "stats" in data
        assert "citation_count" in data
        assert data["citation_count"] >= 1

    def test_citations_issues(self, client):
        resp = client.post("/api/citations", json={
            "text": "id. at 205."
        })
        data = resp.json()
        assert "issues" in data

    def test_empty_text(self, client):
        resp = client.post("/api/citations", json={"text": ""})
        data = resp.json()
        assert data["citation_count"] == 0


class TestRulesetsEndpoint:
    def test_list_rulesets(self, client):
        resp = client.get("/api/rulesets")
        assert resp.status_code == 200
        data = resp.json()
        assert "rulesets" in data
        assert len(data["rulesets"]) >= 1

    def test_wisconsin_in_rulesets(self, client):
        resp = client.get("/api/rulesets")
        data = resp.json()
        jurisdictions = [r["jurisdiction"] for r in data["rulesets"]]
        assert "wisconsin" in jurisdictions


class TestLetterheadEndpoints:
    def test_create_letterhead(self, client):
        resp = client.post("/api/letterheads", json={
            "name": "Test Firm",
            "lines": [
                {"text": "Test Firm LLP", "bold": True, "alignment": "center"},
                {"text": "123 Main St", "alignment": "center"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Firm"
        assert "id" in data

    def test_list_letterheads(self, client):
        resp = client.get("/api/letterheads")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_letterhead(self, client):
        # Create first
        create_resp = client.post("/api/letterheads", json={
            "name": "Lookup Test",
            "lines": [{"text": "Firm Name"}],
        })
        lh_id = create_resp.json()["id"]

        resp = client.get(f"/api/letterheads/{lh_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Lookup Test"

    def test_get_nonexistent_letterhead(self, client):
        resp = client.get("/api/letterheads/nonexistent-id-12345")
        assert resp.status_code == 404

    def test_delete_letterhead(self, client):
        create_resp = client.post("/api/letterheads", json={
            "name": "To Delete",
            "lines": [],
        })
        lh_id = create_resp.json()["id"]

        resp = client.delete(f"/api/letterheads/{lh_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Should be gone
        resp2 = client.get(f"/api/letterheads/{lh_id}")
        assert resp2.status_code == 404

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/letterheads/fake-id-999")
        assert resp.status_code == 404
