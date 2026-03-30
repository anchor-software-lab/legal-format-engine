"""Pydantic models for the anchor-ml-engine.

All data structures used across the pipeline are defined here as Pydantic
BaseModel classes so they can be serialized, validated, and shared cleanly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Normalizer models
# ---------------------------------------------------------------------------


class NormalizedFont(BaseModel):
    """Canonical font specification after normalization."""
    family: str  # canonical family name ("Times New Roman", "Arial", etc.)
    size_pt: float  # snapped to standard size
    weight: float = 0.0  # proportion of document using this font (0-1)


class NormalizedMargins(BaseModel):
    """Canonical margin specification after normalization."""
    top: float
    bottom: float
    left: float
    right: float
    source_quality: str = "exact"  # "exact" (DOCX) or "estimated" (PDF)


class NormalizedHeading(BaseModel):
    """Canonical heading style after normalization."""
    level: int  # 1-4
    case_style: str  # "upper", "title", "sentence"
    alignment: str  # "center", "left"
    bold: bool
    font_size_pt: float | None = None
    numbering: str | None = None  # "roman", "alpha_upper", "alpha_lower", "arabic"
    sample_count: int = 0  # how many headings of this type were found


class NormalizedSection(BaseModel):
    """Canonical section identification."""
    id: str  # canonical section ID (e.g., "argument", "table_of_contents")
    original_name: str  # how it appeared in the source document
    order: int  # position in document (0-indexed)


class NormalizedParagraphStyle(BaseModel):
    """Canonical paragraph formatting for a specific context."""
    context: str  # "body", "block_quote", "footnote"
    font_family: str
    font_size_pt: float
    line_spacing: float
    first_line_indent: float = 0.0  # inches
    left_indent: float = 0.0  # inches
    alignment: str = "left"  # "left", "center", "right", "justify"
    space_before_pt: float = 0.0
    space_after_pt: float = 0.0


class NormalizedDocument(BaseModel):
    """Format-agnostic canonical representation of a document.

    This is what the ML layer sees. All format-specific quirks have been
    stripped. A DOCX and its print-to-PDF produce the same NormalizedDocument.
    """
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    source_filename: str
    source_format: str  # "docx", "pdf", "doc", "html"
    normalized_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Metadata (user-tagged or auto-detected)
    # Domain-agnostic: use category/subcategory instead of jurisdiction/court_level
    category: str | None = None
    subcategory: str | None = None
    document_type: str | None = None

    # Attribution: who authored this document
    author: str | None = None  # individual name
    organization: str | None = None  # organization name

    # Quality score: how confident are we in the extracted formatting?
    # 1.0 = DOCX with explicit styles, 0.5 = PDF with estimated values
    extraction_confidence: float = 1.0

    # Core formatting
    primary_font: NormalizedFont | None = None
    secondary_fonts: list[NormalizedFont] = []
    margins: NormalizedMargins | None = None
    line_spacing: float | None = None  # snapped to standard value

    # Heading styles (one per detected level)
    heading_styles: list[NormalizedHeading] = []

    # Section structure
    sections: list[NormalizedSection] = []

    # Paragraph styles by context
    paragraph_styles: list[NormalizedParagraphStyle] = []

    # Indentation
    body_first_line_indent: float | None = None  # inches, snapped
    block_quote_indent: float | None = None  # inches, snapped

    # Document stats (for weighting)
    total_pages: int | None = None
    total_words: int | None = None
    total_paragraphs: int = 0
    total_headings: int = 0


# ---------------------------------------------------------------------------
# Feature extraction models
# ---------------------------------------------------------------------------


class FeatureValue(BaseModel):
    """A single feature with its value and confidence weight."""
    name: str
    value: float | str  # numerical or categorical
    weight: float = 1.0  # 0-1, reflects extraction confidence
    source: str = ""  # which document this came from


class HeadingFeatures(BaseModel):
    """Features for a single heading level."""
    level: int
    case_style: FeatureValue | None = None  # categorical: "upper", "title", "sentence"
    alignment: FeatureValue | None = None  # categorical: "center", "left"
    bold: FeatureValue | None = None  # 1.0 or 0.0
    font_size_pt: FeatureValue | None = None
    numbering: FeatureValue | None = None  # categorical or None


class DocumentFeatures(BaseModel):
    """Complete feature vector extracted from a NormalizedDocument."""
    document_id: str
    source_filename: str
    category: str | None = None
    subcategory: str | None = None
    document_type: str | None = None
    extraction_confidence: float = 1.0

    # Typography features
    font_family: FeatureValue | None = None
    font_size_pt: FeatureValue | None = None
    line_spacing: FeatureValue | None = None

    # Layout features
    margin_top: FeatureValue | None = None
    margin_bottom: FeatureValue | None = None
    margin_left: FeatureValue | None = None
    margin_right: FeatureValue | None = None
    body_indent: FeatureValue | None = None
    block_quote_indent: FeatureValue | None = None

    # Heading features (per level)
    heading_features: dict[int, HeadingFeatures] = {}

    # Section order features
    section_ids: list[str] = []
    section_count: int = 0


# ---------------------------------------------------------------------------
# Learner output models
# ---------------------------------------------------------------------------


class LearnedValue(BaseModel):
    """A single learned formatting value with confidence."""
    value: float | str
    confidence: float  # 0-1
    sample_count: int  # how many documents contributed
    agreement: float  # proportion of documents that agree (after outlier rejection)
    source_weights: float = 0.0  # sum of weights from contributing documents


class LearnedHeadingStyle(BaseModel):
    """Learned heading style for a specific level."""
    level: int
    case_style: LearnedValue | None = None
    alignment: LearnedValue | None = None
    bold: LearnedValue | None = None
    font_size_pt: LearnedValue | None = None
    numbering: LearnedValue | None = None


class LearnedSectionOrder(BaseModel):
    """Learned section presence and ordering."""
    id: str
    frequency: float  # proportion of documents containing this section
    median_order: int  # typical position
    common_names: list[str] = []


class LearnedFormat(BaseModel):
    """Complete learned formatting specification for a category/subcategory/doctype.

    This is the output of the learner. It can be used to:
    1. Generate a suggested ruleset
    2. Override defaults in the formatting engine
    3. Validate that a document matches the expected format
    """
    category: str | None = None
    subcategory: str | None = None
    document_type: str | None = None

    # Sample info
    document_count: int = 0
    total_confidence_weight: float = 0.0

    # Typography
    font_family: LearnedValue | None = None
    font_size_pt: LearnedValue | None = None
    line_spacing: LearnedValue | None = None

    # Layout
    margin_top: LearnedValue | None = None
    margin_bottom: LearnedValue | None = None
    margin_left: LearnedValue | None = None
    margin_right: LearnedValue | None = None
    body_indent: LearnedValue | None = None
    block_quote_indent: LearnedValue | None = None

    # Headings
    heading_styles: list[LearnedHeadingStyle] = []

    # Sections
    section_order: list[LearnedSectionOrder] = []

    # Overall confidence: min of 3 docs, diminishing returns after 10
    @property
    def overall_confidence(self) -> float:
        """Overall confidence in the learned format.

        Combines sample size with agreement levels.
        """
        if self.document_count == 0:
            return 0.0

        # Sample size factor: ramps from 0 to 1 as docs go from 0 to 10
        size_factor = min(1.0, self.document_count / 10.0)

        # Agreement factor: average confidence across all learned values
        confidences = []
        for attr in ("font_family", "font_size_pt", "line_spacing",
                     "margin_top", "margin_bottom", "margin_left", "margin_right"):
            val = getattr(self, attr)
            if val is not None:
                confidences.append(val.confidence)

        agreement_factor = sum(confidences) / len(confidences) if confidences else 0.0

        return round(size_factor * agreement_factor, 3)


# ---------------------------------------------------------------------------
# Synthesizer models
# ---------------------------------------------------------------------------


class FormatRecommendation(BaseModel):
    """A specific recommendation from the ML to change a formatting rule."""
    field: str
    current_value: object = None
    suggested_value: object = None
    confidence: float = 0.0
    reason: str = ""


# ---------------------------------------------------------------------------
# Attribution models
# ---------------------------------------------------------------------------


class DetectedAttribution(BaseModel):
    """Auto-detected authorship information."""
    author: str | None = None
    organization: str | None = None
    identifier: str | None = None  # e.g., bar number, employee ID
    author_confidence: float = 0.0
    organization_confidence: float = 0.0
    sources: list[str] = []


# ---------------------------------------------------------------------------
# Style profile models
# ---------------------------------------------------------------------------


class StylePreference(BaseModel):
    """A single discretionary formatting preference."""
    field: str  # e.g., "body_first_line_indent", "heading_2_numbering"
    value: object  # the preferred value
    sample_count: int = 0  # how many documents established this preference
    consistency: float = 0.0  # 0-1, how consistently the author uses this value


class StyleProfile(BaseModel):
    """A collection of formatting preferences for an author or organization.

    Profiles only contain discretionary choices -- formatting decisions
    where the rules are silent.
    """
    profile_type: str  # "author" or "organization"
    name: str  # author name or organization name
    document_count: int = 0
    categories: list[str] = []
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    preferences: list[StylePreference] = []

    def get(self, field_name: str) -> StylePreference | None:
        """Look up a preference by field name."""
        for p in self.preferences:
            if p.field == field_name:
                return p
        return None

    def to_dict(self) -> dict:
        return {
            "profile_type": self.profile_type,
            "name": self.name,
            "document_count": self.document_count,
            "categories": self.categories,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "preferences": [
                {
                    "field": p.field,
                    "value": p.value,
                    "sample_count": p.sample_count,
                    "consistency": p.consistency,
                }
                for p in self.preferences
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> StyleProfile:
        profile = cls(
            profile_type=data["profile_type"],
            name=data["name"],
            document_count=data.get("document_count", 0),
            categories=data.get("categories", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
        for p in data.get("preferences", []):
            profile.preferences.append(StylePreference(
                field=p["field"],
                value=p["value"],
                sample_count=p.get("sample_count", 0),
                consistency=p.get("consistency", 0.0),
            ))
        return profile


# ---------------------------------------------------------------------------
# Pattern store models
# ---------------------------------------------------------------------------


class DocumentAnalysis(BaseModel):
    """Result of analyzing a document for formatting patterns.

    Domain-agnostic equivalent of the original BriefAnalysis.
    """
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    source_filename: str = ""
    category: str | None = None
    subcategory: str | None = None
    analyzed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    font_name: str | None = None
    font_size_pt: float | None = None
    margin_top: float | None = None
    margin_bottom: float | None = None
    margin_left: float | None = None
    margin_right: float | None = None
    line_spacing: float | None = None
    paragraph_indent_inches: float | None = None
    block_quote_indent_inches: float | None = None

    heading_patterns: list[dict] = []
    section_patterns: list[dict] = []


class AggregatePatterns(BaseModel):
    """Aggregated patterns across multiple document analyses."""
    category: str | None = None
    subcategory: str | None = None
    document_count: int = 0
    font_name: str | None = None
    font_size_pt: float | None = None
    margin_top: float | None = None
    margin_bottom: float | None = None
    margin_left: float | None = None
    margin_right: float | None = None
    line_spacing: float | None = None
    paragraph_indent_inches: float | None = None
    heading_patterns: list[dict] = []
    section_patterns: list[dict] = []
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Rule hierarchy models
# ---------------------------------------------------------------------------


class FormattingDecision(BaseModel):
    """A single formatting decision with full provenance."""
    field: str  # e.g., "page_format.font_size_pt"
    value: object  # the decided value
    source: str  # "rule", "ml_learned", "style_profile", "default"
    confidence: float = 1.0  # 1.0 for rules, varies for ML/style
    explanation: str = ""


class ResolvedFormat(BaseModel):
    """Complete formatting specification with provenance for every decision.

    Every formatting field has a value and a clear source explaining
    where it came from. This is what the engine uses to format documents.
    """
    category: str = ""
    subcategory: str = ""
    document_type: str = ""

    decisions: list[FormattingDecision] = []

    # Convenience: count by source
    @property
    def rule_count(self) -> int:
        return sum(1 for d in self.decisions if d.source == "rule")

    @property
    def ml_count(self) -> int:
        return sum(1 for d in self.decisions if d.source == "ml_learned")

    @property
    def style_count(self) -> int:
        return sum(1 for d in self.decisions if d.source == "style_profile")

    @property
    def default_count(self) -> int:
        return sum(1 for d in self.decisions if d.source == "default")

    def get(self, field_name: str) -> FormattingDecision | None:
        for d in self.decisions:
            if d.field == field_name:
                return d
        return None

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "subcategory": self.subcategory,
            "document_type": self.document_type,
            "decisions": [
                {
                    "field": d.field,
                    "value": d.value,
                    "source": d.source,
                    "confidence": d.confidence,
                    "explanation": d.explanation,
                }
                for d in self.decisions
            ],
            "summary": {
                "total": len(self.decisions),
                "from_rules": self.rule_count,
                "from_ml": self.ml_count,
                "from_style": self.style_count,
                "from_defaults": self.default_count,
            },
        }
