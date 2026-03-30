"""Tests for letterhead models and manager."""

from __future__ import annotations

import json
import pytest

from legal_format_engine.letterhead.models import Letterhead, LetterheadLine
from legal_format_engine.letterhead.manager import LetterheadManager


class TestLetterheadLine:
    def test_defaults(self):
        ll = LetterheadLine(text="Test")
        assert ll.bold is False
        assert ll.italic is False
        assert ll.font_size_pt == 10.0
        assert ll.alignment == "left"

    def test_bold_centered(self):
        ll = LetterheadLine(text="Firm Name", bold=True, alignment="center", font_size_pt=14)
        assert ll.bold is True
        assert ll.alignment == "center"
        assert ll.font_size_pt == 14


class TestLetterhead:
    def test_auto_id(self):
        lh = Letterhead(name="Test")
        assert lh.id is not None
        assert len(lh.id) > 0

    def test_unique_ids(self):
        lh1 = Letterhead(name="A")
        lh2 = Letterhead(name="B")
        assert lh1.id != lh2.id

    def test_with_lines(self):
        lh = Letterhead(
            name="Smith LLP",
            lines=[
                LetterheadLine(text="Smith LLP", bold=True),
                LetterheadLine(text="123 Main St"),
            ],
        )
        assert len(lh.lines) == 2

    def test_optional_fields(self):
        lh = Letterhead(name="X")
        assert lh.logo_path is None
        assert lh.created_at is None
        assert lh.updated_at is None

    def test_serialization(self):
        lh = Letterhead(
            name="Test",
            lines=[LetterheadLine(text="Line 1")],
        )
        data = lh.model_dump()
        assert data["name"] == "Test"
        assert len(data["lines"]) == 1

    def test_json_roundtrip(self):
        lh = Letterhead(
            name="Roundtrip",
            lines=[LetterheadLine(text="A", bold=True, alignment="center")],
        )
        json_str = lh.model_dump_json()
        restored = Letterhead(**json.loads(json_str))
        assert restored.name == "Roundtrip"
        assert restored.lines[0].bold is True


class TestLetterheadManager:
    @pytest.fixture()
    def manager(self, tmp_dir):
        return LetterheadManager(storage_dir=tmp_dir / "letterheads")

    def test_save_and_get(self, manager):
        lh = Letterhead(name="Test Firm", lines=[LetterheadLine(text="Test")])
        saved = manager.save(lh)
        assert saved.created_at is not None
        assert saved.updated_at is not None

        retrieved = manager.get(lh.id)
        assert retrieved is not None
        assert retrieved.name == "Test Firm"

    def test_get_nonexistent(self, manager):
        assert manager.get("nonexistent") is None

    def test_list_all_empty(self, manager):
        result = manager.list_all()
        assert result == []

    def test_list_all_with_items(self, manager):
        manager.save(Letterhead(name="A"))
        manager.save(Letterhead(name="B"))
        result = manager.list_all()
        assert len(result) == 2

    def test_delete(self, manager):
        lh = Letterhead(name="To Delete")
        manager.save(lh)
        assert manager.delete(lh.id) is True
        assert manager.get(lh.id) is None

    def test_delete_nonexistent(self, manager):
        assert manager.delete("fake-id") is False

    def test_update_existing(self, manager):
        lh = Letterhead(name="Original")
        manager.save(lh)
        lh.name = "Updated"
        manager.save(lh)
        retrieved = manager.get(lh.id)
        assert retrieved.name == "Updated"

    def test_to_render_lines(self, manager):
        lh = Letterhead(
            name="Render Test",
            lines=[
                LetterheadLine(text="Firm", bold=True, alignment="center", font_size_pt=14),
                LetterheadLine(text="Address", italic=True),
            ],
        )
        render_lines = manager.to_render_lines(lh)
        assert len(render_lines) == 2
        assert render_lines[0]["text"] == "Firm"
        assert render_lines[0]["bold"] is True
        assert render_lines[0]["alignment"] == "center"
        assert render_lines[0]["font_size_pt"] == 14
        assert render_lines[1]["italic"] is True

    def test_storage_dir_created(self, tmp_dir):
        new_dir = tmp_dir / "new_storage"
        manager = LetterheadManager(storage_dir=new_dir)
        assert new_dir.exists()

    def test_timestamps_set(self, manager):
        lh = Letterhead(name="Timestamps")
        saved = manager.save(lh)
        assert saved.created_at is not None
        assert saved.updated_at is not None

    def test_save_preserves_created_at(self, manager):
        lh = Letterhead(name="Preserve")
        manager.save(lh)
        original_created = lh.created_at
        # Save again
        manager.save(lh)
        assert lh.created_at == original_created
