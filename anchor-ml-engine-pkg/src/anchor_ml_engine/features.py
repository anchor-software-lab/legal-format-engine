"""Feature extraction: converts NormalizedDocuments into numerical vectors.

The learner works on feature vectors, not raw document objects. This module
extracts consistent, comparable features from NormalizedDocuments.

Features are grouped into categories:
- Typography: font family (categorical), font size, line spacing
- Layout: margins (4 values), indentation
- Headings: per-level style features (case, alignment, bold, numbering)
- Structure: section presence/absence, section ordering

Each feature has a weight reflecting extraction confidence. PDF-derived
margins get lower weight than DOCX-derived margins because they're estimated.
"""

from __future__ import annotations

from anchor_ml_engine.models import (
    DocumentFeatures,
    FeatureValue,
    HeadingFeatures,
    NormalizedDocument,
)


def extract_features(doc: NormalizedDocument) -> DocumentFeatures:
    """Extract a feature vector from a NormalizedDocument.

    The extraction_confidence of the source document is used to weight
    all derived features. PDF features get lower weight than DOCX features.
    """
    base_weight = doc.extraction_confidence

    features = DocumentFeatures(
        document_id=doc.id,
        source_filename=doc.source_filename,
        category=doc.category,
        subcategory=doc.subcategory,
        document_type=doc.document_type,
        extraction_confidence=base_weight,
    )

    # Typography
    if doc.primary_font:
        features.font_family = FeatureValue(
            name="font_family",
            value=doc.primary_font.family,
            weight=base_weight,
            source=doc.source_filename,
        )
        features.font_size_pt = FeatureValue(
            name="font_size_pt",
            value=doc.primary_font.size_pt,
            weight=base_weight,
            source=doc.source_filename,
        )

    if doc.line_spacing is not None:
        features.line_spacing = FeatureValue(
            name="line_spacing",
            value=doc.line_spacing,
            weight=base_weight,
            source=doc.source_filename,
        )

    # Layout -- margins from PDFs get reduced weight
    if doc.margins:
        margin_weight = base_weight
        if doc.margins.source_quality == "estimated":
            margin_weight *= 0.6  # PDF margins are noisy

        for side in ("top", "bottom", "left", "right"):
            setattr(features, f"margin_{side}", FeatureValue(
                name=f"margin_{side}",
                value=getattr(doc.margins, side),
                weight=margin_weight,
                source=doc.source_filename,
            ))

    # Indentation
    if doc.body_first_line_indent is not None:
        features.body_indent = FeatureValue(
            name="body_indent",
            value=doc.body_first_line_indent,
            weight=base_weight,
            source=doc.source_filename,
        )

    if doc.block_quote_indent is not None:
        features.block_quote_indent = FeatureValue(
            name="block_quote_indent",
            value=doc.block_quote_indent,
            weight=base_weight,
            source=doc.source_filename,
        )

    # Heading features (per level)
    for heading in doc.heading_styles:
        hf = HeadingFeatures(level=heading.level)

        heading_weight = base_weight
        if heading.sample_count and heading.sample_count < 3:
            heading_weight *= 0.5  # few samples = less confidence

        hf.case_style = FeatureValue(
            name=f"heading_{heading.level}_case",
            value=heading.case_style,
            weight=heading_weight,
            source=doc.source_filename,
        )
        hf.alignment = FeatureValue(
            name=f"heading_{heading.level}_alignment",
            value=heading.alignment,
            weight=heading_weight,
            source=doc.source_filename,
        )
        hf.bold = FeatureValue(
            name=f"heading_{heading.level}_bold",
            value=1.0 if heading.bold else 0.0,
            weight=heading_weight,
            source=doc.source_filename,
        )
        if heading.font_size_pt is not None:
            hf.font_size_pt = FeatureValue(
                name=f"heading_{heading.level}_font_size",
                value=heading.font_size_pt,
                weight=heading_weight,
                source=doc.source_filename,
            )
        if heading.numbering is not None:
            hf.numbering = FeatureValue(
                name=f"heading_{heading.level}_numbering",
                value=heading.numbering,
                weight=heading_weight,
                source=doc.source_filename,
            )

        features.heading_features[heading.level] = hf

    # Section structure
    features.section_ids = [s.id for s in doc.sections]
    features.section_count = len(doc.sections)

    return features
