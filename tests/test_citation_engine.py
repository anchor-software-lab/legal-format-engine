"""Tests for engines/citation_engine.py."""

from __future__ import annotations

import pytest

from legal_format_engine.engines.citation_engine import (
    Citation,
    CitationIssue,
    CitationReport,
    check_citations,
)


class TestCheckCitations:
    def test_empty_text(self):
        report = check_citations("")
        assert report.stats["total"] == 0
        assert report.issues == []

    def test_no_citations(self):
        report = check_citations("This is plain text with no legal citations at all.")
        assert report.stats["total"] == 0


class TestCaseCitations:
    def test_detects_wis_2d_cite(self):
        text = "In Smith v. Jones, 100 Wis. 2d 200, the court held..."
        report = check_citations(text)
        case_cites = [c for c in report.citations if c.cite_type == "case"]
        assert len(case_cites) >= 1

    def test_detects_federal_cite(self):
        text = "See Brown v. Board, 347 U.S. 483 (1954)."
        report = check_citations(text)
        case_cites = [c for c in report.citations if c.cite_type == "case"]
        assert len(case_cites) >= 1

    def test_case_cite_line_number(self):
        text = "Line one.\nSmith v. Jones, 100 Wis. 2d 200.\nLine three."
        report = check_citations(text)
        case_cites = [c for c in report.citations if c.cite_type == "case"]
        if case_cites:
            assert case_cites[0].line_number == 2

    def test_multiple_case_cites(self):
        text = ("Smith v. Jones, 100 Wis. 2d 200.\n"
                "Brown v. Board, 347 U.S. 483.")
        report = check_citations(text)
        case_cites = [c for c in report.citations if c.cite_type == "case"]
        assert len(case_cites) >= 2


class TestStatuteCitations:
    def test_detects_wis_stat(self):
        text = "Under Wis. Stat. \u00a7 809.19(1), the brief must..."
        report = check_citations(text)
        statute_cites = [c for c in report.citations if c.cite_type == "statute"]
        assert len(statute_cites) >= 1

    def test_detects_usc(self):
        text = "See 42 U.S.C. \u00a7 1983."
        report = check_citations(text)
        statute_cites = [c for c in report.citations if c.cite_type == "statute"]
        assert len(statute_cites) >= 1


class TestIdCitations:
    def test_detects_id(self):
        text = "The court held. Id. at 205."
        report = check_citations(text)
        id_cites = [c for c in report.citations if c.cite_type == "id"]
        assert len(id_cites) >= 1

    def test_lowercase_id_flagged(self):
        text = "The court held. id. at 205."
        report = check_citations(text)
        issues = [i for i in report.issues if i.code == "ID_LOWERCASE"]
        assert len(issues) >= 1
        assert "capitalized" in issues[0].message.lower() or "Id." in issues[0].message

    def test_uppercase_id_no_issue(self):
        text = "The court held. Id. at 205."
        report = check_citations(text)
        issues = [i for i in report.issues if i.code == "ID_LOWERCASE"]
        assert len(issues) == 0

    def test_id_without_at(self):
        text = "See Id."
        report = check_citations(text)
        id_cites = [c for c in report.citations if c.cite_type == "id"]
        assert len(id_cites) >= 1


class TestShortCitations:
    def test_detects_short_cite(self):
        text = "Smith, 100 Wis. 2d at 205."
        report = check_citations(text)
        short_cites = [c for c in report.citations if c.cite_type == "short"]
        assert len(short_cites) >= 1


class TestCaseNameConsistency:
    def test_inconsistent_case_names(self):
        text = ("Smith v. Jones, 100 Wis. 2d 200.\n"
                "Smith vs. Jones, 100 Wis. 2d 200.")
        report = check_citations(text)
        issues = [i for i in report.issues if i.code == "CASE_NAME_INCONSISTENT"]
        assert len(issues) >= 1

    def test_consistent_case_names(self):
        text = ("Smith v. Jones, 100 Wis. 2d 200.\n"
                "Smith v. Jones, 100 Wis. 2d 200.")
        report = check_citations(text)
        issues = [i for i in report.issues if i.code == "CASE_NAME_INCONSISTENT"]
        assert len(issues) == 0


class TestSectionSymbolConsistency:
    def test_mixed_section_and_symbol(self):
        text = "Wis. Stat. \u00a7 809.19. See also section 802.05."
        report = check_citations(text)
        issues = [i for i in report.issues if i.code == "SECTION_SYMBOL_INCONSISTENT"]
        assert len(issues) >= 1

    def test_only_symbol(self):
        text = "Wis. Stat. \u00a7 809.19 and \u00a7 802.05."
        report = check_citations(text)
        issues = [i for i in report.issues if i.code == "SECTION_SYMBOL_INCONSISTENT"]
        assert len(issues) == 0


class TestCitationStats:
    def test_stats_structure(self):
        report = check_citations("")
        assert "total" in report.stats
        assert "case" in report.stats
        assert "statute" in report.stats
        assert "id" in report.stats
        assert "short" in report.stats

    def test_stats_counts(self):
        text = ("Smith v. Jones, 100 Wis. 2d 200.\n"
                "Id. at 205.\n"
                "Wis. Stat. \u00a7 809.19.")
        report = check_citations(text)
        assert report.stats["total"] >= 3
        assert report.stats["case"] >= 1
        assert report.stats["id"] >= 1
        assert report.stats["statute"] >= 1


class TestCitationIssueToDict:
    def test_to_dict(self):
        issue = CitationIssue(code="X", severity="warning", message="msg",
                              citation_text="cite", line_number=5)
        d = issue.to_dict()
        assert d["code"] == "X"
        assert d["line_number"] == 5


class TestCitationDataclass:
    def test_create(self):
        c = Citation(text="Smith v. Jones", cite_type="case", line_number=1)
        assert c.text == "Smith v. Jones"
        assert c.position == 0
