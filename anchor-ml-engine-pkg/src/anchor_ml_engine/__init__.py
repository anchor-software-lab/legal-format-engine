"""Anchor ML Engine: domain-agnostic document format learning and style synthesis.

This package provides:
- normalizer: Converts any document format to a canonical representation
- features: Extracts numerical/categorical feature vectors from normalized docs
- learner: Statistical pattern learning with weighted median and IQR outlier rejection
- synthesizer: Generates formatting specifications from learned patterns
- pipeline: End-to-end orchestrator for ingest, learn, and synthesize
- attribution: Auto-detect author/organization from uploaded documents
- firm_database: Reference database of 160+ law firms with fuzzy matching
- archive: Extract documents from ZIP, RAR, and Adobe Portfolio archives
- style_profiles: Per-author/organization style profiles with rule hierarchy
- rule_hierarchy: Mandatory rules > ML learned > style profiles > defaults
- pattern_store: JSON-based storage for learned patterns
- connectors: Format-specific extractors (DOCX, PDF, Google Docs)
"""

from anchor_ml_engine.models import (
    AggregatePatterns,
    DetectedAttribution,
    DocumentAnalysis,
    DocumentFeatures,
    FeatureValue,
    FormatRecommendation,
    FormattingDecision,
    HeadingFeatures,
    LearnedFormat,
    LearnedHeadingStyle,
    LearnedSectionOrder,
    LearnedValue,
    NormalizedDocument,
    NormalizedFont,
    NormalizedHeading,
    NormalizedMargins,
    NormalizedParagraphStyle,
    NormalizedSection,
    ResolvedFormat,
    StylePreference,
    StyleProfile,
)

from anchor_ml_engine.normalizer import (
    build_normalized_document,
    canonicalize_font_name,
    normalize_document,
    snap_font_size,
    snap_indent,
    snap_line_spacing,
    snap_margin,
    snap_to_standard,
)

from anchor_ml_engine.features import extract_features
from anchor_ml_engine.learner import FormatLearner
from anchor_ml_engine.synthesizer import diff_against_ruleset, synthesize_ruleset
from anchor_ml_engine.pipeline import MLPipeline

__all__ = [
    # Models
    "NormalizedDocument",
    "NormalizedFont",
    "NormalizedMargins",
    "NormalizedHeading",
    "NormalizedSection",
    "NormalizedParagraphStyle",
    "FeatureValue",
    "DocumentFeatures",
    "HeadingFeatures",
    "LearnedValue",
    "LearnedFormat",
    "LearnedHeadingStyle",
    "LearnedSectionOrder",
    "FormatRecommendation",
    "DetectedAttribution",
    "StylePreference",
    "StyleProfile",
    "DocumentAnalysis",
    "AggregatePatterns",
    "FormattingDecision",
    "ResolvedFormat",
    # Normalizer
    "canonicalize_font_name",
    "snap_to_standard",
    "snap_margin",
    "snap_font_size",
    "snap_line_spacing",
    "snap_indent",
    "normalize_document",
    "build_normalized_document",
    # Features
    "extract_features",
    # Learner
    "FormatLearner",
    # Synthesizer
    "synthesize_ruleset",
    "diff_against_ruleset",
    # Pipeline
    "MLPipeline",
]
