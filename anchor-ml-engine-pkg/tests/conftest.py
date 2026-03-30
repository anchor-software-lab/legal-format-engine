"""Shared fixtures for anchor-ml-engine tests."""

from __future__ import annotations

import pytest

from anchor_ml_engine.models import (
    DocumentFeatures,
    FeatureValue,
    HeadingFeatures,
    NormalizedDocument,
    NormalizedFont,
    NormalizedHeading,
    NormalizedMargins,
    NormalizedParagraphStyle,
    NormalizedSection,
    StylePreference,
    StyleProfile,
)


@pytest.fixture
def sample_normalized_doc() -> NormalizedDocument:
    """A realistic NormalizedDocument for testing."""
    return NormalizedDocument(
        id="test001",
        source_filename="test_brief.docx",
        source_format="docx",
        category="wisconsin",
        subcategory="appellate",
        document_type="brief",
        extraction_confidence=1.0,
        primary_font=NormalizedFont(family="Times New Roman", size_pt=12.0, weight=1.0),
        margins=NormalizedMargins(top=1.0, bottom=1.0, left=1.0, right=1.0),
        line_spacing=2.0,
        heading_styles=[
            NormalizedHeading(level=1, case_style="upper", alignment="center", bold=True, sample_count=5),
            NormalizedHeading(level=2, case_style="title", alignment="left", bold=True, numbering="roman", sample_count=8),
        ],
        sections=[
            NormalizedSection(id="table_of_contents", original_name="TABLE OF CONTENTS", order=0),
            NormalizedSection(id="argument", original_name="ARGUMENT", order=1),
            NormalizedSection(id="conclusion", original_name="CONCLUSION", order=2),
        ],
        body_first_line_indent=0.5,
        block_quote_indent=0.5,
    )


@pytest.fixture
def sample_features(sample_normalized_doc) -> DocumentFeatures:
    """Feature vector extracted from sample_normalized_doc."""
    from anchor_ml_engine.features import extract_features
    return extract_features(sample_normalized_doc)


@pytest.fixture
def multiple_features() -> list[DocumentFeatures]:
    """Multiple feature vectors for learning tests."""
    docs = []
    for i in range(5):
        doc = NormalizedDocument(
            id=f"doc_{i:03d}",
            source_filename=f"brief_{i}.docx",
            source_format="docx",
            category="wisconsin",
            subcategory="appellate",
            extraction_confidence=1.0,
            primary_font=NormalizedFont(family="Times New Roman", size_pt=12.0),
            margins=NormalizedMargins(top=1.0, bottom=1.0, left=1.0, right=1.0),
            line_spacing=2.0,
            body_first_line_indent=0.5,
        )
        from anchor_ml_engine.features import extract_features
        docs.append(extract_features(doc))
    return docs


@pytest.fixture
def sample_style_profile() -> StyleProfile:
    """A sample style profile for testing."""
    return StyleProfile(
        profile_type="author",
        name="Test Author",
        document_count=5,
        categories=["wisconsin"],
        preferences=[
            StylePreference(
                field="body_first_line_indent",
                value=0.5,
                sample_count=5,
                consistency=0.9,
            ),
            StylePreference(
                field="heading_space_before_pt",
                value=18.0,
                sample_count=4,
                consistency=0.75,
            ),
        ],
    )
