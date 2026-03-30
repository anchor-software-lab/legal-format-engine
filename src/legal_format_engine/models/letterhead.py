"""Letterhead data model and management.

Supports custom firm/attorney letterheads that are applied to the
top of formatted documents. Users can create, save, load, and delete
letterhead profiles.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field


class LetterheadLine(BaseModel):
    """A single line in the letterhead."""

    text: str
    bold: bool = False
    italic: bool = False
    font_size_pt: float | None = None  # None = use document default
    alignment: str = "center"  # "left", "center", "right"


class Letterhead(BaseModel):
    """A complete letterhead profile."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    name: str  # Display name, e.g. "Anchor Filings" or "My Office"
    lines: list[LetterheadLine] = []
    logo_path: str | None = None  # Path to logo image file (optional)
    logo_width_inches: float = 1.5
    separator_line: bool = True  # Horizontal rule after letterhead
    spacing_after_pt: float = 12.0  # Space between letterhead and caption


# ── Storage ───────────────────────────────────────────────────────────

_DEFAULT_DIR = Path.home() / ".legal-format-engine" / "letterheads"


class LetterheadManager:
    """File-based CRUD for letterhead profiles.

    Each letterhead is stored as a JSON file in the storage directory.
    Logo images are copied into a logos/ subdirectory alongside them.
    """

    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or _DEFAULT_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logos_dir = self.storage_dir / "logos"
        self.logos_dir.mkdir(exist_ok=True)

    def list(self) -> list[Letterhead]:
        """List all saved letterheads."""
        results = []
        for f in sorted(self.storage_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append(Letterhead.model_validate(data))
            except Exception:
                continue
        return results

    def get(self, letterhead_id: str) -> Letterhead | None:
        """Get a letterhead by ID."""
        path = self.storage_dir / f"{letterhead_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Letterhead.model_validate(data)

    def save(self, letterhead: Letterhead, logo_source: Path | None = None) -> Letterhead:
        """Save a letterhead profile. Copies logo if provided."""
        if logo_source and logo_source.exists():
            dest = self.logos_dir / f"{letterhead.id}{logo_source.suffix}"
            shutil.copy2(logo_source, dest)
            letterhead.logo_path = str(dest)

        path = self.storage_dir / f"{letterhead.id}.json"
        path.write_text(letterhead.model_dump_json(indent=2), encoding="utf-8")
        return letterhead

    def delete(self, letterhead_id: str) -> bool:
        """Delete a letterhead and its logo."""
        path = self.storage_dir / f"{letterhead_id}.json"
        if not path.exists():
            return False

        letterhead = self.get(letterhead_id)
        if letterhead and letterhead.logo_path:
            logo = Path(letterhead.logo_path)
            logo.unlink(missing_ok=True)

        path.unlink()
        return True
