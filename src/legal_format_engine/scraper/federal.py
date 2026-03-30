"""Federal courts e-filing requirements scraper.

Scrapes formatting requirements from:
1. United States Courts (uscourts.gov) - OFFICIAL
2. PACER/CM/ECF documentation - OFFICIAL

Federal courts use the CM/ECF (Case Management/Electronic Case Files)
system administered by the Administrative Office of the US Courts.
Individual district courts may have local rules that supplement the
Federal Rules of Civil/Criminal Procedure.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from legal_format_engine.scraper.assessor import ReliabilityAssessor
from legal_format_engine.scraper.base import BaseScraper
from legal_format_engine.scraper.models import (
    CourtLevel,
    CourtSystem,
    EFilingRequirement,
    JurisdictionProfile,
    SourceReliability,
)

logger = logging.getLogger(__name__)

# Federal court e-filing URLs
_USCOURTS_EFILING = "https://www.uscourts.gov/court-records/electronic-filing-cmecf"
_USCOURTS_RULES = "https://www.uscourts.gov/rules-policies/current-rules-practice-procedure"

# Common formatting patterns in federal court documents
_PDF_REQUIREMENT = re.compile(
    r"(?:PDF|pdf)\s*(?:format|file|document)", re.IGNORECASE
)
_FILE_SIZE_PATTERN = re.compile(
    r"(\d+)\s*(?:MB|megabyte|mega[\s-]?byte)", re.IGNORECASE
)
_PAGE_LIMIT_PATTERN = re.compile(
    r"(\d+)[\s-]*page\s*(?:limit|maximum)", re.IGNORECASE
)


class FederalScraper(BaseScraper):
    """Scraper for federal court e-filing requirements (CM/ECF).

    Usage::

        async with FederalScraper() as scraper:
            profile = await scraper.scrape_all()
    """

    JURISDICTION = "US-FED"
    JURISDICTION_NAME = "United States Federal Courts"

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._assessor = ReliabilityAssessor()

    async def scrape_all(self) -> JurisdictionProfile:
        """Scrape federal court e-filing requirements."""
        profile = JurisdictionProfile(
            jurisdiction=self.JURISDICTION,
            jurisdiction_name=self.JURISDICTION_NAME,
        )

        federal_system = CourtSystem(
            name="Federal District Courts (CM/ECF)",
            jurisdiction=self.JURISDICTION,
            level=CourtLevel.DISTRICT,
            parent_system="United States Courts",
            efiling_portal_url="https://pacer.uscourts.gov",
            efiling_vendor="Administrative Office of the US Courts",
            efiling_system_name="CM/ECF",
        )
        profile.courts.append(federal_system)

        await self._scrape_uscourts_efiling(profile, federal_system)
        await self._scrape_uscourts_rules(profile, federal_system)

        # Cross-reference
        for req in profile.requirements:
            self._assessor.cross_reference(req, profile.requirements)

        profile.official_source_count = sum(
            1 for page in self.scrape_log
            if page.domain.endswith(".gov")
        )

        return profile

    async def _scrape_uscourts_efiling(
        self,
        profile: JurisdictionProfile,
        court: CourtSystem,
    ) -> None:
        """Scrape the main CM/ECF information page."""
        url = _USCOURTS_EFILING
        try:
            page = await self.fetch(url)
        except (ValueError, ConnectionError) as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return

        if page.http_status != 200:
            return

        soup = self.parse(page)
        reliability = self.assess_source(url, page)
        text = soup.get_text(separator="\n", strip=True)
        reliability = self._assessor.assess_page(
            reliability, text, page.last_modified
        )

        court.requirements_urls.append(url)
        self._extract_cmecf_requirements(soup, url, reliability, profile, court)

    async def _scrape_uscourts_rules(
        self,
        profile: JurisdictionProfile,
        court: CourtSystem,
    ) -> None:
        """Scrape the federal rules page for formatting requirements."""
        url = _USCOURTS_RULES
        try:
            page = await self.fetch(url)
        except (ValueError, ConnectionError) as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return

        if page.http_status != 200:
            return

        soup = self.parse(page)
        reliability = self.assess_source(url, page)
        text = soup.get_text(separator="\n", strip=True)
        reliability = self._assessor.assess_page(
            reliability, text, page.last_modified
        )

        court.requirements_urls.append(url)
        self._extract_rules_requirements(soup, url, reliability, profile, court)

    def _extract_cmecf_requirements(
        self,
        soup: BeautifulSoup,
        source_url: str,
        reliability: SourceReliability,
        profile: JurisdictionProfile,
        court: CourtSystem,
    ) -> None:
        """Extract CM/ECF-specific requirements."""
        text = soup.get_text(separator="\n", strip=True)
        text_lower = text.lower()

        # PDF format requirement (standard for CM/ECF)
        if _PDF_REQUIREMENT.search(text):
            req = EFilingRequirement(
                court_system_id=court.id,
                jurisdiction=self.JURISDICTION,
                category="file_format",
                field="file_format",
                value=".pdf",
                condition=None,
                description="CM/ECF requires documents in PDF format",
                mandatory=True,
                source_url=source_url,
                source_text=self._find_surrounding_text(text, "pdf", window=200),
                reliability=reliability,
            )
            profile.add_requirement(req)

        # File size limits
        size_match = _FILE_SIZE_PATTERN.search(text)
        if size_match:
            size_mb = int(size_match.group(1))
            req = EFilingRequirement(
                court_system_id=court.id,
                jurisdiction=self.JURISDICTION,
                category="general",
                field="max_file_size_mb",
                value=size_mb,
                condition=None,
                description=f"Maximum file size: {size_mb} MB per document",
                mandatory=True,
                source_url=source_url,
                source_text=self._find_surrounding_text(text, f"{size_mb}", window=150),
                reliability=reliability,
            )
            profile.add_requirement(req)

        # Text-searchable PDF requirement
        if "text-searchable" in text_lower or "searchable pdf" in text_lower:
            req = EFilingRequirement(
                court_system_id=court.id,
                jurisdiction=self.JURISDICTION,
                category="file_format",
                field="pdf_searchable",
                value=True,
                condition=None,
                description="PDFs must be text-searchable (not scanned images)",
                mandatory=True,
                source_url=source_url,
                source_text=self._find_surrounding_text(text, "searchable", window=200),
                reliability=reliability,
            )
            profile.add_requirement(req)

        # PACER/CM/ECF registration requirement
        if "register" in text_lower and "cm/ecf" in text_lower:
            req = EFilingRequirement(
                court_system_id=court.id,
                jurisdiction=self.JURISDICTION,
                category="general",
                field="registration_required",
                value=True,
                condition=None,
                description="Attorney must be registered with CM/ECF to e-file",
                mandatory=True,
                source_url=source_url,
                source_text=self._find_surrounding_text(text, "register", window=200),
                reliability=reliability,
            )
            profile.add_requirement(req)

    def _extract_rules_requirements(
        self,
        soup: BeautifulSoup,
        source_url: str,
        reliability: SourceReliability,
        profile: JurisdictionProfile,
        court: CourtSystem,
    ) -> None:
        """Extract formatting requirements from federal rules page."""
        text = soup.get_text(separator="\n", strip=True)

        # Links to specific rule documents
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"]
            link_text = link.get_text(strip=True).lower()
            if any(
                term in link_text
                for term in ["civil", "criminal", "appellate", "bankruptcy"]
            ) and any(
                term in link_text
                for term in ["rule", "procedure"]
            ):
                if href.startswith("/"):
                    href = f"https://www.uscourts.gov{href}"
                if href not in court.requirements_urls:
                    court.requirements_urls.append(href)
                    logger.info("Found federal rules link: %s", href)

    @staticmethod
    def _find_surrounding_text(full_text: str, needle: str, window: int = 200) -> str:
        """Extract text surrounding a matched term."""
        idx = full_text.lower().find(needle.lower())
        if idx == -1:
            return ""
        start = max(0, idx - window // 2)
        end = min(len(full_text), idx + len(needle) + window // 2)
        excerpt = full_text[start:end].strip()
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(full_text):
            excerpt = excerpt + "..."
        return excerpt
