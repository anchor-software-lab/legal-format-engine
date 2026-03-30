"""Tests for letterhead model, manager, DOCX rendering, and API endpoints."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal_format_engine.api.server import app
from legal_format_engine.letterheads.examples import anchor_filings_letterhead, blank_letterhead
from legal_format_engine.models.letterhead import (
    Letterhead,
    LetterheadLine,
    LetterheadManager,
)


# ── Model Tests ───────────────────────────────────────────────────────


class TestLetterheadModel:
    def test_create_minimal(self):
        lh = Letterhead(name="Test")
        assert lh.name == "Test"
        assert lh.lines == []
        assert lh.logo_path is None
        assert lh.separator_line is True
        assert len(lh.id) == 12

    def test_create_with_lines(self):
        lh = Letterhead(
            name="Full",
            lines=[
                LetterheadLine(text="FIRM NAME", bold=True, font_size_pt=16),
                LetterheadLine(text="123 Main St", font_size_pt=9),
            ],
        )
        assert len(lh.lines) == 2
        assert lh.lines[0].bold is True
        assert lh.lines[0].font_size_pt == 16
        assert lh.lines[1].alignment == "center"

    def test_letterhead_line_defaults(self):
        line = LetterheadLine(text="Hello")
        assert line.bold is False
        assert line.italic is False
        assert line.font_size_pt is None
        assert line.alignment == "center"

    def test_serialization_roundtrip(self):
        lh = Letterhead(
            name="Roundtrip",
            lines=[LetterheadLine(text="Test", bold=True)],
            spacing_after_pt=20.0,
        )
        data = json.loads(lh.model_dump_json())
        restored = Letterhead.model_validate(data)
        assert restored.name == "Roundtrip"
        assert restored.lines[0].bold is True
        assert restored.spacing_after_pt == 20.0


# ── Manager Tests ─────────────────────────────────────────────────────


class TestLetterheadManager:
    @pytest.fixture
    def mgr(self, tmp_path):
        return LetterheadManager(storage_dir=tmp_path / "letterheads")

    def test_empty_list(self, mgr):
        assert mgr.list() == []

    def test_save_and_get(self, mgr):
        lh = Letterhead(name="Test Firm")
        saved = mgr.save(lh)
        assert saved.name == "Test Firm"

        loaded = mgr.get(lh.id)
        assert loaded is not None
        assert loaded.name == "Test Firm"

    def test_save_and_list(self, mgr):
        mgr.save(Letterhead(name="Firm A"))
        mgr.save(Letterhead(name="Firm B"))
        result = mgr.list()
        assert len(result) == 2
        names = {lh.name for lh in result}
        assert "Firm A" in names
        assert "Firm B" in names

    def test_delete(self, mgr):
        lh = Letterhead(name="To Delete")
        mgr.save(lh)
        assert mgr.get(lh.id) is not None

        deleted = mgr.delete(lh.id)
        assert deleted is True
        assert mgr.get(lh.id) is None

    def test_delete_nonexistent(self, mgr):
        assert mgr.delete("nonexistent") is False

    def test_get_nonexistent(self, mgr):
        assert mgr.get("nonexistent") is None

    def test_update_existing(self, mgr):
        lh = Letterhead(name="Original")
        mgr.save(lh)

        lh.name = "Updated"
        lh.lines = [LetterheadLine(text="New Line")]
        mgr.save(lh)

        loaded = mgr.get(lh.id)
        assert loaded.name == "Updated"
        assert len(loaded.lines) == 1

    def test_save_with_logo(self, mgr, tmp_path):
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"\x89PNG fake image data")

        lh = Letterhead(name="With Logo")
        saved = mgr.save(lh, logo_source=logo)
        assert saved.logo_path is not None
        assert Path(saved.logo_path).exists()

    def test_delete_removes_logo(self, mgr, tmp_path):
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"\x89PNG fake image data")

        lh = Letterhead(name="Logo Delete")
        saved = mgr.save(lh, logo_source=logo)
        logo_path = Path(saved.logo_path)
        assert logo_path.exists()

        mgr.delete(lh.id)
        assert not logo_path.exists()


# ── Example Letterheads ───────────────────────────────────────────────


class TestExampleLetterheads:
    def test_anchor_filings(self):
        lh = anchor_filings_letterhead()
        assert lh.id == "dev_anchor_filings"
        assert lh.name == "Anchor Filings"
        assert len(lh.lines) >= 5
        assert lh.lines[0].text == "ANCHOR FILINGS"
        assert lh.lines[0].bold is True
        assert "Smith" in lh.lines[3].text or "Anchor" in lh.lines[0].text

    def test_blank_template(self):
        lh = blank_letterhead()
        assert lh.id == "template_blank"
        assert "[FIRM NAME]" in lh.lines[0].text


# ── DOCX Rendering with Letterhead ───────────────────────────────────


class TestLetterheadDocxRendering:
    def _make_doc(self):
        from legal_format_engine.models.document import (
            ContentBlock, HeadingLevel, LegalDocument, Section,
        )
        return LegalDocument(
            sections=[
                Section(
                    id="argument",
                    heading_text="ARGUMENT",
                    heading_level=HeadingLevel.LEVEL_1,
                    content=[ContentBlock(text="The court erred.")],
                ),
            ],
        )

    def _make_ruleset(self):
        from legal_format_engine.rules.loader import load_ruleset
        return load_ruleset("wisconsin", "appellate", "brief")

    def test_render_without_letterhead(self, tmp_path):
        from legal_format_engine.renderers.docx_renderer import render_docx
        doc = self._make_doc()
        ruleset = self._make_ruleset()
        out = tmp_path / "no_lh.docx"
        render_docx(doc, ruleset, str(out))
        assert out.exists()
        assert out.stat().st_size > 100

    def test_render_with_letterhead(self, tmp_path):
        from legal_format_engine.renderers.docx_renderer import render_docx
        doc = self._make_doc()
        ruleset = self._make_ruleset()
        lh = anchor_filings_letterhead()
        out = tmp_path / "with_lh.docx"
        render_docx(doc, ruleset, str(out), letterhead=lh)
        assert out.exists()
        # File with letterhead should be larger
        no_lh = tmp_path / "no_lh2.docx"
        render_docx(doc, ruleset, str(no_lh))
        assert out.stat().st_size > no_lh.stat().st_size

    def test_render_with_blank_template(self, tmp_path):
        from legal_format_engine.renderers.docx_renderer import render_docx
        doc = self._make_doc()
        ruleset = self._make_ruleset()
        lh = blank_letterhead()
        out = tmp_path / "blank_lh.docx"
        render_docx(doc, ruleset, str(out), letterhead=lh)
        assert out.exists()


# ── API Tests ─────────────────────────────────────────────────────────


client = TestClient(app)


class TestLetterheadAPI:
    def test_list_empty(self):
        resp = client.get("/api/letterheads")
        assert resp.status_code == 200
        # May have leftover from other tests, but structure is correct
        data = resp.json()
        assert "letterheads" in data
        assert isinstance(data["letterheads"], list)

    def test_create_letterhead(self):
        resp = client.post("/api/letterheads", json={
            "name": "API Test Firm",
            "lines": [
                {"text": "TEST FIRM", "bold": True, "font_size_pt": 14, "alignment": "center"},
                {"text": "123 Test Ave", "font_size_pt": 9, "alignment": "center"},
            ],
            "separator_line": True,
            "spacing_after_pt": 10,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Test Firm"
        assert len(data["lines"]) == 2
        assert data["id"]

    def test_create_and_get(self):
        # Create
        resp = client.post("/api/letterheads", json={
            "name": "Get Test",
            "lines": [{"text": "Line 1"}],
        })
        lh_id = resp.json()["id"]

        # Get
        resp = client.get(f"/api/letterheads/{lh_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Test"

    def test_get_nonexistent(self):
        resp = client.get("/api/letterheads/nonexistent_id")
        assert resp.status_code == 404

    def test_update_letterhead(self):
        # Create
        resp = client.post("/api/letterheads", json={
            "name": "Before Update",
            "lines": [],
        })
        lh_id = resp.json()["id"]

        # Update
        resp = client.put(f"/api/letterheads/{lh_id}", json={
            "name": "After Update",
            "lines": [{"text": "Updated Line"}],
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "After Update"

    def test_update_nonexistent(self):
        resp = client.put("/api/letterheads/nonexistent_id", json={
            "name": "Nope",
            "lines": [],
        })
        assert resp.status_code == 404

    def test_delete_letterhead(self):
        # Create
        resp = client.post("/api/letterheads", json={
            "name": "To Delete",
            "lines": [],
        })
        lh_id = resp.json()["id"]

        # Delete
        resp = client.delete(f"/api/letterheads/{lh_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Confirm gone
        resp = client.get(f"/api/letterheads/{lh_id}")
        assert resp.status_code == 404

    def test_delete_nonexistent(self):
        resp = client.delete("/api/letterheads/nonexistent_id")
        assert resp.status_code == 404

    def test_format_with_letterhead(self):
        # Create a letterhead
        resp = client.post("/api/letterheads", json={
            "name": "Format Test LH",
            "lines": [{"text": "MY FIRM", "bold": True}],
        })
        lh_id = resp.json()["id"]

        # Format with letterhead
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nContent.\n\nCONCLUSION\n\nDone.",
            "metadata": _meta_dict(),
            "output_format": "docx",
            "letterhead_id": lh_id,
        })
        assert resp.status_code == 200
        assert "openxmlformats" in resp.headers["content-type"]

    def test_format_with_invalid_letterhead(self):
        resp = client.post("/api/format", json={
            "text": "ARGUMENT\n\nContent.",
            "metadata": _meta_dict(),
            "output_format": "docx",
            "letterhead_id": "nonexistent",
        })
        assert resp.status_code == 404


def _meta_dict():
    return {
        "jurisdiction": "wisconsin",
        "court_level": "appellate",
        "document_type": "brief",
        "case": {
            "case_number": "2025AP001234-CR",
            "court_name": "Court of Appeals",
            "parties": [
                {"name": "State of Wisconsin", "role": "plaintiff-respondent"},
                {"name": "John Test", "role": "defendant-appellant"},
            ],
        },
        "attorney": {
            "name": "Jane Doe",
            "bar_number": "1234567",
            "address": "123 Main St",
            "phone": "(608) 555-1234",
            "email": "jane@test.com",
        },
        "document_title": "Brief of Defendant-Appellant",
    }
