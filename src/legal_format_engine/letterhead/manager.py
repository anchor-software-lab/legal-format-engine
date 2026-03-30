"""Letterhead storage manager."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import json
from datetime import datetime

from legal_format_engine.letterhead.models import Letterhead, LetterheadLine

DEFAULT_DIR = Path.home() / ".legal-format-engine" / "letterheads"


class LetterheadManager:
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or DEFAULT_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, letterhead: Letterhead) -> Letterhead:
        now = datetime.utcnow().isoformat()
        if not letterhead.created_at:
            letterhead.created_at = now
        letterhead.updated_at = now

        path = self.storage_dir / f"{letterhead.id}.json"
        path.write_text(letterhead.model_dump_json(indent=2))
        return letterhead

    def get(self, letterhead_id: str) -> Optional[Letterhead]:
        path = self.storage_dir / f"{letterhead_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return Letterhead(**data)

    def list_all(self) -> list[Letterhead]:
        results = []
        for f in sorted(self.storage_dir.glob("*.json")):
            data = json.loads(f.read_text())
            results.append(Letterhead(**data))
        return results

    def delete(self, letterhead_id: str) -> bool:
        path = self.storage_dir / f"{letterhead_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def to_render_lines(self, letterhead: Letterhead) -> list[dict]:
        """Convert a Letterhead to the format expected by the DOCX renderer."""
        return [
            {
                "text": line.text,
                "bold": line.bold,
                "italic": line.italic,
                "font_size_pt": line.font_size_pt,
                "alignment": line.alignment,
            }
            for line in letterhead.lines
        ]
