"""Pattern storage for learned brief formatting patterns.

Stores and retrieves BriefAnalysis records as JSON files in
~/.legal-format-engine/learned_patterns/. Provides aggregation
across multiple briefs for a given jurisdiction.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path

from legal_format_engine.models.patterns import (
    AggregatePatterns,
    BriefAnalysis,
    FontPattern,
    HeadingPattern,
    MarginPattern,
    SectionPattern,
)

logger = logging.getLogger(__name__)

_DEFAULT_STORE_DIR = Path.home() / ".legal-format-engine" / "learned_patterns"


class PatternStore:
    """File-based storage for brief analysis records.

    Each analyzed brief is stored as a JSON file named by its ID.
    """

    def __init__(self, store_dir: str | Path | None = None) -> None:
        self._dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def store_dir(self) -> Path:
        return self._dir

    def save(self, analysis: BriefAnalysis) -> Path:
        """Save a BriefAnalysis record to disk.

        Returns the path to the saved JSON file.
        """
        file_path = self._dir / f"{analysis.id}.json"
        file_path.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Saved analysis %s for '%s'", analysis.id, analysis.source_filename)
        return file_path

    def load(self, analysis_id: str) -> BriefAnalysis | None:
        """Load a single analysis by ID. Returns None if not found."""
        file_path = self._dir / f"{analysis_id}.json"
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return BriefAnalysis.model_validate(data)
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

    def list_all(self) -> list[BriefAnalysis]:
        """List all stored analyses, sorted by analyzed_at descending."""
        analyses: list[BriefAnalysis] = []
        for file_path in self._dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                analyses.append(BriefAnalysis.model_validate(data))
            except Exception:
                logger.warning("Skipping corrupt analysis file: %s", file_path.name)
                continue
        analyses.sort(key=lambda a: a.analyzed_at, reverse=True)
        return analyses

    def list_by_jurisdiction(self, jurisdiction: str) -> list[BriefAnalysis]:
        """List all analyses for a specific jurisdiction."""
        return [
            a for a in self.list_all()
            if a.jurisdiction and a.jurisdiction.lower() == jurisdiction.lower()
        ]

    def aggregate(
        self,
        jurisdiction: str,
        court_level: str | None = None,
    ) -> AggregatePatterns:
        """Compute aggregate patterns across all briefs for a jurisdiction.

        Uses voting and averaging to determine the most common patterns.
        Confidence scores reflect how many briefs agree on each pattern.

        Args:
            jurisdiction: The jurisdiction to aggregate for.
            court_level: Optional court level filter.

        Returns:
            An AggregatePatterns with consensus patterns and confidence scores.
        """
        analyses = self.list_by_jurisdiction(jurisdiction)
        if court_level:
            analyses = [
                a for a in analyses
                if a.court_level and a.court_level.lower() == court_level.lower()
            ]

        brief_count = len(analyses)
        if brief_count == 0:
            return AggregatePatterns(
                jurisdiction=jurisdiction,
                court_level=court_level,
                brief_count=0,
            )

        font = _aggregate_fonts(analyses)
        margins = _aggregate_margins(analyses)
        line_spacing = _aggregate_line_spacing(analyses)
        headings = _aggregate_headings(analyses)
        sections = _aggregate_sections(analyses)
        paragraph_indent = _aggregate_indent(analyses)

        return AggregatePatterns(
            jurisdiction=jurisdiction,
            court_level=court_level,
            brief_count=brief_count,
            font=font,
            margins=margins,
            line_spacing=line_spacing,
            headings=headings,
            sections=sections,
            paragraph_indent_inches=paragraph_indent,
        )


def _aggregate_fonts(analyses: list[BriefAnalysis]) -> FontPattern | None:
    """Find most common font name and size across analyses."""
    font_votes: Counter[str] = Counter()
    size_votes: Counter[float] = Counter()

    for a in analyses:
        if a.font_patterns:
            # Primary font is first in list
            font_votes[a.font_patterns[0].font_name] += 1
            size_votes[a.font_patterns[0].font_size_pt] += 1

    if not font_votes:
        return None

    best_font, font_count = font_votes.most_common(1)[0]
    best_size, size_count = size_votes.most_common(1)[0]
    n = len(analyses)

    return FontPattern(
        font_name=best_font,
        font_size_pt=best_size,
        confidence=round(min(font_count, size_count) / n, 2),
    )


def _aggregate_margins(analyses: list[BriefAnalysis]) -> MarginPattern | None:
    """Average margins across analyses."""
    margins = [a.margin_pattern for a in analyses if a.margin_pattern]
    if not margins:
        return None

    n = len(margins)
    avg_top = sum(m.top for m in margins) / n
    avg_bottom = sum(m.bottom for m in margins) / n
    avg_left = sum(m.left for m in margins) / n
    avg_right = sum(m.right for m in margins) / n

    # Confidence: how tightly clustered are the values?
    # If all margins are within 0.1 inch of the average, high confidence.
    spread = max(
        max(m.top for m in margins) - min(m.top for m in margins),
        max(m.bottom for m in margins) - min(m.bottom for m in margins),
        max(m.left for m in margins) - min(m.left for m in margins),
        max(m.right for m in margins) - min(m.right for m in margins),
    )
    # Confidence inversely proportional to spread, capped at 1.0
    confidence = max(0.0, min(1.0, 1.0 - spread / 1.0))

    return MarginPattern(
        top=round(avg_top, 2),
        bottom=round(avg_bottom, 2),
        left=round(avg_left, 2),
        right=round(avg_right, 2),
        confidence=round(confidence, 2),
    )


def _aggregate_line_spacing(analyses: list[BriefAnalysis]) -> float | None:
    """Most common line spacing value."""
    spacings = [a.line_spacing for a in analyses if a.line_spacing is not None]
    if not spacings:
        return None
    # Round to nearest 0.5 and vote
    rounded = [round(s * 2) / 2 for s in spacings]
    counter = Counter(rounded)
    best, _ = counter.most_common(1)[0]
    return best


def _aggregate_headings(analyses: list[BriefAnalysis]) -> list[HeadingPattern]:
    """Aggregate heading patterns by level."""
    level_data: dict[int, list[HeadingPattern]] = {}

    for a in analyses:
        for hp in a.heading_patterns:
            level_data.setdefault(hp.level, []).append(hp)

    result = []
    n = len(analyses)

    for level, patterns in sorted(level_data.items()):
        # Vote on case style
        case_votes = Counter(p.case_style for p in patterns)
        best_case, _ = case_votes.most_common(1)[0]

        # Vote on alignment
        align_votes = Counter(p.alignment for p in patterns)
        best_align, _ = align_votes.most_common(1)[0]

        # Vote on bold
        bold_count = sum(1 for p in patterns if p.bold)
        best_bold = bold_count > len(patterns) / 2

        # Vote on numbering
        numbering_votes = Counter(
            p.numbering for p in patterns if p.numbering
        )
        best_numbering = None
        if numbering_votes:
            best_numbering, _ = numbering_votes.most_common(1)[0]

        # Average font size
        sizes = [p.font_size_pt for p in patterns if p.font_size_pt is not None]
        best_size = round(sum(sizes) / len(sizes), 1) if sizes else None

        # Confidence = fraction of analyses that have this heading level
        briefs_with_level = len(set(id(p) for p in patterns))  # rough count
        confidence = round(len(patterns) / max(n, 1), 2)
        confidence = min(confidence, 1.0)

        result.append(HeadingPattern(
            level=level,
            case_style=best_case,
            alignment=best_align,
            bold=best_bold,
            font_size_pt=best_size,
            numbering=best_numbering,
            confidence=confidence,
        ))

    return result


def _aggregate_sections(analyses: list[BriefAnalysis]) -> list[SectionPattern]:
    """Aggregate section patterns: frequency, ordering, name variants."""
    section_data: dict[str, dict] = {}
    n = len(analyses)

    for a in analyses:
        for sp in a.section_patterns:
            if sp.id not in section_data:
                section_data[sp.id] = {
                    "names": [],
                    "orders": [],
                    "count": 0,
                }
            section_data[sp.id]["names"].extend(sp.common_names)
            section_data[sp.id]["orders"].append(sp.typical_order)
            section_data[sp.id]["count"] += 1

    result = []
    for section_id, data in section_data.items():
        # Deduplicate names preserving order
        seen: set[str] = set()
        unique_names: list[str] = []
        for name in data["names"]:
            name_lower = name.lower()
            if name_lower not in seen:
                seen.add(name_lower)
                unique_names.append(name)

        avg_order = round(sum(data["orders"]) / len(data["orders"]))
        frequency = round(data["count"] / n, 2)

        result.append(SectionPattern(
            id=section_id,
            common_names=unique_names,
            frequency=frequency,
            typical_order=avg_order,
        ))

    # Sort by typical order
    result.sort(key=lambda s: s.typical_order)
    return result


def _aggregate_indent(analyses: list[BriefAnalysis]) -> float | None:
    """Average paragraph indent across analyses."""
    indents = [
        a.paragraph_indent_inches
        for a in analyses
        if a.paragraph_indent_inches is not None
    ]
    if not indents:
        return None
    return round(sum(indents) / len(indents), 2)
