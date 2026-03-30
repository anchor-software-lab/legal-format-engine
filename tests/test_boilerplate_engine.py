"""Tests for engines/boilerplate_engine.py."""

from __future__ import annotations

import pytest

from legal_format_engine.engines.boilerplate_engine import (
    generate_certifications,
    generate_signature_block,
)
from legal_format_engine.models.document import Attorney


class TestGenerateSignatureBlock:
    def test_returns_section(self, sample_attorney):
        sig = generate_signature_block(sample_attorney)
        assert sig.section_type == "signature_block"

    def test_respectfully_submitted(self, sample_attorney):
        sig = generate_signature_block(sample_attorney)
        texts = [b.text for b in sig.content]
        assert any("Respectfully submitted" in t for t in texts)

    def test_attorney_name(self, sample_attorney):
        sig = generate_signature_block(sample_attorney)
        texts = [b.text for b in sig.content]
        assert any("Alice Advocate" in t for t in texts)

    def test_bar_number(self, sample_attorney):
        sig = generate_signature_block(sample_attorney)
        texts = [b.text for b in sig.content]
        assert any("1012345" in t for t in texts)

    def test_firm_name(self, sample_attorney):
        sig = generate_signature_block(sample_attorney)
        texts = [b.text for b in sig.content]
        assert any("Smith & Smith LLP" in t for t in texts)

    def test_phone(self, sample_attorney):
        sig = generate_signature_block(sample_attorney)
        texts = [b.text for b in sig.content]
        assert any("555-1234" in t for t in texts)

    def test_email(self, sample_attorney):
        sig = generate_signature_block(sample_attorney)
        texts = [b.text for b in sig.content]
        assert any("alice@smithsmith.com" in t for t in texts)

    def test_date(self, sample_attorney):
        sig = generate_signature_block(sample_attorney, date="March 15, 2025")
        texts = [b.text for b in sig.content]
        assert any("March 15, 2025" in t for t in texts)

    def test_no_date(self, sample_attorney):
        sig = generate_signature_block(sample_attorney)
        texts = [b.text for b in sig.content]
        assert not any("Dated:" in t for t in texts)

    def test_underline_present(self, sample_attorney):
        sig = generate_signature_block(sample_attorney)
        texts = [b.text for b in sig.content]
        assert any("___" in t for t in texts)

    def test_electronic_signature(self, sample_attorney):
        sig = generate_signature_block(sample_attorney)
        texts = [b.text for b in sig.content]
        assert any("Electronically signed by" in t for t in texts)

    def test_multiline_address(self, sample_attorney):
        sig = generate_signature_block(sample_attorney)
        texts = [b.text for b in sig.content]
        assert any("123 Main St" in t for t in texts)
        assert any("Madison, WI 53703" in t for t in texts)

    def test_minimal_attorney(self):
        atty = Attorney(name="Jane Doe")
        sig = generate_signature_block(atty)
        texts = [b.text for b in sig.content]
        assert any("Jane Doe" in t for t in texts)
        assert not any("Bar No." in t for t in texts)


class TestGenerateCertifications:
    def test_returns_list(self, minimal_ruleset, sample_attorney):
        certs = generate_certifications(minimal_ruleset, sample_attorney)
        assert isinstance(certs, list)

    def test_number_of_certs(self, minimal_ruleset, sample_attorney):
        certs = generate_certifications(minimal_ruleset, sample_attorney)
        # minimal_ruleset has 2 required certs
        assert len(certs) == 2

    def test_word_count_substituted(self, minimal_ruleset, sample_attorney):
        certs = generate_certifications(minimal_ruleset, sample_attorney, word_count=8500)
        texts = " ".join(b.text for c in certs for b in c.content)
        assert "8500" in texts

    def test_word_count_placeholder_without_count(self, minimal_ruleset, sample_attorney):
        certs = generate_certifications(minimal_ruleset, sample_attorney)
        texts = " ".join(b.text for c in certs for b in c.content)
        assert "{word_count}" in texts

    def test_cert_section_type(self, minimal_ruleset, sample_attorney):
        certs = generate_certifications(minimal_ruleset, sample_attorney)
        for cert in certs:
            assert cert.section_type.startswith("certification_")

    def test_signature_line_in_cert(self, minimal_ruleset, sample_attorney):
        certs = generate_certifications(minimal_ruleset, sample_attorney)
        for cert in certs:
            texts = [b.text for b in cert.content]
            assert any("___" in t for t in texts)
            assert any("Alice Advocate" in t for t in texts)

    def test_with_wisconsin_ruleset(self, wi_ruleset, sample_attorney):
        certs = generate_certifications(wi_ruleset, sample_attorney, word_count=9000)
        assert len(certs) >= 4  # form_length, e-filing, service, appendix
        texts = " ".join(b.text for c in certs for b in c.content)
        assert "9000" in texts

    def test_skips_non_required(self, sample_attorney):
        from legal_format_engine.models.section import CertificationTemplate, Ruleset, PageFormat
        rs = Ruleset(
            name="X", jurisdiction="x", court_level="x", document_type="x",
            certification_templates=[
                CertificationTemplate(cert_type="optional", template="Optional.", required=False),
                CertificationTemplate(cert_type="required", template="Required.", required=True),
            ],
        )
        certs = generate_certifications(rs, sample_attorney)
        assert len(certs) == 1
        assert certs[0].section_type == "certification_required"
