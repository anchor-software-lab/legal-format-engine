"""Tests for ML style profiles and rule hierarchy."""

import tempfile
from pathlib import Path

import pytest

from legal_format_engine.ml.normalizer import (
    NormalizedDocument,
    NormalizedFont,
    NormalizedMargins,
    NormalizedHeading,
    NormalizedSection,
    NormalizedParagraphStyle,
)
from legal_format_engine.ml.styles import (
    DISCRETIONARY_FIELDS,
    StyleProfile,
    StyleProfileStore,
    StylePreference,
    build_style_profile,
)
from legal_format_engine.ml.rule_hierarchy import (
    FormattingDecision,
    ResolvedFormat,
    identify_rule_governed_fields,
    resolve_format,
)
from legal_format_engine.rules.schema import (
    HeadingRule,
    PageFormat,
    Ruleset,
)


def _make_doc(
    author: str = "John Smith",
    firm: str = "Smith & Associates",
    jurisdiction: str = "wisconsin",
    first_line_indent: float = 0.5,
    block_quote_indent: float = 0.75,
    alignment: str = "justify",
) -> NormalizedDocument:
    """Create a test document with known values."""
    return NormalizedDocument(
        source_filename="test.docx",
        source_format="docx",
        jurisdiction=jurisdiction,
        court_level="appellate",
        document_type="brief",
        author=author,
        firm=firm,
        extraction_confidence=1.0,
        primary_font=NormalizedFont(family="Times New Roman", size_pt=12.0),
        margins=NormalizedMargins(top=1.0, bottom=1.0, left=1.0, right=1.0),
        line_spacing=2.0,
        heading_styles=[
            NormalizedHeading(level=1, case_style="title", alignment="center", bold=True),
        ],
        sections=[
            NormalizedSection(id="table_of_contents", original_name="Table of Contents", order=0),
            NormalizedSection(id="argument", original_name="Argument", order=1),
            NormalizedSection(id="conclusion", original_name="Conclusion", order=2),
            NormalizedSection(id="introduction", original_name="Introduction", order=3),
        ],
        paragraph_styles=[
            NormalizedParagraphStyle(
                context="body",
                font_family="Times New Roman",
                font_size_pt=12.0,
                line_spacing=2.0,
                first_line_indent=first_line_indent,
                alignment=alignment,
            ),
            NormalizedParagraphStyle(
                context="block_quote",
                font_family="Times New Roman",
                font_size_pt=11.0,
                line_spacing=1.0,
                left_indent=block_quote_indent,
            ),
        ],
    )


class TestStyleProfile:
    def test_serialization_roundtrip(self):
        profile = StyleProfile(
            profile_type="author",
            name="John Smith",
            document_count=5,
            jurisdictions=["wisconsin"],
            preferences=[
                StylePreference(
                    field="body_first_line_indent",
                    value=0.5,
                    sample_count=5,
                    consistency=0.9,
                ),
            ],
        )
        data = profile.to_dict()
        restored = StyleProfile.from_dict(data)
        assert restored.name == "John Smith"
        assert restored.profile_type == "author"
        assert len(restored.preferences) == 1
        assert restored.preferences[0].value == 0.5

    def test_get_preference(self):
        profile = StyleProfile(
            profile_type="firm",
            name="Test Firm",
            preferences=[
                StylePreference(field="body_first_line_indent", value=0.3,
                                sample_count=3, consistency=0.8),
            ],
        )
        pref = profile.get("body_first_line_indent")
        assert pref is not None
        assert pref.value == 0.3

        assert profile.get("nonexistent") is None


class TestStyleProfileStore:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StyleProfileStore(Path(tmpdir))
            profile = StyleProfile(
                profile_type="author",
                name="Jane Doe",
                document_count=3,
            )
            store.save(profile)

            loaded = store.load("author", "Jane Doe")
            assert loaded is not None
            assert loaded.name == "Jane Doe"

    def test_list_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StyleProfileStore(Path(tmpdir))
            store.save(StyleProfile(profile_type="author", name="Alice"))
            store.save(StyleProfile(profile_type="firm", name="Bob Law"))

            profiles = store.list_all()
            assert len(profiles) == 2

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StyleProfileStore(Path(tmpdir))
            store.save(StyleProfile(profile_type="author", name="Delete Me"))
            assert store.delete("author", "Delete Me")
            assert store.load("author", "Delete Me") is None
            assert not store.delete("author", "Delete Me")


