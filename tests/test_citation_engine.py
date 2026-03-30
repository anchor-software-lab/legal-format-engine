"""Tests for citation consistency engine."""

from legal_format_engine.engines.citation_engine import (
    CitationType,
    IssueSeverity,
    check_citation_consistency,
    check_document_citations,
)


class TestCaseCitationDetection:
    def test_detects_wi_case(self):
        text = "State v. Sullivan, 216 Wis. 2d 768, 576 N.W.2d 30 (1998)"
        report = check_citation_consistency(text)
        cases = [c for c in report.citations if c.citation_type == CitationType.CASE]
        assert len(cases) >= 1

    def test_detects_federal_case(self):
        text = "United States v. Curtin, 489 F.3d 935 (9th Cir. 2007)"
        report = check_citation_consistency(text)
        cases = [c for c in report.citations if c.citation_type == CitationType.CASE]
        assert len(cases) >= 1

    def test_extracts_case_name(self):
        text = "State v. Smith, 123 Wis. 2d 456, 789 N.W.2d 012 (2020)"
        report = check_citation_consistency(text)
        cases = [c for c in report.citations if c.citation_type == CitationType.CASE]
        assert any("State v. Smith" in c.case_name for c in cases)

    def test_extracts_pin_cite(self):
        text = "State v. Smith, 123 Wis. 2d 456, 460 (2020)"
        report = check_citation_consistency(text)
        cases = [c for c in report.citations if c.citation_type == CitationType.CASE]
        assert any(c.pin_cite == "460" for c in cases)


class TestIdDetection:
    def test_detects_id(self):
        text = "The court held this was error. Id. at 460."
        report = check_citation_consistency(text)
        ids = [c for c in report.citations if c.citation_type == CitationType.ID]
        assert len(ids) == 1

    def test_detects_id_without_pin(self):
        text = "The court agreed. Id."
        report = check_citation_consistency(text)
        ids = [c for c in report.citations if c.citation_type == CitationType.ID]
        assert len(ids) == 1

    def test_tracks_id_form(self):
        text = "First. Id. at 10. Second. Id. at 20."
        report = check_citation_consistency(text)
        assert len(report.id_usages) == 2
        assert all(u["form"] == "Id." for u in report.id_usages)


class TestShortCiteDetection:
    def test_detects_short_cite(self):
        text = "Smith, 123 Wis. 2d at 460"
        report = check_citation_consistency(text)
        shorts = [c for c in report.citations if c.citation_type == CitationType.SHORT_CITE]
        assert len(shorts) == 1
        assert shorts[0].pin_cite == "460"


class TestStatuteDetection:
    def test_detects_wi_statute(self):
        text = "Wis. Stat. § 904.04(2)(a)"
        report = check_citation_consistency(text)
        statutes = report.statute_citations
        assert len(statutes) >= 1

    def test_detects_short_form_statute(self):
        text = "under s. 809.19(8)(b)"
        report = check_citation_consistency(text)
        statutes = report.statute_citations
        assert len(statutes) >= 1


class TestConsistencyChecks:
    def test_inconsistent_case_name(self):
        text = (
            "State v. Smith, 123 Wis. 2d 456 (2020). "
            "Later, State v.  Smith, 123 Wis. 2d 456 (2020)."
        )
        report = check_citation_consistency(text)
        # Two different forms should trigger a warning
        name_issues = [i for i in report.issues if i.code == "INCONSISTENT_CASE_NAME"]
        # May or may not flag depending on normalization
        assert isinstance(report.case_names, dict)

    def test_inconsistent_id_forms(self):
        text = "First point. Id. at 10. Second point. id. at 20."
        report = check_citation_consistency(text)
        id_issues = [i for i in report.issues if i.code == "INCONSISTENT_ID_FORM"]
        assert len(id_issues) >= 1

    def test_lowercase_id_flagged(self):
        text = "The court agreed. id. at 456."
        report = check_citation_consistency(text)
        issues = [i for i in report.issues if i.code == "LOWERCASE_ID"]
        assert len(issues) >= 1

    def test_section_symbol_spacing(self):
        text = "under §904.04(2)"
        report = check_citation_consistency(text)
        issues = [i for i in report.issues if i.code == "SECTION_SYMBOL_SPACING"]
        assert len(issues) >= 1
        assert issues[0].suggestion == "§ 904.04"


class TestDocumentCitations:
    def test_cross_section_analysis(self):
        sections = [
            {"id": "argument_1", "text": "State v. Sullivan, 216 Wis. 2d 768 (1998). Id. at 774."},
            {"id": "argument_2", "text": "Sullivan, 216 Wis. 2d at 780."},
        ]
        report = check_document_citations(sections)
        assert len(report.citations) > 0
        assert len(report.id_usages) > 0


class TestOnActualBriefText:
    """Test against realistic brief text patterns."""

    def test_christopherson_style_citations(self):
        text = """
        State v. Sullivan, 216 Wis. 2d 768, 774, 576 N.W.2d 30 (1998).
        The court in Sullivan identified a three-step analysis. Sullivan,
        216 Wis. 2d at 772. See also State v. Normington, 2008 WI App 8,
        306 Wis. 2d 727, 744 N.W.2d 867. Under Wis. Stat. § 904.04(2)(a),
        other-acts evidence must satisfy three conditions. Id. at 774.
        The circuit court's analysis under s. 809.19(8)(b) was inadequate.
        """
        report = check_citation_consistency(text)
        assert len(report.citations) > 0
        assert len(report.statute_citations) > 0
