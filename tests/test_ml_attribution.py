"""Tests for ml/attribution.py."""

from __future__ import annotations

import pytest

from legal_format_engine.ml.attribution import (
    Attribution,
    _detect_from_certification,
    _detect_from_header,
    _detect_from_signature,
    detect_attribution,
    detect_from_docx_metadata,
)


class TestDetectAttribution:
    def test_from_signature_block(self):
        text = """
        ARGUMENT

        The court should reverse.

        CONCLUSION

        For the foregoing reasons, reverse.

        Respectfully submitted,

        Electronically signed by John Smith
        _________________________
        John Smith
        Bar No. 1012345
        Kirkland & Ellis LLP
        300 N LaSalle
        Chicago, IL 60654
        Phone: (312) 555-1234
        """
        result = detect_attribution(text)
        assert result.author == "John Smith"
        assert result.firm is not None
        assert "Kirkland" in result.firm

    def test_from_slash_s_signature(self):
        text = """
        Respectfully submitted,

        /s/ Jane Doe
        _________________________
        Jane Doe
        Smith & Smith LLP
        """
        result = detect_attribution(text)
        assert result.author == "Jane Doe"

    def test_from_certification(self):
        text = """
        Some text.

        CERTIFICATE OF SERVICE

        I hereby certify that I served this document.
        Baker McKenzie LLP
        Bar No. 999999
        """
        result = detect_attribution(text)
        assert result.firm is not None or result.bar_number is not None

    def test_from_header(self):
        text = "Quinn Emanuel Urquhart & Sullivan LLP\n123 Main St\nNew York, NY\n\nIN THE SUPREME COURT"
        result = detect_attribution(text)
        assert result.firm is not None
        assert "Quinn" in result.firm

    def test_no_attribution(self):
        text = "This is plain text with no signatures or firm names at all."
        result = detect_attribution(text)
        assert result.author is None
        assert result.firm is None

    def test_empty_text(self):
        result = detect_attribution("")
        assert result.author is None


class TestDetectFromSignature:
    def test_electronic_signature(self):
        text = "Respectfully submitted,\n\nElectronically signed by Alice Advocate\nFoley & Lardner LLP"
        result = _detect_from_signature(text)
        assert result.author == "Alice Advocate"
        assert result.confidence >= 0.8

    def test_bar_number(self):
        text = "Respectfully submitted,\n\nElectronically signed by Alice\nBar No. 123456\nSmith LLP"
        result = _detect_from_signature(text)
        assert result.bar_number == "123456"

    def test_no_match(self):
        text = "Just some regular text."
        result = _detect_from_signature(text)
        assert result.author is None

    def test_source_field(self):
        text = "Respectfully submitted,\n\nElectronically signed by X\nSmith LLP"
        result = _detect_from_signature(text)
        assert result.source == "signature_block"


class TestDetectFromCertification:
    def test_cert_of_service(self):
        text = """
        CERTIFICATE OF SERVICE
        I certify that this was served.
        Bar No. 999
        Quarles & Brady LLP
        """
        result = _detect_from_certification(text)
        assert result.source == "certification"

    def test_no_cert(self):
        result = _detect_from_certification("Regular text")
        assert result.firm is None


class TestDetectFromHeader:
    def test_firm_in_header(self):
        text = "Michael Best & Friedrich LLP\n123 E Wisconsin Ave\nMilwaukee, WI\n\nBody text"
        result = _detect_from_header(text)
        assert result.firm is not None
        assert result.source == "header"
        assert result.confidence == 0.5

    def test_no_firm_in_header(self):
        text = "IN THE COURT OF APPEALS\nState of Wisconsin\nDistrict I"
        result = _detect_from_header(text)
        assert result.firm is None


class TestDetectFromDocxMetadata:
    def test_author_and_company(self):
        result = detect_from_docx_metadata({"author": "Jane Doe", "company": "Foley & Lardner LLP"})
        assert result.author == "Jane Doe"
        assert result.firm == "Foley & Lardner LLP"
        assert result.source == "docx_metadata"
        assert result.confidence == 0.7

    def test_empty_metadata(self):
        result = detect_from_docx_metadata({})
        assert result.author is None
        assert result.firm is None


class TestAttribution:
    def test_defaults(self):
        a = Attribution()
        assert a.author is None
        assert a.firm is None
        assert a.bar_number is None
        assert a.source == ""
        assert a.confidence == 0.0


class TestFirmSuffixDetection:
    @pytest.mark.parametrize("text", [
        "Foley & Lardner LLP",
        "Smith Law Firm",
        "Johnson and Associates",
        "Legal Aid Society P.C.",
        "Public Defender PLLC",
        "Davis Law Office",
        "Brown Attorneys at Law",
        "Smith Law Group",
    ])
    def test_recognizes_firm_suffixes(self, text):
        full_text = f"Respectfully submitted,\n\nElectronically signed by Jane\n{text}"
        result = _detect_from_signature(full_text)
        assert result.firm is not None
