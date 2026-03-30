"""Tests for the base scraper infrastructure."""

import pytest

from legal_format_engine.scraper.base import classify_domain, BaseScraper
from legal_format_engine.scraper.models import SourceTier


class TestDomainClassification:
    """Test automatic source tier classification."""

    def test_official_gov_domain(self):
        assert classify_domain("https://wicourts.gov/efiling") == SourceTier.OFFICIAL
        assert classify_domain("https://www.uscourts.gov/rules") == SourceTier.OFFICIAL
        assert classify_domain("https://courts.ca.gov/page") == SourceTier.OFFICIAL

    def test_official_state_courts(self):
        assert classify_domain("https://www.courts.state.ny.us/x") == SourceTier.OFFICIAL
        assert classify_domain("https://www.txcourts.gov/rules") == SourceTier.OFFICIAL

    def test_quasi_official_tyler(self):
        assert classify_domain("https://efilinghelp.zendesk.com/article") == SourceTier.QUASI_OFFICIAL

    def test_secondary_legal_publishers(self):
        assert classify_domain("https://www.justia.com/courts") == SourceTier.SECONDARY
        assert classify_domain("https://law.cornell.edu/rules") == SourceTier.SECONDARY

    def test_tertiary_unknown(self):
        assert classify_domain("https://random-blog.com/courts") == SourceTier.TERTIARY
        assert classify_domain("https://example.com/legal") == SourceTier.TERTIARY

    def test_bar_associations_quasi_official(self):
        assert classify_domain("https://wisbar.org/rules") == SourceTier.QUASI_OFFICIAL


class TestBaseScraperSourceAssessment:
    """Test BaseScraper's source assessment."""

    @pytest.mark.asyncio
    async def test_assess_official_source(self):
        from legal_format_engine.scraper.models import ScrapedPage
        async with BaseScraper() as scraper:
            page = ScrapedPage(
                url="https://wicourts.gov/efiling",
                domain="wicourts.gov",
                http_status=200,
            )
            rel = scraper.assess_source("https://wicourts.gov/efiling", page)
            assert rel.tier == SourceTier.OFFICIAL
            assert rel.authority == 1.0
            assert rel.purpose == 1.0

    @pytest.mark.asyncio
    async def test_assess_tertiary_source(self):
        from legal_format_engine.scraper.models import ScrapedPage
        async with BaseScraper() as scraper:
            page = ScrapedPage(
                url="https://blog.example.com/courts",
                domain="blog.example.com",
                http_status=200,
            )
            rel = scraper.assess_source("https://blog.example.com/courts", page)
            assert rel.tier == SourceTier.TERTIARY
            assert rel.authority == 0.15