class TestBuildStyleProfile:
    def test_builds_from_consistent_documents(self):
        docs = [
            (_make_doc(first_line_indent=0.5, alignment="justify"), {}),
            (_make_doc(first_line_indent=0.5, alignment="justify"), {}),
            (_make_doc(first_line_indent=0.5, alignment="justify"), {}),
        ]
        profile = build_style_profile(docs, "author", "John Smith")

        assert profile.document_count == 3
        assert profile.name == "John Smith"

        indent_pref = profile.get("body_first_line_indent")
        assert indent_pref is not None
        assert indent_pref.value == 0.5
        assert indent_pref.consistency == 1.0

    def test_inconsistent_values_still_captured(self):
        docs = [
            (_make_doc(first_line_indent=0.5), {}),
            (_make_doc(first_line_indent=0.5), {}),
            (_make_doc(first_line_indent=0.3), {}),
        ]
        profile = build_style_profile(docs, "author", "Mixed")

        indent_pref = profile.get("body_first_line_indent")
        assert indent_pref is not None
        # Majority wins
        assert indent_pref.value == 0.5
        assert indent_pref.consistency == pytest.approx(0.667, abs=0.01)

    def test_rule_governed_fields_excluded(self):
        docs = [(_make_doc(), {})]
        # Mark body_first_line_indent as rule-governed
        profile = build_style_profile(
            docs, "author", "Test",
            rule_governed_fields={"body_first_line_indent"},
        )
        assert profile.get("body_first_line_indent") is None

    def test_only_discretionary_fields_included(self):
        docs = [(_make_doc(), {})]
        profile = build_style_profile(docs, "author", "Test")

        for pref in profile.preferences:
            assert pref.field in DISCRETIONARY_FIELDS


class TestRuleHierarchy:
    def _make_ruleset(self) -> Ruleset:
        return Ruleset(
            jurisdiction="wisconsin",
            court_level="appellate",
            document_type="brief",
            page_format=PageFormat(
                font_name="Times New Roman",
                font_size_pt=10,
                line_spacing=2.0,
                margin_top_inches=1.25,
                margin_bottom_inches=1.25,
                margin_left_inches=2.0,
                margin_right_inches=2.0,
            ),
            heading_rules=[
                HeadingRule(level=1, case_style="title", alignment="center", bold=True),
                HeadingRule(level=2, case_style="upper", alignment="left",
                            numbering="roman", bold=True),
            ],
        )

    def test_rule_governed_fields_identified(self):
        ruleset = self._make_ruleset()
        governed = identify_rule_governed_fields(ruleset)

        assert "font_name" in governed
        assert "font_size_pt" in governed
        assert "heading_1_case_style" in governed
        assert "heading_2_numbering" in governed

    def test_rules_always_win(self):
        ruleset = self._make_ruleset()
        resolved = resolve_format(ruleset)

        font_decision = resolved.get("font_name")
        assert font_decision is not None
        assert font_decision.value == "Times New Roman"
        assert font_decision.source == "rule"
        assert font_decision.confidence == 1.0

        size_decision = resolved.get("font_size_pt")
        assert size_decision is not None
        assert size_decision.value == 10
        assert size_decision.source == "rule"

    def test_margins_from_rules(self):
        ruleset = self._make_ruleset()
        resolved = resolve_format(ruleset)

        left = resolved.get("margin_left_inches")
        assert left.value == 2.0
        assert left.source == "rule"

    def test_discretionary_fields_get_defaults(self):
        ruleset = self._make_ruleset()
        resolved = resolve_format(ruleset)

        indent = resolved.get("body_first_line_indent")
        assert indent is not None
        assert indent.source == "default"

    def test_style_profile_fills_gaps(self):
        ruleset = self._make_ruleset()
        style = StyleProfile(
            profile_type="author",
            name="Test Attorney",
            preferences=[
                StylePreference(
                    field="body_first_line_indent",
                    value=0.3,
                    sample_count=10,
                    consistency=0.9,
                ),
            ],
        )
        resolved = resolve_format(ruleset, style=style)

        indent = resolved.get("body_first_line_indent")
        assert indent is not None
        assert indent.value == 0.3
        assert indent.source == "style_profile"

    def test_style_cannot_override_rules(self):
        """Even if a style profile has font preferences, rules win."""
        ruleset = self._make_ruleset()
        resolved = resolve_format(ruleset)

        # Font is from rule no matter what
        font = resolved.get("font_name")
        assert font.source == "rule"
        assert font.value == "Times New Roman"

    def test_provenance_summary(self):
        ruleset = self._make_ruleset()
        resolved = resolve_format(ruleset)
        result = resolved.to_dict()

        assert result["summary"]["from_rules"] > 0
        assert result["summary"]["total"] > 0
        assert "decisions" in result

    def test_heading_rules_enforced(self):
        ruleset = self._make_ruleset()
        resolved = resolve_format(ruleset)

        h1_case = resolved.get("heading_1_case_style")
        assert h1_case.value == "title"
        assert h1_case.source == "rule"

        h2_numbering = resolved.get("heading_2_numbering")
        assert h2_numbering.value == "roman"
        assert h2_numbering.source == "rule"


class TestNormalizedDocumentAttribution:
    def test_author_and_firm_fields(self):
        doc = _make_doc(author="Jane Doe", firm="Doe & Partners")
        assert doc.author == "Jane Doe"
        assert doc.firm == "Doe & Partners"

    def test_serialization_with_attribution(self):
        doc = _make_doc(author="Test", firm="Test Firm")
        data = doc.model_dump()
        assert data["author"] == "Test"
        assert data["firm"] == "Test Firm"

        restored = NormalizedDocument.model_validate(data)
        assert restored.author == "Test"
        assert restored.firm == "Test Firm"
