"""Machine learning pipeline for legal document formatting."""

from legal_format_engine.ml.normalizer import normalize_document, NormalizedDocument
from legal_format_engine.ml.features import extract_features, FeatureVector
from legal_format_engine.ml.learner import learn_patterns, LearnedPatterns
from legal_format_engine.ml.synthesizer import synthesize_ruleset, recommend_changes
from legal_format_engine.ml.pipeline import MLPipeline
from legal_format_engine.ml.attribution import detect_attribution
from legal_format_engine.ml.firm_database import FirmDatabase

__all__ = [
    "normalize_document",
    "NormalizedDocument",
    "extract_features",
    "FeatureVector",
    "learn_patterns",
    "LearnedPatterns",
    "synthesize_ruleset",
    "recommend_changes",
    "MLPipeline",
    "detect_attribution",
    "FirmDatabase",
]
