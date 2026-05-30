"""Anchor Quality Gate — orchestrator and checker framework.

This package is the conductor of the quality-gate pipeline. It defines:

- The domain model (Document, Segment, Finding, Suggestion, …)
- The Checker protocol that every analyzer implements
- The registry that gathers checkers
- The Pipeline that runs them and produces a QualityReport

Checkers live in their own packages (legal_format_engine.checkers,
legal_citations.checkers, etc.) and register themselves with the
registry. The Pipeline runs deterministic checkers first, then LLM-backed
checkers, then scores and deduplicates findings.
"""

from legal_quality_gate.types import (
    Authority,
    Capability,
    CharRange,
    Citation,
    Document,
    Finding,
    GoodLawStatus,
    ObservedStyle,
    ParsedCitation,
    Provenance,
    QualityReport,
    Segment,
    SegmentKind,
    Severity,
    Suggestion,
    SuggestionKind,
    Treatment,
    TreatmentSignal,
)
from legal_quality_gate.checker import CheckContext, Checker
from legal_quality_gate.registry import CheckerRegistry, default_registry
from legal_quality_gate.pipeline import Pipeline
from legal_quality_gate.policy import Policy, load_policy
from legal_quality_gate.scoring import score_findings

__all__ = [
    "Authority",
    "Capability",
    "CharRange",
    "Citation",
    "Checker",
    "CheckContext",
    "CheckerRegistry",
    "Document",
    "Finding",
    "GoodLawStatus",
    "ObservedStyle",
    "ParsedCitation",
    "Pipeline",
    "Policy",
    "Provenance",
    "QualityReport",
    "Segment",
    "SegmentKind",
    "Severity",
    "Suggestion",
    "SuggestionKind",
    "Treatment",
    "TreatmentSignal",
    "default_registry",
    "load_policy",
    "score_findings",
]
