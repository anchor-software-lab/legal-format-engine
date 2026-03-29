"""Tests for the attribution detection module."""

import pytest

from legal_format_engine.ml.attribution import (
    AttributionDetector,
    DetectedAttribution,
)


@pytest.fixture
def detector():
    return AttributionDetector()


# ── Signature block detection ─────────────────────────────────────────


class TestSignatureBlock:
    def test_respectfully_submitted_basic(self, detector):
        text = """
ARGUMENT

The trial court erred in granting summary judgment.

Respectfully submitted,

John A. Smith
Baker & McKenzie, LLP
123 Main Street
Chicago, IL 60601
(312) 555-1234
jsmith@bakermckenzie.com
State Bar No. 123456

Attorney for Defendant-Appellant
"""
        result = detector.detect_from_text(text)
        assert result.author == "John A. Smith"
        assert result.firm == "Baker & McKenzie, LLP"
        assert result.bar_number == "123456"
        assert "signature_block" in result.sources
        assert result.author_confidence >= 0.8

    def test_electronically_signed(self, detector):
        text = """
CONCLUSION

For the foregoing reasons, the judgment should be reversed.

Electronically signed by Jane R. Doe
Williams & Connolly, LLP
725 Twelfth Street, NW
Washington, DC 20005
Bar No. 987654
"""
        result = detector.detect_from_text(text)
        assert result.author == "Jane R. Doe"
        assert result.firm == "Williams & Connolly, LLP"
        assert result.bar_number == "987654"

    def test_slash_s_signature(self, detector):
        text = """
Respectfully submitted,

/s/ Robert J. Martinez
Martinez Law Group
456 Oak Avenue
Austin, TX 78701
State Bar No. 24098765
"""
        result = detector.detect_from_text(text)
        assert result.author == "Robert J. Martinez"
        assert "Martinez Law Group" in result.firm
        assert result.bar_number == "24098765"

    def test_all_caps_attorney_name(self, detector):
        text = """
Respectfully submitted,

THOMAS P. WILSON
Wilson & Associates, P.C.
789 Pine Road
Denver, CO 80202
"""
        result = detector.detect_from_text(text)
        assert result.author == "Thomas P. Wilson"  # normalized from ALL CAPS
        assert "Wilson & Associates" in result.firm

    def test_esquire_suffix(self, detector):
        text = """
Respectfully submitted,

Sarah L. Johnson, Esq.
Johnson & Partners, PLLC
State Bar No. 55555
"""
        result = detector.detect_from_text(text)
        assert result.author == "Sarah L. Johnson"
        assert "PLLC" in result.firm
        assert result.bar_number == "55555"

    def test_multiple_attorneys_picks_first(self, detector):
        text = """
Respectfully submitted,

Michael D. Brown
David R. Green
Anderson & Brown, LLP
State Bar No. 11111
"""
        result = detector.detect_from_text(text)
        # First attorney should be picked as primary
        assert result.author == "Michael D. Brown"
        assert result.firm == "Anderson & Brown, LLP"

    def test_wsba_number(self, detector):
        text = """
Respectfully submitted,

Patricia K. Lee
Lee Legal Services, LLC
WSBA No. 45678
"""
        result = detector.detect_from_text(text)
        assert result.bar_number == "45678"


# ── Letterhead detection ─────────────────────────────────────────────


class TestLetterhead:
    def test_firm_in_first_lines(self, detector):
        text = """Kirkland & Ellis, LLP
300 North LaSalle
Chicago, IL 60654
(312) 862-2000

IN THE UNITED STATES DISTRICT COURT
FOR THE NORTHERN DISTRICT OF ILLINOIS
"""
        result = detector.detect_from_text(text)
        assert result.firm == "Kirkland & Ellis, LLP"
        assert "letterhead" in result.sources

    def test_law_offices_pattern(self, detector):
        text = """Law Offices of James T. Walker
Bar No. 112233
100 Broadway, Suite 500
New York, NY 10005

SUPREME COURT OF THE STATE OF NEW YORK
"""
        result = detector.detect_from_text(text)
        assert "Law Offices of James T. Walker" in result.firm
        assert result.bar_number == "112233"

    def test_law_firm_pattern(self, detector):
        text = """Henderson Law Firm
200 Court Street
Memphis, TN 38103

IN THE CIRCUIT COURT
"""
        result = detector.detect_from_text(text)
        assert "Henderson Law Firm" in result.firm

    def test_associates_pattern(self, detector):
        text = """Garcia & Associates
Suite 1200
555 Market Street
San Francisco, CA 94105
"""
        result = detector.detect_from_text(text)
        assert "Garcia & Associates" in result.firm


