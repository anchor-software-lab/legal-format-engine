"""ML Learner - statistical learning with weighted median and outlier rejection."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import statistics

from legal_format_engine.ml.features import FeatureVector


@dataclass
class LearnedPatterns:
    """Patterns learned from multiple documents."""
    font_name: Optional[str] = None
    font_name_confidence: float = 0.0
    font_size_pt: Optional[float] = None
    font_size_confidence: float = 0.0
    margin_top: Optional[float] = None
    margin_bottom: Optional[float] = None
    margin_left: Optional[float] = None
    margin_right: Optional[float] = None
    margin_confidence: float = 0.0
    line_spacing: Optional[float] = None
    first_line_indent: Optional[float] = None
    document_count: int = 0
    jurisdiction: Optional[str] = None


def learn_patterns(vectors: list[FeatureVector]) -> LearnedPatterns:
    """Learn formatting patterns from a collection of feature vectors.

    Uses weighted median for numerical features and weighted voting for categorical.
    Outliers are rejected using IQR method.
    """
    if not vectors:
        return LearnedPatterns()

    patterns = LearnedPatterns(document_count=len(vectors))

    # Font name (weighted voting)
    font_votes: dict[str, float] = {}
    for v in vectors:
        if v.font_name:
            name, weight = v.font_name
            font_votes[name] = font_votes.get(name, 0) + weight
    if font_votes:
        patterns.font_name = max(font_votes, key=font_votes.get)
        total = sum(font_votes.values())
        patterns.font_name_confidence = font_votes[patterns.font_name] / total if total > 0 else 0

    # Numerical features
    patterns.font_size_pt, patterns.font_size_confidence = _weighted_median(
        [(v.font_size[0], v.font_size[1]) for v in vectors if v.font_size]
    )

    patterns.margin_top, mc1 = _weighted_median(
        [(v.margin_top[0], v.margin_top[1]) for v in vectors if v.margin_top]
    )
    patterns.margin_bottom, mc2 = _weighted_median(
        [(v.margin_bottom[0], v.margin_bottom[1]) for v in vectors if v.margin_bottom]
    )
    patterns.margin_left, mc3 = _weighted_median(
        [(v.margin_left[0], v.margin_left[1]) for v in vectors if v.margin_left]
    )
    patterns.margin_right, mc4 = _weighted_median(
        [(v.margin_right[0], v.margin_right[1]) for v in vectors if v.margin_right]
    )
    confidences = [c for c in [mc1, mc2, mc3, mc4] if c > 0]
    patterns.margin_confidence = sum(confidences) / len(confidences) if confidences else 0

    patterns.line_spacing, _ = _weighted_median(
        [(v.line_spacing[0], v.line_spacing[1]) for v in vectors if v.line_spacing]
    )
    patterns.first_line_indent, _ = _weighted_median(
        [(v.first_line_indent[0], v.first_line_indent[1]) for v in vectors if v.first_line_indent]
    )

    if vectors:
        patterns.jurisdiction = vectors[0].jurisdiction

    return patterns


def _weighted_median(
    values_weights: list[tuple[float, float]],
) -> tuple[Optional[float], float]:
    """Compute weighted median with IQR outlier rejection.

    Returns (value, confidence) where confidence is proportion of non-outlier weight.
    """
    if not values_weights:
        return None, 0.0

    # Sort by value
    sorted_vw = sorted(values_weights, key=lambda x: x[0])
    values = [v for v, _ in sorted_vw]

    # IQR outlier rejection
    if len(values) >= 4:
        q1 = values[len(values) // 4]
        q3 = values[3 * len(values) // 4]
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        filtered = [(v, w) for v, w in sorted_vw if lower <= v <= upper]
        if filtered:
            sorted_vw = filtered

    # Weighted median
    total_weight = sum(w for _, w in sorted_vw)
    if total_weight == 0:
        return None, 0.0

    cumulative = 0
    for val, weight in sorted_vw:
        cumulative += weight
        if cumulative >= total_weight / 2:
            return val, min(1.0, total_weight / len(values_weights))

    return sorted_vw[-1][0], min(1.0, total_weight / len(values_weights))
