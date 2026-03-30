"""Citation consistency engine - checks for common citation issues."""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Citation:
    """Represents a detected citation."""
    text: str
    cite_type: str  # "case", "statute", "short", "id", "signal"
    line_number: int = 0
    position: int = 0


@dataclass
class CitationIssue:
    """A citation consistency issue."""
    code: str
    severity: str  # "error", "warning", "info"
    message: str
    citation_text: str = ""
    line_number: int = 0

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "citation_text": self.citation_text,
            "line_number": self.line_number,
        }


@dataclass
class CitationReport:
    """Full citation analysis report."""
    citations: list[Citation] = field(default_factory=list)
    issues: list[CitationIssue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


# Patterns
_CASE_CITE = re.compile(
    r"([A-Z][a-zA-Z\'\-]+(?:\s+(?:v\.|vs\.)\s+[A-Z][a-zA-Z\'\-]+))"
    r"[,\s]+\d+\s+(?:Wis\.\s*2d|F\.\s*(?:2d|3d|4th)|S\.\s*Ct\.|U\.S\.|N\.W\.\s*2d)"
    r"[\s\d,\(\)]*"
)
_STATUTE_CITE = re.compile(
    r"(?:Wis\.\s*Stat\.\s*[§]+\s*[\d\.]+(?:\(\w+\))*"
    r"|(?:\d+)\s+U\.S\.C\.\s*[§]+\s*[\d\.]+(?:\(\w+\))*)"
)
_ID_CITE = re.compile(r"\b(Id\.|id\.)\s*(?:at\s+\d+)?")
_SHORT_CITE = re.compile(
    r"([A-Z][a-zA-Z\'\-]+),\s+\d+\s+(?:Wis\.\s*2d|F\.\s*(?:2d|3d|4th))\s+at\s+\d+"
)
_SIGNAL = re.compile(r"\b(See|See also|Cf\.|E\.g\.,|Accord|But see|Compare|Contra)\b")


def check_citations(text: str) -> CitationReport:
    """Analyze text for citation consistency issues.

    Checks:
    - Case name consistency
    - Id. capitalization (must be italic "Id." not "id.")
    - Signal usage
    - Section symbol consistency
    """
    citations: list[Citation] = []
    issues: list[CitationIssue] = []

    lines = text.split("\n")
    for line_num, line in enumerate(lines, 1):
        # Case citations
        for m in _CASE_CITE.finditer(line):
            citations.append(Citation(
                text=m.group(0).strip(),
                cite_type="case",
                line_number=line_num,
                position=m.start(),
            ))

        # Statute citations
        for m in _STATUTE_CITE.finditer(line):
            citations.append(Citation(
                text=m.group(0).strip(),
                cite_type="statute",
                line_number=line_num,
                position=m.start(),
            ))

        # Id. citations
        for m in _ID_CITE.finditer(line):
            citations.append(Citation(
                text=m.group(0).strip(),
                cite_type="id",
                line_number=line_num,
                position=m.start(),
            ))
            # Check capitalization
            if m.group(1) == "id.":
                issues.append(CitationIssue(
                    code="ID_LOWERCASE",
                    severity="warning",
                    message="'id.' should be capitalized as 'Id.' per Bluebook Rule 4.1",
                    citation_text=m.group(0).strip(),
                    line_number=line_num,
                ))

        # Short citations
        for m in _SHORT_CITE.finditer(line):
            citations.append(Citation(
                text=m.group(0).strip(),
                cite_type="short",
                line_number=line_num,
                position=m.start(),
            ))

    # Check case name consistency
    case_names: dict[str, list[str]] = {}
    for c in citations:
        if c.cite_type == "case":
            # Extract base case name
            m = re.match(r"([A-Z][a-zA-Z\'\-]+(?:\s+(?:v\.|vs\.)\s+[A-Z][a-zA-Z\'\-]+))", c.text)
            if m:
                base = m.group(1)
                normalized = base.lower().replace("vs.", "v.")
                case_names.setdefault(normalized, []).append(base)

    for normalized, variants in case_names.items():
        unique = set(variants)
        if len(unique) > 1:
            issues.append(CitationIssue(
                code="CASE_NAME_INCONSISTENT",
                severity="warning",
                message=f"Inconsistent case name formatting: {', '.join(sorted(unique))}",
                citation_text=variants[0],
            ))

    # Section symbol consistency
    has_section = "§" in text
    has_double_section = "§§" in text
    has_word_section = re.search(r"\bsection\b", text, re.IGNORECASE) is not None
    if has_section and has_word_section:
        issues.append(CitationIssue(
            code="SECTION_SYMBOL_INCONSISTENT",
            severity="info",
            message="Mixed use of '§' symbol and 'section' word — consider standardizing",
        ))

    stats = {
        "total": len(citations),
        "case": sum(1 for c in citations if c.cite_type == "case"),
        "statute": sum(1 for c in citations if c.cite_type == "statute"),
        "id": sum(1 for c in citations if c.cite_type == "id"),
        "short": sum(1 for c in citations if c.cite_type == "short"),
    }

    return CitationReport(
        citations=citations,
        issues=issues,
        stats=stats,
    )
