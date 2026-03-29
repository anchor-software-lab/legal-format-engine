"""Tests for the FastAPI server endpoints."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal_format_engine.api.server import app

client = TestClient(app)


def _meta_dict():
    return {
        "jurisdiction": "wisconsin",
        "court_level": "appellate",
        "document_type": "brief",
        "case": {
            "case_number": "2025AP001234-CR",
            "court_name": "Court of Appeals",
            "district": "District II",
            "county_of_origin": "Dane",
            "judge_name": "Hon. Smith",
            "parties": [
                {"name": "State of Wisconsin", "role": "plaintiff-respondent"},
                {"name": "John Test", "role": "defendant-appellant"},
            ],
        },
        "attorney": {
            "name": "Jane Doe",
            "bar_number": "1234567",
            "firm": "SPD",
            "address": "123 Main St",
            "phone": "(608) 555-1234",
            "email": "jane@spd.wi.gov",
        },
        "document_title": "Brief of Defendant-Appellant",
    }


# ── Health ────────────────────────────────────────────────────────────


class TestHealth:
    def test_health(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


# ── Validate ──────────────────────────────────────────────────────────


class TestValidate:
    def test_validate_empty_text(self):
        resp = client.post("/api/validate", json={
            "text": "",
            "metadata": _meta_dict(),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["issue_count"] > 0

    def test_validate_with_sections(self):
        text = (
            "STATEMENT OF ISSUES\n\nIssue.\n\n"
            "ARGUMENT\n\nArgument.\n\n"
            "CONCLUSION\n\nDone.\n"
        )
        resp = client.post("/api/validate", json={
            "text": text,
            "metadata": _meta_dict(),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["issues"], list)
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) >= 3

    def test_validate_with_variant(self):
        resp = client.post("/api/validate", json={
            "text": "ARGUMENT\n\nContent.",
            "metadata": _meta_dict(),
            "variant": "spd",
        })
        assert resp.status_code == 200

    def test_validate_invalid_ruleset(self):
        resp = client.post("/api/validate", json={
            "text": "ARGUMENT\n\nContent.",
            "metadata": _meta_dict(),
            "jurisdiction": "nonexistent",
        })
        assert resp.status_code == 404


# ── Format ────────────────────────────────────────────────────────────


class TestFormat:
    def test_format_markdown(self):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nThe court erred.\n\nCONCLUSION\n\nReverse.",
            "metadata": _meta_dict(),
            "output_format": "markdown",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "markdown" in data
        assert "ARGUMENT" in data["markdown"]
        assert isinstance(data["issues"], list)
        assert isinstance(data["sections"], list)

    def test_format_docx(self):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nThe court erred.\n\nCONCLUSION\n\nReverse.",
            "metadata": _meta_dict(),
            "output_format": "docx",
        })
        assert resp.status_code == 200
        assert "openxmlformats" in resp.headers["content-type"]
        assert len(resp.content) > 100

    def test_format_with_word_count(self):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nContent.\n\nCONCLUSION\n\nDone.",
            "metadata": _meta_dict(),
            "output_format": "markdown",
            "word_count": 5000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "5000" in data["markdown"] or "5,000" in data["markdown"]

    def test_format_no_insert_missing(self):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nContent.",
            "metadata": _meta_dict(),
            "output_format": "markdown",
            "insert_missing": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        generated = [s for s in data["sections"] if s["is_generated"]]
        assert len(generated) == 0

    def test_format_spd_variant(self):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nContent.\n\nCONCLUSION\n\nDone.",
            "metadata": _meta_dict(),
            "output_format": "docx",
            "variant": "spd",
        })
        assert resp.status_code == 200


# ── Format Upload ─────────────────────────────────────────────────────


class TestFormatUpload:
    def test_upload_text_file(self):
        text_content = "ARGUMENT\n\nThe court erred.\n\nCONCLUSION\n\nReverse."
        resp = client.post(
            "/api/format/upload",
            files={"file": ("brief.txt", text_content.encode(), "text/plain")},
            data={
                "metadata_json": json.dumps(_meta_dict()),
                "output_format": "markdown",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "ARGUMENT" in data["markdown"]

    def test_upload_invalid_metadata(self):
        resp = client.post(
            "/api/format/upload",
            files={"file": ("brief.txt", b"content", "text/plain")},
            data={"metadata_json": "not json"},
        )
        assert resp.status_code == 422


# ── Citations ─────────────────────────────────────────────────────────


class TestCitations:
    def test_citations_basic(self):
        text = "State v. Sullivan, 216 Wis. 2d 768 (1998). Id. at 774."
        resp = client.post("/api/citations", json={"text": text})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_citations"] >= 2
        assert data["cases"] >= 1
        assert data["id_references"] >= 1

    def test_citations_empty(self):
        resp = client.post("/api/citations", json={"text": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_citations"] == 0

    def test_citations_statutes(self):
        text = "under s. 809.19(8)(b) and s. 904.04(2)(a)"
        resp = client.post("/api/citations", json={"text": text})
        assert resp.status_code == 200
        data = resp.json()
        assert data["statutes"] >= 2

    def test_citations_with_issues(self):
        text = "under §904.04(2)"
        resp = client.post("/api/citations", json={"text": text})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["issues"]) >= 1

    def test_citations_upload(self):
        text = "State v. Sullivan, 216 Wis. 2d 768 (1998)."
        resp = client.post(
            "/api/citations/upload",
            files={"file": ("brief.txt", text.encode(), "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cases"] >= 1


# ── Validate Upload ───────────────────────────────────────────────────


class TestValidateUpload:
    def test_validate_upload_text(self):
        text = "ARGUMENT\n\nContent.\n\nCONCLUSION\n\nDone."
        resp = client.post(
            "/api/validate/upload",
            files={"file": ("brief.txt", text.encode(), "text/plain")},
            data={"metadata_json": json.dumps(_meta_dict())},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["issues"], list)
