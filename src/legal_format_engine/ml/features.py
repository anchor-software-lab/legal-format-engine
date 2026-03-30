"""ML Feature Extractor - converts normalized documents into weighted feature vectors."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from legal_format_engine.ml.normalizer import NormalizedDocument


@dataclass
class FeatureVector:
    """Weighted feature vector for ML learning."""
    # Numerical features (value, weight)
    font_size: Optional[tuple[float, float]] = None
    margin_top: Optional[tuple[float, float]] = None
    margin_bottom: Optional[tuple[float, float]] = None
    margin_left: Optional[tuple[float, float]] = None
    margin_right: Optional[tuple[float, float]] = None
    line_spacing: Optional[tuple[float, float]] = None
    first_line_indent: Optional[tuple[float, float]] = None

    # Categorical features (value, weight)
    font_name: Optional[tuple[str, float]] = None

    # Complex features
    heading_styles: list[dict] = field(default_factory=list)
    section_names: list[str] = field(default_factory=list)

    # Metadata
    source_format: str = "unknown"
    confidence: float = 1.0
    author: Optional[str] = None
    firm: Optional[str] = None
    jurisdiction: Optional[str] = None


def extract_features(doc: NormalizedDocument) -> FeatureVector:
    """Extract weighted features from a normalized document.

    PDF features get lower weight (0.6) than DOCX (1.0).
    """
    w = doc.confidence  # Base weight from format confidence

    fv = FeatureVector(
        source_format=doc.source_format,
        confidence=doc.confidence,
        author=doc.author,
        firm=doc.firm,
        jurisdiction=doc.jurisdiction,
    )

    if doc.font_size_pt is not None:
        fv.font_size = (doc.font_size_pt, w)

    if doc.margin_top is not None:
        fv.margin_top = (doc.margin_top, w)
    if doc.margin_bottom is not None:
        fv.margin_bottom = (doc.margin_bottom, w)
    if doc.margin_left is not None:
        fv.margin_left = (doc.margin_left, w)
    if doc.margin_right is not None:
        fv.margin_right = (doc.margin_right, w)

    if doc.line_spacing is not None:
        fv.line_spacing = (doc.line_spacing, w)

    if doc.first_line_indent is not None:
        fv.first_line_indent = (doc.first_line_indent, w)

    if doc.font_name:
        fv.font_name = (doc.font_name, w)

    fv.heading_styles = doc.heading_styles
    fv.section_names = doc.section_names

    return fv
