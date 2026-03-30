"""Statistical pattern learner with outlier rejection.

This is the core ML engine. It takes feature vectors from multiple documents
and learns consensus formatting patterns, weighted by extraction confidence.

The approach is deliberately NOT neural-network based. Document formatting is
often deterministic -- organizations have rules. The "learning" is about
discovering what those rules actually look like in practice, by observing
many real documents.

Algorithm:
1. Collect weighted feature vectors from documents matching a filter
2. For numerical features (font size, margins): weighted median with IQR outlier rejection
3. For categorical features (font family, case style): weighted voting
4. For structural features (sections): frequency analysis with ordering consensus
5. Confidence scores derived from agreement level and sample size

Outlier rejection is critical: one document with 8pt font or 3" margins shouldn't
pull the learned model away from the real standard. We use the IQR method
(values outside 1.5 * IQR from Q1/Q3 are rejected).
"""

from __future__ import annotations

import math
from collections import Counter

from anchor_ml_engine.models import (
    DocumentFeatures,
    FeatureValue,
    LearnedFormat,
    LearnedHeadingStyle,
    LearnedSectionOrder,
    LearnedValue,
)


class FormatLearner:
    """Learns formatting patterns from document feature vectors.

    Usage:
        learner = FormatLearner()
        learner.add(features1)
        learner.add(features2)
        learner.add(features3)
        result = learner.learn()
    """

    def __init__(self) -> None:
        self._features: list[DocumentFeatures] = []

    def add(self, features: DocumentFeatures) -> None:
        """Add a document's features to the learning set."""
        self._features.append(features)

    def add_all(self, features_list: list[DocumentFeatures]) -> None:
        """Add multiple documents' features."""
        self._features.extend(features_list)

    @property
    def count(self) -> int:
        return len(self._features)

    def learn(self) -> LearnedFormat:
        """Run the learning algorithm and return a LearnedFormat.

        Requires at least 1 document. More documents = higher confidence.
        """
        if not self._features:
            return LearnedFormat()

        result = LearnedFormat(
            document_count=len(self._features),
        )

        # Grab metadata from first document (should all match for a filtered set)
        result.category = self._features[0].category
        result.subcategory = self._features[0].subcategory
        result.document_type = self._features[0].document_type
        result.total_confidence_weight = sum(
            f.extraction_confidence for f in self._features
        )

        # Learn typography
        result.font_family = self._learn_categorical("font_family")
        result.font_size_pt = self._learn_numerical("font_size_pt")
        result.line_spacing = self._learn_numerical("line_spacing")

        # Learn layout
        result.margin_top = self._learn_numerical("margin_top")
        result.margin_bottom = self._learn_numerical("margin_bottom")
        result.margin_left = self._learn_numerical("margin_left")
        result.margin_right = self._learn_numerical("margin_right")
        result.body_indent = self._learn_numerical("body_indent")
        result.block_quote_indent = self._learn_numerical("block_quote_indent")

        # Learn heading styles
        result.heading_styles = self._learn_headings()

        # Learn section order
        result.section_order = self._learn_sections()

        return result

    def _learn_numerical(self, attr_name: str) -> LearnedValue | None:
        """Learn a numerical feature using weighted median with IQR outlier rejection."""
        values: list[tuple[float, float]] = []  # (value, weight)

        for f in self._features:
            fv: FeatureValue | None = getattr(f, attr_name, None)
            if fv is not None and isinstance(fv.value, (int, float)):
                values.append((float(fv.value), fv.weight))

        if not values:
            return None

        # Sort by value for median/IQR computation
        values.sort(key=lambda x: x[0])
        raw_values = [v[0] for v in values]

        # IQR outlier rejection (only if we have enough samples)
        if len(raw_values) >= 4:
            q1 = _percentile(raw_values, 25)
            q3 = _percentile(raw_values, 75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            values = [(v, w) for v, w in values if lower <= v <= upper]

        if not values:
            return None

        # Weighted median
        result_value = _weighted_median(values)

        # Agreement: proportion of values that are close to the median
        total_weight = sum(w for _, w in values)
        agreeing_weight = sum(
            w for v, w in values if abs(v - result_value) < 0.3
        )
        agreement = agreeing_weight / total_weight if total_weight > 0 else 0.0

        # Confidence combines agreement and sample size
        size_factor = min(1.0, len(values) / 5.0)
        confidence = round(agreement * size_factor, 3)

        return LearnedValue(
            value=round(result_value, 2),
            confidence=confidence,
            sample_count=len(values),
            agreement=round(agreement, 3),
            source_weights=round(total_weight, 3),
        )

    def _learn_categorical(self, attr_name: str) -> LearnedValue | None:
        """Learn a categorical feature using weighted voting."""
        votes: list[tuple[str, float]] = []  # (value, weight)

        for f in self._features:
            fv: FeatureValue | None = getattr(f, attr_name, None)
            if fv is not None and isinstance(fv.value, str):
                votes.append((fv.value, fv.weight))

        if not votes:
            return None

        # Weighted vote counting
        weighted_counts: dict[str, float] = {}
        for value, weight in votes:
            weighted_counts[value] = weighted_counts.get(value, 0) + weight

        total_weight = sum(w for _, w in votes)
        winner = max(weighted_counts, key=weighted_counts.get)
        winner_weight = weighted_counts[winner]

        agreement = winner_weight / total_weight if total_weight > 0 else 0.0
        size_factor = min(1.0, len(votes) / 5.0)
        confidence = round(agreement * size_factor, 3)

        return LearnedValue(
            value=winner,
            confidence=confidence,
            sample_count=len(votes),
            agreement=round(agreement, 3),
            source_weights=round(total_weight, 3),
        )

    def _learn_headings(self) -> list[LearnedHeadingStyle]:
        """Learn heading styles per level."""
        # Collect heading features across all documents, grouped by level
        level_features: dict[int, list[tuple[dict, float]]] = {}

        for f in self._features:
            for level, hf in f.heading_features.items():
                if level not in level_features:
                    level_features[level] = []
                level_features[level].append((
                    {
                        "case_style": hf.case_style,
                        "alignment": hf.alignment,
                        "bold": hf.bold,
                        "font_size_pt": hf.font_size_pt,
                        "numbering": hf.numbering,
                    },
                    f.extraction_confidence,
                ))

        styles = []
        for level in sorted(level_features):
            items = level_features[level]
            style = LearnedHeadingStyle(level=level)

            # Learn each attribute
            style.case_style = _vote_categorical(
                [(d["case_style"], w) for d, w in items if d["case_style"]],
                f"heading_{level}_case",
            )
            style.alignment = _vote_categorical(
                [(d["alignment"], w) for d, w in items if d["alignment"]],
                f"heading_{level}_alignment",
            )
            style.bold = _vote_categorical(
                [(d["bold"], w) for d, w in items if d["bold"]],
                f"heading_{level}_bold",
            )
            style.font_size_pt = _median_numerical(
                [(d["font_size_pt"], w) for d, w in items if d["font_size_pt"]],
                f"heading_{level}_font_size",
            )
            style.numbering = _vote_categorical(
                [(d["numbering"], w) for d, w in items if d["numbering"]],
                f"heading_{level}_numbering",
            )

            styles.append(style)

        return styles

    def _learn_sections(self) -> list[LearnedSectionOrder]:
        """Learn section ordering from documents."""
        # Count section frequency and collect orderings
        section_counts: Counter[str] = Counter()
        section_orders: dict[str, list[int]] = {}

        total_docs = len(self._features)
        for f in self._features:
            for i, sid in enumerate(f.section_ids):
                section_counts[sid] += 1
                section_orders.setdefault(sid, []).append(i)

        result = []
        for sid, count in section_counts.most_common():
            orders = section_orders[sid]
            median_order = int(_percentile(sorted(orders), 50))
            frequency = count / total_docs if total_docs > 0 else 0.0

            result.append(LearnedSectionOrder(
                id=sid,
                frequency=round(frequency, 3),
                median_order=median_order,
            ))

        # Sort by median order
        result.sort(key=lambda s: s.median_order)
        return result


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def _percentile(sorted_values: list[float], pct: float) -> float:
    """Compute a percentile from a sorted list of values."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]

    k = (len(sorted_values) - 1) * pct / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


def _weighted_median(values: list[tuple[float, float]]) -> float:
    """Compute weighted median from (value, weight) pairs."""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0][0]

    values.sort(key=lambda x: x[0])
    total_weight = sum(w for _, w in values)
    cumulative = 0.0
    for val, weight in values:
        cumulative += weight
        if cumulative >= total_weight / 2:
            return val
    return values[-1][0]


def _vote_categorical(
    items: list[tuple[FeatureValue | None, float]],
    name: str,
) -> LearnedValue | None:
    """Run weighted voting on categorical FeatureValue items."""
    votes: list[tuple[str, float]] = []
    for fv, doc_weight in items:
        if fv is not None and isinstance(fv.value, (str, float, int)):
            val = str(fv.value) if not isinstance(fv.value, str) else fv.value
            votes.append((val, fv.weight * doc_weight))

    if not votes:
        return None

    weighted_counts: dict[str, float] = {}
    for value, weight in votes:
        weighted_counts[value] = weighted_counts.get(value, 0) + weight

    total = sum(w for _, w in votes)
    winner = max(weighted_counts, key=weighted_counts.get)
    agreement = weighted_counts[winner] / total if total > 0 else 0.0

    return LearnedValue(
        value=winner,
        confidence=round(agreement * min(1.0, len(votes) / 5.0), 3),
        sample_count=len(votes),
        agreement=round(agreement, 3),
        source_weights=round(total, 3),
    )


def _median_numerical(
    items: list[tuple[FeatureValue | None, float]],
    name: str,
) -> LearnedValue | None:
    """Compute weighted median on numerical FeatureValue items."""
    values: list[tuple[float, float]] = []
    for fv, doc_weight in items:
        if fv is not None and isinstance(fv.value, (int, float)):
            values.append((float(fv.value), fv.weight * doc_weight))

    if not values:
        return None

    result = _weighted_median(values)
    total = sum(w for _, w in values)
    agreeing = sum(w for v, w in values if abs(v - result) < 0.5)
    agreement = agreeing / total if total > 0 else 0.0

    return LearnedValue(
        value=round(result, 2),
        confidence=round(agreement * min(1.0, len(values) / 5.0), 3),
        sample_count=len(values),
        agreement=round(agreement, 3),
        source_weights=round(total, 3),
    )
