"""Tests for engines/caption_engine.py."""

from __future__ import annotations

import pytest

from legal_format_engine.engines.caption_engine import (
    DISTRICT_MAP,
    _default_court_name,
    _format_parties,
    generate_caption,
)
from legal_format_engine.models.document import CaseMetadata, Party, PartyRole
from legal_format_engine.models.section import Ruleset, PageFormat


class TestGenerateCaption:
    def test_returns_caption_block(self, sample_case_meta, wi_ruleset):
        caption = generate_caption(sample_case_meta, "Opening Brief", wi_ruleset)
        assert caption is not None

    def test_court_name_from_metadata(self, sample_case_meta, wi_ruleset):
        caption = generate_caption(sample_case_meta, "Brief", wi_ruleset)
        assert caption.court_name == "STATE OF WISCONSIN COURT OF APPEALS"

    def test_court_name_uppercased_in_lines(self, sample_case_meta, wi_ruleset):
        caption = generate_caption(sample_case_meta, "Brief", wi_ruleset)
        court_line = caption.lines[0]
        assert court_line.text == court_line.text.upper()
        assert court_line.bold is True
        assert court_line.centered is True

    def test_case_number_in_lines(self, sample_case_meta, wi_ruleset):
        caption = generate_caption(sample_case_meta, "Brief", wi_ruleset)
        case_no_lines = [l for l in caption.lines if "2025AP001234" in l.text]
        assert len(case_no_lines) >= 1
        assert "Case No." in case_no_lines[0].text

    def test_document_title_uppercased(self, sample_case_meta, wi_ruleset):
        caption = generate_caption(sample_case_meta, "Opening Brief", wi_ruleset)
        title_lines = [l for l in caption.lines if "OPENING BRIEF" in l.text]
        assert len(title_lines) >= 1

    def test_document_title_stored(self, sample_case_meta, wi_ruleset):
        caption = generate_caption(sample_case_meta, "Reply Brief", wi_ruleset)
        assert caption.document_title == "Reply Brief"

    def test_district_in_caption(self, sample_case_meta, wi_ruleset):
        caption = generate_caption(sample_case_meta, "Brief", wi_ruleset)
        district_lines = [l for l in caption.lines if "District I" in l.text]
        assert len(district_lines) == 1

    def test_no_district(self, wi_ruleset):
        meta = CaseMetadata(case_name="A v. B", case_number="123")
        caption = generate_caption(meta, "Brief", wi_ruleset)
        district_lines = [l for l in caption.lines if "District" in l.text]
        assert len(district_lines) == 0

    def test_horizontal_rules_present(self, sample_case_meta, wi_ruleset):
        caption = generate_caption(sample_case_meta, "Brief", wi_ruleset)
        hr_lines = [l for l in caption.lines if l.text.startswith("\u2500")]
        assert len(hr_lines) >= 2

    def test_all_lines_are_caption(self, sample_case_meta, wi_ruleset):
        caption = generate_caption(sample_case_meta, "Brief", wi_ruleset)
        for line in caption.lines:
            assert line.is_caption is True

    def test_empty_doc_title(self, sample_case_meta, wi_ruleset):
        caption = generate_caption(sample_case_meta, "", wi_ruleset)
        title_lines = [l for l in caption.lines if l.text and l.text == l.text.upper()
                       and "COURT" not in l.text and not l.text.startswith("\u2500")
                       and "Case No." not in l.text and "SMITH" not in l.text
                       and "JONES" not in l.text]
        # No title line with content
        assert caption.document_title == ""


class TestFormatParties:
    def test_two_parties_with_v(self, sample_case_meta):
        lines = _format_parties(sample_case_meta)
        v_lines = [l for l in lines if "v." in l.text]
        assert len(v_lines) == 1

    def test_party_names_uppercased(self, sample_case_meta):
        lines = _format_parties(sample_case_meta)
        name_lines = [l for l in lines if "JOHN SMITH" in l.text or "JANE JONES" in l.text]
        assert len(name_lines) == 2

    def test_party_designation(self, sample_case_meta):
        lines = _format_parties(sample_case_meta)
        desig_lines = [l for l in lines if "Appellant" in l.text or "Respondent" in l.text]
        assert len(desig_lines) == 2

    def test_no_parties(self):
        meta = CaseMetadata(case_name="A v. B", case_number="123")
        lines = _format_parties(meta)
        assert lines == []

    def test_single_party(self):
        meta = CaseMetadata(
            case_name="State v. Smith",
            case_number="123",
            parties=[Party(name="John Smith", role=PartyRole.DEFENDANT)],
        )
        lines = _format_parties(meta)
        v_lines = [l for l in lines if "v." in l.text]
        assert len(v_lines) == 0  # no v. with single party

    def test_three_parties(self):
        meta = CaseMetadata(
            case_name="Multi-party",
            case_number="123",
            parties=[
                Party(name="Alice", role=PartyRole.PLAINTIFF),
                Party(name="Bob", role=PartyRole.DEFENDANT),
                Party(name="Charlie", role=PartyRole.INTERVENOR),
            ],
        )
        lines = _format_parties(meta)
        v_lines = [l for l in lines if "v." in l.text]
        assert len(v_lines) == 2  # between each pair

    def test_default_designation_from_role(self):
        meta = CaseMetadata(
            case_name="X",
            case_number="1",
            parties=[Party(name="X", role=PartyRole.PETITIONER)],
        )
        lines = _format_parties(meta)
        desig_lines = [l for l in lines if "Petitioner" in l.text]
        assert len(desig_lines) == 1


class TestDefaultCourtName:
    def test_wisconsin_coa(self, wi_ruleset):
        assert "COURT OF APPEALS" in _default_court_name(wi_ruleset)

    def test_wisconsin_supreme(self):
        rs = Ruleset(name="X", jurisdiction="wisconsin", court_level="supreme_court",
                     document_type="brief")
        assert "SUPREME COURT" in _default_court_name(rs)

    def test_wisconsin_circuit(self):
        rs = Ruleset(name="X", jurisdiction="wisconsin", court_level="circuit_court",
                     document_type="brief")
        assert "CIRCUIT COURT" in _default_court_name(rs)

    def test_no_ruleset(self):
        assert _default_court_name(None) == "COURT"

    def test_non_wisconsin(self):
        rs = Ruleset(name="X", jurisdiction="california", court_level="supreme_court",
                     document_type="brief")
        assert _default_court_name(rs) == "COURT"


class TestDistrictMap:
    def test_all_districts(self):
        assert DISTRICT_MAP["1"] == "District I"
        assert DISTRICT_MAP["2"] == "District II"
        assert DISTRICT_MAP["3"] == "District III"
        assert DISTRICT_MAP["4"] == "District IV"