# ── Certificate of service ───────────────────────────────────────────


class TestCertificateOfService:
    def test_i_certify_pattern(self, detector):
        text = """
ARGUMENT

Some legal argument here.

Certificate of Service

I, Alexandra M. Chen, hereby certify that on this 15th day of March, 2026,
I caused a copy of the foregoing to be served upon all counsel of record.

/s/ Alexandra M. Chen
Chen & Associates
"""
        result = detector.detect_from_text(text)
        assert result.author == "Alexandra M. Chen"
        assert "certificate_of_service" in result.sources

    def test_cert_with_firm(self, detector):
        text = """
Certificate of Service

I hereby certify that the foregoing was served electronically.

/s/ William F. Roberts
Roberts & Smith, LLP
State Bar No. 99999
"""
        result = detector.detect_from_text(text)
        assert result.author == "William F. Roberts"
        assert result.firm == "Roberts & Smith, LLP"
        assert result.bar_number == "99999"


# ── Caption attorney identification ──────────────────────────────────


class TestCaptionAttorney:
    def test_attorney_for_line(self, detector):
        text = """
IN THE SUPREME COURT OF WISCONSIN

Case No. 2025AP001234

STATE OF WISCONSIN,
    Plaintiff-Respondent,

v.

JOHN DOE,
    Defendant-Appellant.

Emily R. Parker
Parker Legal, P.C.
Bar No. 77777
Attorney for Defendant-Appellant

BRIEF OF DEFENDANT-APPELLANT
"""
        result = detector.detect_from_text(text)
        assert result.author == "Emily R. Parker"
        assert "Parker Legal" in result.firm


# ── Name normalization ───────────────────────────────────────────────


class TestNormalization:
    def test_normalize_all_caps_name(self, detector):
        assert detector._normalize_attorney_name("JOHN SMITH") == "John Smith"

    def test_normalize_esquire(self, detector):
        assert detector._normalize_attorney_name("John Smith, Esq.") == "John Smith"

    def test_normalize_slash_s_prefix(self, detector):
        assert detector._normalize_attorney_name("/s/ John Smith") == "John Smith"

    def test_normalize_by_prefix(self, detector):
        assert detector._normalize_attorney_name("By: John Smith") == "John Smith"

    def test_normalize_firm_trailing_comma(self, detector):
        assert detector._normalize_firm_name("Baker McKenzie,") == "Baker McKenzie"

    def test_normalize_firm_by_prefix(self, detector):
        assert detector._normalize_firm_name("By: Baker McKenzie LLP") == "Baker McKenzie LLP"

    def test_normalize_firm_whitespace(self, detector):
        assert detector._normalize_firm_name("  Baker   McKenzie  LLP  ") == "Baker McKenzie LLP"


# ── Name-like heuristic ─────────────────────────────────────────────


class TestLooksLikeAttorneyName:
    def test_simple_name(self, detector):
        assert detector._looks_like_attorney_name("John A. Smith") is True

    def test_name_with_esquire(self, detector):
        assert detector._looks_like_attorney_name("John Smith, Esq.") is True

    def test_rejects_email(self, detector):
        assert detector._looks_like_attorney_name("john@example.com") is False

    def test_rejects_phone(self, detector):
        assert detector._looks_like_attorney_name("(312) 555-1234") is False

    def test_rejects_address(self, detector):
        assert detector._looks_like_attorney_name("Chicago, IL 60601") is False

    def test_rejects_firm_name(self, detector):
        assert detector._looks_like_attorney_name("Baker McKenzie, LLP") is False

    def test_rejects_heading(self, detector):
        assert detector._looks_like_attorney_name("ARGUMENT") is False

    def test_rejects_bar_number_line(self, detector):
        assert detector._looks_like_attorney_name("State Bar No. 12345") is False

    def test_rejects_sentence(self, detector):
        assert detector._looks_like_attorney_name("The Court Should Reverse The Judgment Of The Lower Court") is False

    def test_rejects_single_word(self, detector):
        assert detector._looks_like_attorney_name("Smith") is False


# ── Bar number patterns ──────────────────────────────────────────────


