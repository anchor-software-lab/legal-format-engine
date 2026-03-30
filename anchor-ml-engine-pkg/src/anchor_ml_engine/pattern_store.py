"""Pattern storage for learned document formatting patterns.

Stores and retrieves DocumentAnalysis records as JSON files.
Provides aggregation across multiple documents for a given category.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path

from anchor_ml_engine.models import (
    AggregatePatterns,
    DocumentAnalysis,
)

logger = logging.getLogger(__name__)

_DEFAULT_STORE_DIR = Path.home() / ".anchor-ml-engine" / "learned_patterns"


class PatternStore:
    """File-based storage for document analysis records.

    Each analyzed document is stored as a JSON file named by its ID.
    """

    def __init__(self, store_dir: str | Path | None = None) -> None:
        self._dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def store_dir(self) -> Path:
        return self._dir

    def save(self, analysis: DocumentAnalysis) -> Path:
        """Save a DocumentAnalysis record to disk.

        Returns the path to the saved JSON file.
        """
        file_path = self._dir / f"{analysis.id}.json"
        file_path.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Saved analysis %s for '%s'", analysis.id, analysis.source_filename)
        return file_path

    def load(self, analysis_id: str) -> DocumentAnalysis | None:
        """Load a single analysis by ID. Returns None if not found."""
        file_path = self._dir / f"{analysis_id}.json"
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return DocumentAnalysis.model_validate(data)
        except Exception:
            logger.exception("Failed to load analysis %s", analysis_id)
            return None

    def delete(self, analysis_id: str) -> bool:
        """Delete a single analysis by ID. Returns True if deleted."""
        file_path = self._dir / f"{analysis_id}.json"
        if file_path.exists():
            file_path.unlink()
            logger.info("Deleted analysis %s", analysis_id)
            return True
        return False

    def list_all(self) -> list[DocumentAnalysis]:
        """List all stored analyses, sorted by analyzed_at descending."""
        analyses: list[DocumentAnalysis] = []
        for file_path in self._dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                analyses.append(DocumentAnalysis.model_validate(data))
            except Exception:
                logger.warning("Skipping corrupt analysis file: %s", file_path.name)
                continue
        analyses.sort(key=lambda a: a.analyzed_at, reverse=True)
        return analyses

    def list_by_category(self, category: str) -> list[DocumentAnalysis]:
        """List all analyses for a specific category."""
        return [
            a for a in self.list_all()
            if a.category and a.category.lower() == category.lower()
        ]

    def aggregate(
        self,
        category: str,
        subcategory: str | None = None,
    ) -> AggregatePatterns:
        """Compute aggregate patterns across all documents for a category.

        Uses voting and averaging to determine the most common patterns.
        Confidence scores reflect how many documents agree on each pattern.

        Args:
            category: The category to aggregate for.
            subcategory: Optional subcategory filter.

        Returns:
            An AggregatePatterns with consensus patterns and confidence scores.
        """
        analyses = self.list_by_category(category)
        if subcategory:
            analyses = [
                a for a in analyses
                if a.subcategory and a.subcategory.lower() == subcategory.lower()
            ]

        doc_count = len(analyses)
        if doc_count == 0:
            return AggregatePatterns(
                category=category,
                subcategory=subcategory,
                document_count=0,
            )

        font = _aggregate_fonts(analyses)
        margins = _aggregate_margins(analyses)
        line_spacing = _aggregate_line_spacing(analyses)
        paragraph_indent = _aggregate_indent(analyses)

        return AggregatePatterns(
            category=category,
            subcategory=subcategory,
            document_count=doc_count,
            font_name=font[0] if font else None,
            font_size_pt=font[1] if font else None,
            margin_top=margins.get("top") if margins else None,
            margin_bottom=margins.get("bottom") if margins else None,
            margin_left=margins.get("left") if margins else None,
            margin_right=margins.get("right") if margins else None,
            line_spacing=line_spacing,
            paragraph_indent_inches=paragraph_indent,
        )


def _aggregate_fonts(analyses: list[DocumentAnalysis]) -> tuple[str, float] | None:
    """Find most common font name and size across analyses."""
    font_votes: Counter[str] = Counter()
    size_votes: Counter[float] = Counter()

    for a in analyses:
        if a.font_name:
            font_votes[a.font_name] += 1
        if a.font_size_pt:
            size_votes[a.font_size_pt] += 1

    if not font_votes:
        return None

    best_font, _ = font_votes.most_common(1)[0]
    best_size = size_votes.most_common(1)[0][0] if size_votes else 12.0

    return (best_font, best_size)


def _aggregate_margins(analyses: list[DocumentAnalysis]) -> dict | None:
    """Average margins across analyses."""
    tops = [a.margin_top for a in analyses if a.margin_top is not None]
    bottoms = [a.margin_bottom for a in analyses if a.margin_bottom is not None]
    lefts = [a.margin_left for a in analyses if a.margin_left is not None]
    rights = [a.margin_right for a in analyses if a.margin_right is not None]

    if not tops:
        return None

    return {
        "top": round(sum(tops) / len(tops), 2),
        "bottom": round(sum(bottoms) / len(bottoms), 2) if bottoms else None,
        "left": round(sum(lefts) / len(lefts), 2) if lefts else None,
        "right": round(sum(rights) / len(rights), 2) if rights else None,
    }


def _aggregate_line_spacing(analyses: list[DocumentAnalysis]) -> float | None:
    """Most common line spacing value."""
    spacings = [a.line_spacing for a in analyses if a.line_spacing is not None]
    if not spacings:
        return None
    # Round to nearest 0.5 and vote
    rounded = [round(s * 2) / 2 for s in spacings]
    counter = Counter(rounded)
    best, _ = counter.most_common(1)[0]
    return best


def _aggregate_indent(analyses: list[DocumentAnalysis]) -> float | None:
    """Average paragraph indent across analyses."""
    indents = [
        a.paragraph_indent_inches
        for a in analyses
        if a.paragraph_indent_inches is not None
    ]
    if not indents:
        return None
    return round(sum(indents) / len(indents), 2)
