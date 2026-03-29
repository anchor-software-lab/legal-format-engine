"""Tests for boilerplate generation engine."""

from legal_format_engine.engines.boilerplate_engine import (
    generate_certifications,
    generate_signature_block,
)


class TestSignatureBlock:
    def test_generates(self, sample_metadata):
        sig = generate_signature_block(sample_metadata)
        assert sig.attorney_name == "Nicholas Smith"
        assert sig.bar_number == "1234567"
        assert sig.firm == "Smith Law Office"
        assert sig.email == "nick@smithlaw.com"


class TestCertifications:
    def test_generates_all(self, sample_metadata, wi_appellate_ruleset):
        certs = generate_certifications(
            sample_metadata,
            wi_appellate_ruleset.certifications,
            word_count=8500,
        )
        assert len(certs) == len(wi_appellate_ruleset.certifications)

    def test_word_count_substitution(self, sample_metadata, wi_appellate_ruleset):
        certs = generate_certifications(
            sample_metadata,
            wi_appellate_ruleset.certifications,
            word_count=8500,
        )
        form_cert = next(c for c in certs if c.id == "form_and_length")
        assert "8500" in form_cert.content[0].text

    def test_placeholder_when_no_word_count(self, sample_metadata, wi_appellate_ruleset):
        certs = generate_certifications(
            sample_metadata,
            wi_appellate_ruleset.certifications,
        )
        form_cert = next(c for c in certs if c.id == "form_and_length")
        assert "[WORD COUNT]" in form_cert.content[0].text

    def test_headings_uppercase(self, sample_metadata, wi_appellate_ruleset):
        certs = generate_certifications(
            sample_metadata, wi_appellate_ruleset.certifications
        )
        for cert in certs:
            assert cert.heading_text == cert.heading_text.upper()
            assert cert.is_generated is True