class TestBarNumberPatterns:
    def test_state_bar_no(self, detector):
        text = "Respectfully submitted,\n\nJane Doe\nState Bar No. 123456"
        result = detector.detect_from_text(text)
        assert result.bar_number == "123456"

    def test_bar_no_colon(self, detector):
        text = "Respectfully submitted,\n\nJane Doe\nBar No.: 789012"
        result = detector.detect_from_text(text)
        assert result.bar_number == "789012"

    def test_wsba_no(self, detector):
        text = "Respectfully submitted,\n\nJane Doe\nWSBA No. 45678"
        result = detector.detect_from_text(text)
        assert result.bar_number == "45678"

    def test_sbn(self, detector):
        text = "Respectfully submitted,\n\nJane Doe\nSBN 334455"
        result = detector.detect_from_text(text)
        assert result.bar_number == "334455"


# ── Confidence scoring ───────────────────────────────────────────────


class TestConfidence:
    def test_signature_block_high_confidence(self, detector):
        text = """
Respectfully submitted,

John Smith
Smith & Jones, LLP
State Bar No. 11111
"""
        result = detector.detect_from_text(text)
        assert result.author_confidence >= 0.8
        assert result.firm_confidence >= 0.8

    def test_letterhead_only_moderate_confidence(self, detector):
        text = """Smith & Jones, LLP
100 Main Street
Anytown, US 12345

IN THE COURT OF COMMON PLEAS

Some argument text here.
"""
        result = detector.detect_from_text(text)
        assert result.firm_confidence >= 0.5
        assert result.firm_confidence < 0.9

    def test_no_attribution_zero_confidence(self, detector):
        text = """
IN THE SUPREME COURT

ARGUMENT

The trial court erred.
"""
        result = detector.detect_from_text(text)
        assert result.author_confidence == 0.0
        assert result.firm_confidence == 0.0


# ── Multiple sources corroboration ───────────────────────────────────


class TestCorroboration:
    def test_signature_and_cert_corroborate(self, detector):
        text = """
ARGUMENT

The judgment should be reversed.

Respectfully submitted,

Maria L. Garcia
Garcia & Partners, LLP
State Bar No. 55555

Attorney for Appellant

Certificate of Service

I, Maria L. Garcia, hereby certify that on March 15, 2026,
I served the foregoing on all parties.

/s/ Maria L. Garcia
"""
        result = detector.detect_from_text(text)
        assert result.author == "Maria L. Garcia"
        assert "signature_block" in result.sources
        assert "certificate_of_service" in result.sources


# ── Edge cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_text(self, detector):
        result = detector.detect_from_text("")
        assert result.author is None
        assert result.firm is None
        assert result.sources == []

    def test_no_signature_block(self, detector):
        text = "This is a simple document with no legal formatting at all."
        result = detector.detect_from_text(text)
        assert result.author is None

    def test_unsupported_file_extension(self, detector, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("Some text")
        result = detector.detect(f)
        assert isinstance(result, DetectedAttribution)

    def test_nonexistent_file(self, detector, tmp_path):
        f = tmp_path / "nonexistent.docx"
        result = detector.detect(f)
        assert isinstance(result, DetectedAttribution)
        assert result.author is None

    def test_detect_routes_to_pdf(self, detector, tmp_path):
        """detect() routes .pdf files to detect_from_pdf()."""
        # We can't easily create a real PDF in a unit test, but we can
        # verify that a nonexistent PDF returns gracefully.
        f = tmp_path / "test.pdf"
        result = detector.detect(f)
        assert isinstance(result, DetectedAttribution)


# ── DetectedAttribution dataclass ────────────────────────────────────


class TestDetectedAttribution:
    def test_defaults(self):
        attr = DetectedAttribution()
        assert attr.author is None
        assert attr.firm is None
        assert attr.bar_number is None
        assert attr.author_confidence == 0.0
        assert attr.firm_confidence == 0.0
        assert attr.sources == []

    def test_custom_values(self):
        attr = DetectedAttribution(
            author="John Doe",
            firm="Doe & Associates",
            bar_number="12345",
            author_confidence=0.9,
            firm_confidence=0.8,
            sources=["signature_block", "metadata"],
        )
        assert attr.author == "John Doe"
        assert attr.firm == "Doe & Associates"
        assert attr.bar_number == "12345"
        assert len(attr.sources) == 2
