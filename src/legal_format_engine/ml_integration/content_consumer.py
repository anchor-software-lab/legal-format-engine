"""Content consumer: loads ML-exported argument structure and citation data.

This module consumes the structural JSON exported by the ML engine's
format_export.export_argument_structure(). It provides:

- Argument architecture analysis (section types, reasoning flows)
- Citation pattern data (density, signals, court distribution)
- Reasoning pattern models for document generation

This is the foundation for a Midpage-style legal research connector.

Governance: only distilled structural patterns cross this boundary.
No verbatim text, no case-specific facts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SectionStructure:
    """Structural analysis of an argument section."""
    id: str = ""
    section_type: str = ""  # e.g., "main_argument", "sub_argument"
    argument_type: str = ""  # e.g., "sufficiency_of_evidence"
    standard_of_review: str = ""  # e.g., "de_novo"
    reasoning_flow: list[str] = field(default_factory=list)
    citation_count: int = 0
    word_count: int = 0
    depth: int = 1


@dataclass
class CitationPatterns:
    """Citation usage patterns from analyzed documents."""
    total_citations: int = 0
    unique_authorities: int = 0
    citation_density: float = 0.0  # cites per page
    by_section: dict[str, int] = field(default_factory=dict)
    signal_distribution: dict[str, int] = field(default_factory=dict)
    court_distribution: dict[str, int] = field(default_factory=dict)
    pinpoint_rate: float = 0.0  # proportion of cites with pinpoints


@dataclass
class ReasoningModel:
    """A distilled reasoning pattern for argument construction."""
    pattern_type: str = ""  # e.g., "rule_application", "analogical"
    components: list[str] = field(default_factory=list)
    frequency: float = 0.0
    typical_citation_density: float = 0.0


@dataclass
class DocumentStructureSpec:
    """Complete structural specification imported from the ML engine.

    Contains distilled argument architecture, citation patterns, and
    reasoning models — never verbatim document content.
    """
    document_type: str = ""
    total_word_count: int = 0
    total_sections: int = 0
    total_arguments: int = 0
    argument_to_total_ratio: float = 0.0
    sections: list[SectionStructure] = field(default_factory=list)
    citation_patterns: CitationPatterns = field(default_factory=CitationPatterns)
    reasoning_models: list[ReasoningModel] = field(default_factory=list)


def load_structure_spec(path: str | Path) -> DocumentStructureSpec:
    """Load a structural spec from JSON exported by the ML engine.

    Args:
        path: Path to the JSON file produced by
              anchor_ml_engine.format_export.export_argument_structure()

    Returns:
        A DocumentStructureSpec with distilled structural patterns.
    """
    path = Path(path)
    with open(path) as f:
        data = json.load(f)

    spec = DocumentStructureSpec()

    # Metadata
    meta = data.get("_export_metadata", {})
    spec.document_type = meta.get("document_type", "")

    # Document metrics
    metrics = data.get("document_metrics", {})
    spec.total_word_count = metrics.get("total_word_count", 0)
    spec.total_sections = metrics.get("total_sections", 0)
    spec.total_arguments = metrics.get("total_arguments", 0)
    spec.argument_to_total_ratio = metrics.get("argument_to_total_ratio", 0.0)

    # Sections
    for s in data.get("argument_sections", []):
        spec.sections.append(SectionStructure(
            id=s.get("id", ""),
            section_type=s.get("section_type", ""),
            argument_type=s.get("argument_type", ""),
            standard_of_review=s.get("standard_of_review", ""),
            reasoning_flow=s.get("reasoning_flow", []),
            citation_count=s.get("citation_count", 0),
            word_count=s.get("word_count", 0),
            depth=s.get("depth", 1),
        ))

    # Citation patterns
    cg = data.get("citation_graph", {})
    spec.citation_patterns = CitationPatterns(
        total_citations=cg.get("total_citations", 0),
        unique_authorities=cg.get("unique_authorities", 0),
        citation_density=cg.get("citation_density", 0.0),
        by_section=cg.get("by_section", {}),
        signal_distribution=cg.get("signal_distribution", {}),
        court_distribution=cg.get("court_distribution", {}),
        pinpoint_rate=cg.get("pinpoint_rate", 0.0),
    )

    # Reasoning models
    for rp in data.get("reasoning_patterns", []):
        spec.reasoning_models.append(ReasoningModel(
            pattern_type=rp.get("pattern_type", ""),
            components=rp.get("components", []),
            frequency=rp.get("frequency", 0.0),
            typical_citation_density=rp.get("typical_citation_density", 0.0),
        ))

    return spec


def suggest_argument_outline(
    structure_spec: DocumentStructureSpec,
    argument_type: str | None = None,
) -> list[dict]:
    """Suggest an argument outline based on learned structural patterns.

    Uses the reasoning models and section patterns to suggest how an
    argument of the given type should be structured.

    Args:
        structure_spec: Loaded structural spec from ML engine.
        argument_type: Optional filter to a specific argument type.

    Returns:
        A list of outline items with section_type, reasoning_flow,
        and expected citation density.
    """
    outline: list[dict] = []

    # Find matching sections from the learned structure
    matching_sections = structure_spec.sections
    if argument_type:
        matching_sections = [
            s for s in matching_sections
            if s.argument_type == argument_type or s.section_type in ("main_argument", "sub_argument")
        ]

    # Find the most common reasoning flow
    best_pattern = None
    for model in structure_spec.reasoning_models:
        if argument_type and model.pattern_type == "rule_application":
            best_pattern = model
            break
        if best_pattern is None or model.frequency > best_pattern.frequency:
            best_pattern = model

    if best_pattern:
        for i, component in enumerate(best_pattern.components):
            outline.append({
                "order": i + 1,
                "component": component,
                "description": _component_description(component),
                "pattern_type": best_pattern.pattern_type,
            })
    elif matching_sections:
        # Fall back to section-level structure
        for i, section in enumerate(matching_sections):
            outline.append({
                "order": i + 1,
                "section_type": section.section_type,
                "argument_type": section.argument_type,
                "reasoning_flow": section.reasoning_flow,
                "expected_citations": section.citation_count,
            })

    return outline


def _component_description(component: str) -> str:
    """Human-readable description of a reasoning component."""
    descriptions = {
        "standard_of_review": "State the applicable standard of review",
        "rule_statement": "State the governing legal rule with authority",
        "rule_explanation": "Explain how courts have applied the rule",
        "fact_application": "Apply the rule to the facts of this case",
        "conclusion": "State the conclusion that follows",
        "transition": "Transition to the next point",
        "analysis": "Develop the analytical argument",
        "issue_statement": "Frame the issue for the court",
    }
    return descriptions.get(component, component.replace("_", " ").title())
