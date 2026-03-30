"""Style profiles - learned formatting preferences per author/firm."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StyleProfile:
    """Formatting preferences for an author or firm."""
    identifier: str  # Author name or firm name
    profile_type: str = "author"  # "author" or "firm"
    first_line_indent: Optional[float] = None
    block_quote_indent: Optional[float] = None
    section_spacing_pt: Optional[float] = None
    footnote_style: Optional[str] = None
    justify: Optional[bool] = None
    include_toc: Optional[bool] = None
    include_toa: Optional[bool] = None
    document_count: int = 0
    confidence: float = 0.0


def build_style_profile(
    identifier: str,
    vectors: list,
    profile_type: str = "author",
) -> StyleProfile:
    """Build a style profile from feature vectors for a specific author/firm."""
    profile = StyleProfile(
        identifier=identifier,
        profile_type=profile_type,
        document_count=len(vectors),
    )

    # Aggregate first-line indent
    indents = []
    for v in vectors:
        if v.first_line_indent:
            indents.append(v.first_line_indent[0])
    if indents:
        profile.first_line_indent = sorted(indents)[len(indents) // 2]  # median
        profile.confidence = min(1.0, len(indents) / 3)  # More docs = more confidence

    return profile


@dataclass
class RuleHierarchyResult:
    """Result of applying the rule hierarchy."""
    field: str
    value: object
    source: str  # "court_rule", "ml_learned", "style_profile", "default"
    confidence: float = 1.0


def resolve_format(
    court_rules: dict,
    ml_patterns: dict,
    style_profile: Optional[StyleProfile],
    defaults: dict,
) -> dict:
    """Apply the rule hierarchy:
    1. Court Rules (YAML) — mandatory, always enforced
    2. ML Learned Patterns — consensus from uploaded documents
    3. Style Profiles — author/firm discretionary preferences
    4. Engine Defaults — fallback for everything else

    Returns the resolved format dict.
    """
    result = dict(defaults)

    # Apply style profile (lowest priority of the overrides)
    if style_profile:
        if style_profile.first_line_indent is not None:
            result["first_line_indent_inches"] = style_profile.first_line_indent

    # Apply ML patterns (higher priority than style)
    for key, value in ml_patterns.items():
        if value is not None:
            result[key] = value

    # Apply court rules (highest priority — always wins)
    for key, value in court_rules.items():
        if value is not None:
            result[key] = value

    return result
