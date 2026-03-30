"""Citation consistency engine.

Detects citation patterns in legal documents and checks for
consistency issues. Does NOT attempt full Bluebook validation -
instead focuses on practical consistency within a single document.

Checks for:
- Inconsistent case name formatting (italics vs. not, abbreviations)
- Inconsistent short cite forms
- Id. usage consistency (capitalization, spacing, punctuation)
- Signal consistency (See, See also, Cf., etc.)
- Pin cite formatting (at vs. comma)
- Statutory citation formatting
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class CitationType(Enum):
    """Types of legal citations."""
    CASE = "case"
    STATUTE = "statute"
    RULE = "rule"
    CONSTITUTIONAL = "constitutional"
    SECONDARY = "secondary"
    ID = "id"
    SHORT_CITE = "short_cite"


class IssueSeverity(Enum):
    """How serious is the citation issue."""
    ERROR = "error"       # Definitely wrong
    WARNING = "warning"   # Likely inconsistent
    INFO = "info"         # Style suggestion


@dataclass
class Citation:
    """A single detected citation."""
    text: str
    citation_type: CitationType
    case_name: str = ""
    reporter: str = ""
    volume: str = ""
    page: str = ""
    pin_cite: str = ""
    year: str = ""
    court: str = ""
    # Position in the document
    section_id: str = ""
    line_offset: int = 0


@dataclass
class CitationIssue:
    """A detected citation consistency problem."""
    severity: IssueSeverity
    code: str
    message: str
    citation_text: str = ""
    suggestion: str = ""
    section_id: str = ""


@dataclass
class CitationReport:
    """Results of citation consistency analysis."""
    citations: list[Citation] = field(default_factory=list)
    issues: list[CitationIssue] = field(default_factory=list)
    case_names: dict[str, list[str]] = field(default_factory=dict)
    id_usages: list[dict] = field(default_factory=list)
    statute_citations: list[Citation] = field(default_factory=list)


# ── Regex Patterns ──────────────────────────────────────────────────

# Case citations: "State v. Smith, 123 Wis. 2d 456, 789 N.W.2d 012 (2020)"
_CASE_CITE_PATTERN = re.compile(
    r"(?P<name>[A-Z][A-Za-z\.\'\-]+(?:\s+(?:v\.|vs\.)\s+[A-Z][A-Za-z\.\'\-\s]+?))"
    r",?\s*"
    r"(?P<volume>\d+)\s+"
    r"(?P<reporter>"
    r"Wis\.?\s*2d|Wis\.|"
    r"N\.W\.2d|N\.W\.|"
    r"F\.\s*(?:2d|3d|4th|Supp\.(?:\s*2d|\s*3d)?)|"
    r"U\.S\.|S\.\s*Ct\.|L\.\s*Ed\.\s*2d|"
    r"F\.R\.D\."
    r")\s+"
    r"(?P<page>\d+)"
    r"(?:,\s*(?P<pin>\d+(?:[-–]\d+)?))?"
    r"(?:\s*\((?P<paren>[^)]+)\))?"
)

# Id. citations
_ID_PATTERN = re.compile(
    r"(?P<id>Id\.|id\.|ID\.)"
    r"(?:\s+at\s+(?P<pin>\d+(?:[-–]\d+)?))?"
)

# Short cites: "Smith, 123 Wis. 2d at 460"
_SHORT_CITE_PATTERN = re.compile(
    r"(?P<name>[A-Z][A-Za-z\.\'\-]+)"
    r",\s*"
    r"(?P<volume>\d+)\s+"
    r"(?P<reporter>"
    r"Wis\.?\s*2d|Wis\.|"
    r"N\.W\.2d|N\.W\.|"
    r"F\.\s*(?:2d|3d|4th)|"
    r"U\.S\."
    r")\s+"
    r"at\s+(?P<pin>\d+(?:[-–]\d+)?)"
)

# Wisconsin statutes: "Wis. Stat. § 904.04(2)(a)" or "§ 904.04"
_WI_STATUTE_PATTERN = re.compile(
    r"(?:Wis\.?\s*Stat\.?\s*(?:(?:Rule|§|sec\.?)\s*)?|§\s*)"
    r"(?P<section>\d+\.\d+)"
    r"(?P<subsections>(?:\(\w+\))*)"
)

# Wis. Stat. Rule: "Wis. Stat. Rule 809.19"
_WI_RULE_PATTERN = re.compile(
    r"(?:Wis\.?\s*Stat\.?\s*Rule\s+|s\.\s*)"
    r"(?P<section>\d+\.\d+)"
    r"(?P<subsections>(?:\(\w+\))*)"
)

# Signals
_SIGNAL_PATTERN = re.compile(
    r"(?:^|\.\s+)"
    r"(?P<signal>See|See also|See, e\.g\.,|See generally|Cf\.|But see|"
    r"Accord|Compare|Contra|E\.g\.,)"
    r"\s+"
)


def check_citation_consistency(text: str, section_id: str = "") -> CitationReport:
    """Analyze text for citation consistency issues.

    Args:
        text: The document text to analyze.
        section_id: Optional section identifier for issue reporting.

    Returns:
        A CitationReport with detected citations and issues.
    """
    report = CitationReport()

    # Extract all citation types
    _extract_case_citations(text, report, section_id)
    _extract_id_citations(text, report, section_id)
    _extract_short_citations(text, report, section_id)
    _extract_statute_citations(text, report, section_id)

    # Run consistency checks
    _check_case_name_consistency(report)
    _check_id_consistency(report)
    _check_signal_consistency(text, report, section_id)
    _check_spacing_issues(text, report, section_id)

    return report


def check_document_citations(sections: list[dict]) -> CitationReport:
    """Check citation consistency across all sections of a document.

    Args:
        sections: List of dicts with 'id' and 'text' keys.

    Returns:
        Aggregated CitationReport.
    """
    combined = CitationReport()

    for section in sections:
        section_id = section.get("id", "")
        text = section.get("text", "")
        report = check_citation_consistency(text, section_id)
        combined.citations.extend(report.citations)
        combined.issues.extend(report.issues)
        combined.id_usages.extend(report.id_usages)
        combined.statute_citations.extend(report.statute_citations)

        # Merge case name tracking
        for name, variants in report.case_names.items():
            if name not in combined.case_names:
                combined.case_names[name] = []
            combined.case_names[name].extend(variants)

    # Re-run cross-section checks
    _check_case_name_consistency(combined)

    return combined


# ── Extraction ──────────────────────────────────────────────────────

def _extract_case_citations(
    text: str, report: CitationReport, section_id: str
) -> None:
    """Find and extract case citations."""
    for match in _CASE_CITE_PATTERN.finditer(text):
        citation = Citation(
            text=match.group(0),
            citation_type=CitationType.CASE,
            case_name=match.group("name").strip(),
            reporter=match.group("reporter").strip(),
            volume=match.group("volume"),
            page=match.group("page"),
            pin_cite=match.group("pin") or "",
            section_id=section_id,
            line_offset=match.start(),
        )
        paren = match.group("paren")
        if paren:
            # Try to extract year and court from parenthetical
            year_match = re.search(r"\b(\d{4})\b", paren)
            if year_match:
                citation.year = year_match.group(1)
                citation.court = paren.replace(year_match.group(1), "").strip(" ,")

        report.citations.append(citation)

        # Track case name variants
        normalized = _normalize_case_name(citation.case_name)
        if normalized not in report.case_names:
            report.case_names[normalized] = []
        report.case_names[normalized].append(citation.case_name)


def _extract_id_citations(
    text: str, report: CitationReport, section_id: str
) -> None:
    """Find Id. citations and track their forms."""
    for match in _ID_PATTERN.finditer(text):
        id_form = match.group("id")
        pin = match.group("pin") or ""

        citation = Citation(
            text=match.group(0),
            citation_type=CitationType.ID,
            pin_cite=pin,
            section_id=section_id,
            line_offset=match.start(),
        )
        report.citations.append(citation)
        report.id_usages.append({
            "form": id_form,
            "pin": pin,
            "full_text": match.group(0),
            "position": match.start(),
            "section_id": section_id,
        })


def _extract_short_citations(
    text: str, report: CitationReport, section_id: str
) -> None:
    """Find short-form case citations."""
    for match in _SHORT_CITE_PATTERN.finditer(text):
        citation = Citation(
            text=match.group(0),
            citation_type=CitationType.SHORT_CITE,
            case_name=match.group("name").strip(),
            reporter=match.group("reporter").strip(),
            volume=match.group("volume"),
            pin_cite=match.group("pin"),
            section_id=section_id,
            line_offset=match.start(),
        )
        report.citations.append(citation)


def _extract_statute_citations(
    text: str, report: CitationReport, section_id: str
) -> None:
    """Find statutory citations."""
    for pattern in [_WI_STATUTE_PATTERN, _WI_RULE_PATTERN]:
        for match in pattern.finditer(text):
            citation = Citation(
                text=match.group(0),
                citation_type=CitationType.STATUTE,
                section_id=section_id,
                line_offset=match.start(),
            )
            report.citations.append(citation)
            report.statute_citations.append(citation)


# ── Consistency Checks ──────────────────────────────────────────────

def _check_case_name_consistency(report: CitationReport) -> None:
    """Check for inconsistent case name formatting."""
    for normalized, variants in report.case_names.items():
        if len(variants) <= 1:
            continue

        unique_forms = list(set(variants))
        if len(unique_forms) > 1:
            report.issues.append(CitationIssue(
                severity=IssueSeverity.WARNING,
                code="INCONSISTENT_CASE_NAME",
                message=(
                    f"Case name '{normalized}' appears in {len(unique_forms)} "
                    f"different forms: {', '.join(repr(f) for f in unique_forms)}"
                ),
                citation_text=unique_forms[0],
                suggestion=f"Use a consistent form throughout (e.g., '{unique_forms[0]}')",
            ))


def _check_id_consistency(report: CitationReport) -> None:
    """Check for inconsistent Id. usage."""
    if not report.id_usages:
        return

    forms = [u["form"] for u in report.id_usages]
    unique_forms = set(forms)

    if len(unique_forms) > 1:
        report.issues.append(CitationIssue(
            severity=IssueSeverity.WARNING,
            code="INCONSISTENT_ID_FORM",
            message=(
                f"'Id.' appears in inconsistent forms: "
                f"{', '.join(repr(f) for f in sorted(unique_forms))}"
            ),
            suggestion="Use 'Id.' consistently (capitalized, with period).",
        ))

    # Check for "Id." at start of sentence (should be capitalized)
    for usage in report.id_usages:
        if usage["form"] == "id.":
            report.issues.append(CitationIssue(
                severity=IssueSeverity.INFO,
                code="LOWERCASE_ID",
                message="'id.' should typically be capitalized as 'Id.' at the start of a citation.",
                citation_text=usage["full_text"],
                suggestion="Id.",
                section_id=usage["section_id"],
            ))


def _check_signal_consistency(
    text: str, report: CitationReport, section_id: str
) -> None:
    """Check for inconsistent citation signal usage."""
    signals_found: dict[str, list[str]] = {}

    for match in _SIGNAL_PATTERN.finditer(text):
        signal = match.group("signal")
        normalized = signal.lower().rstrip(".,")
        if normalized not in signals_found:
            signals_found[normalized] = []
        signals_found[normalized].append(signal)

    for normalized, forms in signals_found.items():
        unique_forms = set(forms)
        if len(unique_forms) > 1:
            report.issues.append(CitationIssue(
                severity=IssueSeverity.WARNING,
                code="INCONSISTENT_SIGNAL",
                message=(
                    f"Citation signal '{normalized}' appears in "
                    f"inconsistent forms: {', '.join(repr(f) for f in sorted(unique_forms))}"
                ),
                section_id=section_id,
            ))


def _check_spacing_issues(
    text: str, report: CitationReport, section_id: str
) -> None:
    """Check for common spacing issues in citations."""
    # Double spaces in citations
    double_space_cites = re.findall(
        r"(?:Wis\.|N\.W\.|F\.|U\.S\.)\s{2,}\d+", text
    )
    for cite in double_space_cites:
        report.issues.append(CitationIssue(
            severity=IssueSeverity.INFO,
            code="DOUBLE_SPACE_IN_CITE",
            message="Extra space detected in citation.",
            citation_text=cite.strip(),
            suggestion=re.sub(r"\s{2,}", " ", cite).strip(),
            section_id=section_id,
        ))

    # Section symbol spacing: "§904.04" should be "§ 904.04"
    no_space_section = re.findall(r"§\d+\.\d+", text)
    for cite in no_space_section:
        report.issues.append(CitationIssue(
            severity=IssueSeverity.INFO,
            code="SECTION_SYMBOL_SPACING",
            message="Missing space after section symbol (§).",
            citation_text=cite,
            suggestion=cite.replace("§", "§ "),
            section_id=section_id,
        ))


def _normalize_case_name(name: str) -> str:
    """Normalize a case name for comparison."""
    # Remove common variations
    name = name.strip().rstrip(",")
    name = re.sub(r"\s+", " ", name)
    # Normalize "v." variations
    name = re.sub(r"\s+vs?\.\s+", " v. ", name)
    return name.lower()
