"""Tests for the attribution module."""

import pytest
from anchor_ml_engine.attribution import AttributionDetector


class TestAttributionDetector:
    def setup_method(self):
        self.detector = AttributionDetector()

    def test_detect_from_text_signature_block(self):
        text = """
        ARGUMENT

        The defendant argues that...

        Respectfully submitted,

        /s/ John A. Smith
        Smith & Associates, LLP
        123 Main Street
        Madison, WI 53703
        (608) 555-1234
        jsmith@smithlaw.com
        State Bar No. 1234567
        Attorney for Defendant-Appellant
        """
        result = self.detector.detect_from_text(text)
        assert result.author == "John A. Smith"
        assert result.organization == "Smith & Associates, LLP"
        assert result.identifier == "1234567"
        assert result.author_confidence > 0.5

    def test_detect_from_text_esigned(self):
        text = """
        /s/ Jane B. Doe
        Jones & Doe, P.C.
        State Bar No. 7654321
        """
        result = self.detector.detect_from_text(text)
        assert result.author == "Jane B. Doe"
        assert result.organization == "Jones & Doe, P.C."

    def test_detect_from_text_certificate_of_service(self):
        text = """
        CERTIFICATE OF SERVICE

        I, Michael Johnson, hereby certify that on this date I served
        a copy of the foregoing upon all parties of record.
        """
        result = self.detector.detect_from_text(text)
        assert result.author == "Michael Johnson"

    def test_detect_from_empty_text(self):
        result = self.detector.detect_from_text("")
        assert result.author is None
        assert result.organization is None

    def test_normalize_author_name_all_caps(self):
        result = self.detector._normalize_author_name("JOHN SMITH")
        assert result == "John Smith"

    def test_normalize_author_name_esquire(self):
        result = self.detector._normalize_author_name("John Smith, Esq.")
        assert result == "John Smith"

    def test_normalize_author_name_slash_s(self):
        result = self.detector._normalize_author_name("/s/ John Smith")
        assert result == "John Smith"

    def test_normalize_org_name(self):
        result = self.detector._normalize_org_name("  Smith & Associates, LLP  ")
        assert result == "Smith & Associates, LLP"

    def test_looks_like_author_name_positive(self):
        assert self.detector._looks_like_author_name("John Smith") is True
        assert self.detector._looks_like_author_name("Jane A. Doe") is True
        assert self.detector._looks_like_author_name("John Smith, Esq.") is True

    def test_looks_like_author_name_negative(self):
        assert self.detector._looks_like_author_name("ARGUMENT") is False
        assert self.detector._looks_like_author_name("Smith & Associates, LLP") is False
        assert self.detector._looks_like_author_name("john@email.com") is False
        assert self.detector._looks_like_author_name("(555) 555-1234") is False
        assert self.detector._looks_like_author_name("Madison, WI 53703") is False
        assert self.detector._looks_like_author_name("") is False

    def test_merge_corroborating_results(self):
        primary = self.detector.detect_from_text("")
        primary.author = "John Smith"
        primary.author_confidence = 0.5
        primary.sources = ["metadata"]

        secondary = self.detector.detect_from_text("")
        secondary.author = "John Smith"
        secondary.author_confidence = 0.85
        secondary.sources = ["signature_block"]

        merged = self.detector._merge_results(primary, secondary)
        # Corroboration should boost confidence
        assert merged.author == "John Smith"
        assert merged.author_confidence > 0.85

    def test_merge_conflicting_results(self):
        primary = self.detector.detect_from_text("")
        primary.author = "John Smith"
        primary.author_confidence = 0.5
        primary.sources = ["metadata"]

        secondary = self.detector.detect_from_text("")
        secondary.author = "Jane Doe"
        secondary.author_confidence = 0.85
        secondary.sources = ["signature_block"]

        merged = self.detector._merge_results(primary, secondary)
        # Higher confidence wins
        assert merged.author == "Jane Doe"
        assert merged.author_confidence == 0.85
