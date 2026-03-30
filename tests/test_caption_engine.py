"""Tests for caption generation engine."""

from legal_format_engine.engines.caption_engine import generate_caption
from legal_format_engine.models.document import Alignment


class TestCaptionEngine:
    def test_generates_caption(self, sample_metadata, wi_appellate_ruleset):
        caption = generate_caption(sample_metadata, wi_appellate_ruleset.caption_rule)
        assert caption is not None
        assert len(caption.lines) > 0

    def test_court_name_uppercase(self, sample_metadata, wi_appellate_ruleset):
        caption = generate_caption(sample_metadata, wi_appellate_ruleset.caption_rule)
        court_line = caption.lines[0]
        assert court_line.text == "COURT OF APPEALS OF WISCONSIN"
        assert court_line.bold is True

    def test_includes_district(self, sample_metadata, wi_appellate_ruleset):
        caption = generate_caption(sample_metadata, wi_appellate_ruleset.caption_rule)
        texts = [line.text for line in caption.lines]
        assert "DISTRICT II" in texts

    def test_includes_case_number(self, sample_metadata, wi_appellate_ruleset):
        caption = generate_caption(sample_metadata, wi_appellate_ruleset.caption_rule)
        texts = [line.text for line in caption.lines]
        assert any("2024AP001234-CR" in t for t in texts)

    def test_includes_parties(self, sample_metadata, wi_appellate_ruleset):
        caption = generate_caption(sample_metadata, wi_appellate_ruleset.caption_rule)
        texts = [line.text for line in caption.lines]
        assert any("STATE OF WISCONSIN" in t for t in texts)
        assert any("JOHN A. CHRISTOPHERSON" in t for t in texts)

    def test_includes_document_title(self, sample_metadata, wi_appellate_ruleset):
        caption = generate_caption(sample_metadata, wi_appellate_ruleset.caption_rule)
        texts = [line.text for line in caption.lines]
        assert any("BRIEF OF DEFENDANT-APPELLANT" in t for t in texts)

    def test_separator(self, sample_metadata, wi_appellate_ruleset):
        caption = generate_caption(sample_metadata, wi_appellate_ruleset.caption_rule)
        texts = [line.text for line in caption.lines]
        assert "v." in texts
