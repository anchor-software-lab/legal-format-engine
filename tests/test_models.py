"""Tests for data models."""

from legal_format_engine.models.document import (
    Alignment,
    ContentBlock,
    HeadingLevel,
    LegalDocument,
    Section,
    Severity,
    ValidationIssue,
)
from legal_format_engine.models.metadata import (
    AttorneyInfo,
    CaseMetadata,
    DocumentMetadata,
    Party,
    PartyRole,
)


class TestMetadata:
    def test_party_creation(self):
        party = Party(name="State of Wisconsin", role=PartyRole.PLAINTIFF_RESPONDENT)
        assert party.name == "State of Wisconsin"
        assert party.role == PartyRole.PLAINTIFF_RESPONDENT

    def test_metadata_roundtrip(self, sample_metadata):
        data = sample_metadata.model_dump()
        restored = DocumentMetadata.model_validate(data)
        assert restored.jurisdiction == "wisconsin"
        assert restored.case.case_number == "2024AP001234-CR"
        assert len(restored.case.parties) == 2


class TestDocument:
    def test_empty_document(self):
        doc = LegalDocument()
        assert doc.sections == []
        assert doc.issues == []
        assert doc.caption is None

    def test_section_creation(self):
        section = Section(
            id="argument",
            heading_text="ARGUMENT",
            heading_level=HeadingLevel.LEVEL_1,
            content=[ContentBlock(text="Some argument text.")],
        )
        assert section.heading_level == HeadingLevel.LEVEL_1
        assert len(section.content) == 1

    def test_validation_issue(self):
        issue = ValidationIssue(
            severity=Severity.WARNING,
            code="MISSING_SECTION",
            message="Required section 'Conclusion' is missing.",
        )
        assert issue.auto_fixable is False
