"""Wisconsin court e-filing requirements scraper.

Scrapes formatting requirements from:
1. Wisconsin Court System (wicourts.gov) - OFFICIAL
2. Tyler Technologies e-filing help portal (efilinghelp.zendesk.com) - QUASI-OFFICIAL

Wisconsin uses the Tyler Technologies Odyssey File & Serve system for
e-filing across all circuit courts, the Court of Appeals, and the
Supreme Court.

Known requirements (from Dunnington session, Forest County 2024):
- Proposed orders: 3" top margin, .docx format, no judge signature block
- Source: https://efilinghelp.zendesk.com/hc/en-us/articles/25044580029965
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

# Wisconsin-specific URLs
_WI_EFILING_HELP = "https://efilinghelp.zendesk.com/hc/en-us/articles/25044580029965"
_WI_CIRCUIT_EFILING = "https://www.wicourts.gov/ecourts/efilecircuit.htm"
_WI_CIRCUIT_TECH = "https://www.wicourts.gov/ecourts/efilecircuit/tech.htm"
_WI_APPELLATE_EFILING = "https://www.wicourts.gov/ecourts/efileappellate.htm"

# Wisconsin-specific known requirements (from official sources, Wis. Stat. s. 801.18)
# These serve as baseline values when scraping confirms them.
_WI_KNOWN_REQUIREMENTS = {
    # All documents
    "header_margin_top_inches": 0.5,  # blank top for court-applied header
    "file_stamp_width_inches": 2.0,   # upper-right blank square
    "file_stamp_height_inches": 2.0,
    "max_file_size_mb": 50,
    "max_page_width_inches": 12,
    "max_page_height_inches": 18,
    "scan_dpi": 300,
    # Proposed orders
    "proposed_order_margin_top_inches": 3.0,
    # Accepted fonts
    "accepted_fonts": [
        "Arial", "Calibri", "Cambria", "Geneva",
        "Tahoma", "Times", "Times New Roman",
    ],
    "font_size_pt": 12,
}

# Patterns for extracting requirements from Wisconsin court pages
_MARGIN_PATTERN = re.compile(
    r"(\d+)[\-\s]*inch\s*(?:top\s*)?margin", re.IGNORECASE
)
_FORMAT_PATTERN = re.compile(
    r"\.?(docx?|pdf|rtf)\s*(?:format|file)", re.IGNORECASE
)
_FONT_PATTERN = re.compile(
    r"(?:font|typeface)[:\s]*([\w\s]+?)(?:\s*(?:\d+|,|$))", re.IGNORECASE
)
_FONT_SIZE_PATTERN = re.compile(
    r"(\d+)\s*(?:pt|point)", re.IGNORECASE
)


class WisconsinScraper(BaseScraper):
    """Scraper for Wisconsin court e-filing requirements.

    Usage::

        async with WisconsinScraper() as scraper:
            profile = await scraper.scrape_all()
            print(profile.requirements)
    """

    JURISDICTION = "WI"
    JURISDICTION_NAME = "Wisconsin"

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._assessor = ReliabilityAssessor()

    async def scrape_all(self) -> JurisdictionProfile:
        """Scrape all known Wisconsin e-filing requirement sources.

        Returns a JurisdictionProfile with all extracted requirements
        and their reliability assessments.
        """
        profile = JurisdictionProfile(
            jurisdiction=self.JURISDICTION,
            jurisdiction_name=self.JURISDICTION_NAME,
        )

        # Define court systems
        circuit_court = CourtSystem(
            name="Wisconsin Circuit Court",
            jurisdiction=self.JURISDICTION,
            state="WI",
            level=CourtLevel.CIRCUIT,
            parent_system="Wisconsin Court System",
            efiling_portal_url="https://efiling.wicourts.gov",
            efiling_vendor="Tyler Technologies",
            efiling_system_name="Odyssey File & Serve",
        )
        profile.courts.append(circuit_court)

        # Scrape each source
        await self._scrape_efiling_help(profile, circuit_court)
        await self._scrape_wicourts_circuit(profile, circuit_court)
        await self._scrape_wicourts_tech(profile, circuit_court)

        # Cross-reference all requirements
        for req in profile.requirements:
            self._assessor.cross_reference(req, profile.requirements)

        # Count official sources
        profile.official_source_count = sum(
            1 for page in self.scrape_log
            if page.domain.endswith(".gov") or page.domain.endswith(".wicourts.gov")
        )

        return profile

    async def _scrape_efiling_help(
        self,
        profile: JurisdictionProfile,
        court: CourtSystem,
    ) -> None:
        """Scrape Tyler Technologies e-filing help portal for WI requirements."""
        url = _WI_EFILING_HELP
        try:
            page = await self.fetch(url)
        except (ValueError, ConnectionError) as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return

        if page.http_status != 200:
            logger.warning("Non-200 status for %s: %d", url, page.http_status)
            return

        soup = self.parse(page)
        reliability = self.assess_source(url, page)
        text = soup.get_text(separator="\n", strip=True)

        # Refine reliability based on content
        reliability = self._assessor.assess_page(
            reliability, text, page.last_modified
        )

        court.requirements_urls.append(url)
        page.requirements_found = 0

        # Extract requirements from the article content
        article = soup.find("article") or soup.find("div", class_="article-body")
        if article is None:
            article = soup  # fallback to full page

        self._extract_proposed_order_requirements(
            article, url, reliability, profile, court
        )
        self._extract_general_requirements(
            article, url, reliability, profile, court
        )

    async def _scrape_wicourts_circuit(
        self,
        profile: JurisdictionProfile,
        court: CourtSystem,
    ) -> None:
        """Scrape official wicourts.gov circuit court e-filing page."""
        url = _WI_CIRCUIT_EFILING
        try:
            page = await self.fetch(url)
        except (ValueError, ConnectionError) as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return

        if page.http_status != 200:
            logger.warning("Non-200 status for %s: %d", url, page.http_status)
            return

        soup = self.parse(page)
        reliability = self.assess_source(url, page)
        text = soup.get_text(separator="\n", strip=True)

        reliability = self._assessor.assess_page(
            reliability, text, page.last_modified
        )

        court.requirements_urls.append(url)

        # Extract links to additional resources and requirements
        self._extract_linked_resources(soup, url, profile, court)
        self._extract_general_requirements(
            soup, url, reliability, profile, court
        )

    async def _scrape_wicourts_tech(
        self,
        profile: JurisdictionProfile,
        court: CourtSystem,
    ) -> None:
        """Scrape official wicourts.gov technical requirements page.

        This is the most authoritative source for Wisconsin e-filing
        formatting requirements (official .gov domain).
        """
        url = _WI_CIRCUIT_TECH
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

        # Extract requirements from the tech page
        self._extract_proposed_order_requirements(
            soup, url, reliability, profile, court
        )
        self._extract_general_requirements(
            soup, url, reliability, profile, court
        )
        self._extract_document_standards(
            soup, url, reliability, profile, court
        )

    def _extract_document_standards(
        self,
        soup: BeautifulSoup,
        source_url: str,
        reliability: SourceReliability,
        profile: JurisdictionProfile,
        court: CourtSystem,
    ) -> None:
        """Extract document standard requirements (header margin, file stamp, etc.)."""
        text = soup.get_text(separator="\n", strip=True)
        text_lower = text.lower()

        # Header margin (1/2-inch top on every page)
        if "1/2" in text_lower and "margin" in text_lower:
            req = EFilingRequirement(
                court_system_id=court.id,
                jurisdiction=self.JURISDICTION,
                category="margin",
                field="header_margin_top_inches",
                value=0.5,
                condition=None,
                description="Blank 1/2-inch top margin on every page for court-applied document header",
                mandatory=True,
                source_url=source_url,
                source_text=self._find_surrounding_text(text, "1/2", window=200),
                reliability=reliability,
            )
            profile.add_requirement(req)

        # File stamp area (2x2 inch upper-right)
        if "2-inch" in text_lower or "file stamp" in text_lower or "upper-right" in text_lower:
            req = EFilingRequirement(
                court_system_id=court.id,
                jurisdiction=self.JURISDICTION,
                category="margin",
                field="file_stamp_area",
                value={"width_inches": 2.0, "height_inches": 2.0, "position": "upper-right"},
                condition=None,
                description="Blank 2x2-inch area in upper-right corner of first page for court file stamp",
                mandatory=True,
                source_url=source_url,
                source_text=self._find_surrounding_text(text, "upper-right", window=200),
                reliability=reliability,
            )
            profile.add_requirement(req)

        # DPI scanning requirement
        if "300" in text and "dpi" in text_lower:
            req = EFilingRequirement(
                court_system_id=court.id,
                jurisdiction=self.JURISDICTION,
                category="general",
                field="scan_dpi",
                value=300,
                condition=None,
                description="Scanned documents must be 300 DPI, black and white preferred",
                mandatory=True,
                source_url=source_url,
                source_text=self._find_surrounding_text(text, "300", window=150),
                reliability=reliability,
            )
            profile.add_requirement(req)

        # No active content
        if "javascript" in text_lower or "macro" in text_lower:
            req = EFilingRequirement(
                court_system_id=court.id,
                jurisdiction=self.JURISDICTION,
                category="general",
                field="no_active_content",
                value=True,
                condition=None,
                description="No JavaScript, macros, document security, or digital signatures in filed documents",
                mandatory=True,
                source_url=source_url,
                source_text=self._find_surrounding_text(text, "javascript", window=200),
                reliability=reliability,
            )
            profile.add_requirement(req)

    def _extract_proposed_order_requirements(
        self,
        soup: BeautifulSoup,
        source_url: str,
        reliability: SourceReliability,
        profile: JurisdictionProfile,
        court: CourtSystem,
    ) -> None:
        """Extract proposed order-specific requirements.

        These are the most critical requirements: formatting rules that
        apply specifically to proposed orders submitted via e-filing.
        """
        text = soup.get_text(separator="\n", strip=True)
        text_lower = text.lower()

        # Look for proposed order section
        if "proposed order" not in text_lower:
            return

        # 3-inch top margin requirement
        margin_matches = _MARGIN_PATTERN.findall(text)
        for match in margin_matches:
            inches = int(match)
            if 1 <= inches <= 5:  # sanity check
                req = EFilingRequirement(
                    court_system_id=court.id,
                    jurisdiction=self.JURISDICTION,
                    category="margin",
                    field="margin_top_inches",
                    value=float(inches),
                    condition="proposed_order",
                    description=f"{inches}-inch top margin required for proposed orders (space for court's digital signature/stamp)",
                    mandatory=True,
                    source_url=source_url,
                    source_text=self._find_surrounding_text(text, f"{inches}", window=200),
                    reliability=reliability,
                )
                profile.add_requirement(req)

        # .docx format requirement
        if ".docx" in text_lower and "proposed order" in text_lower:
            req = EFilingRequirement(
                court_system_id=court.id,
                jurisdiction=self.JURISDICTION,
                category="file_format",
                field="file_format",
                value=".docx",
                condition="proposed_order",
                description="Proposed orders must be submitted in .docx format so the court can edit before signing",
                mandatory=True,
                source_url=source_url,
                source_text=self._find_surrounding_text(text, ".docx", window=200),
                reliability=reliability,
            )
            profile.add_requirement(req)

        # No judge signature block
        if any(
            phrase in text_lower
            for phrase in [
                "no judge signature",
                "do not include a signature",
                "without a signature line for the judge",
                "leave space for",
            ]
        ):
            req = EFilingRequirement(
                court_system_id=court.id,
                jurisdiction=self.JURISDICTION,
                category="signature",
                field="judge_signature_block",
                value=False,
                condition="proposed_order",
                description="Proposed orders must not include a judge signature block; court applies digital signature",
                mandatory=True,
                source_url=source_url,
                source_text=self._find_surrounding_text(text, "signature", window=200),
                reliability=reliability,
            )
            profile.add_requirement(req)

    def _extract_general_requirements(
        self,
        soup: BeautifulSoup,
        source_url: str,
        reliability: SourceReliability,
        profile: JurisdictionProfile,
        court: CourtSystem,
    ) -> None:
        """Extract general e-filing formatting requirements."""
        text = soup.get_text(separator="\n", strip=True)
        text_lower = text.lower()

        # File format requirements (general)
        format_matches = _FORMAT_PATTERN.findall(text)
        for fmt in set(format_matches):
            fmt_lower = fmt.lower()
            if fmt_lower in ("docx", "doc", "pdf", "rtf"):
                req = EFilingRequirement(
                    court_system_id=court.id,
                    jurisdiction=self.JURISDICTION,
                    category="file_format",
                    field=f"accepted_format_{fmt_lower}",
                    value=f".{fmt_lower}",
                    condition=None,
                    description=f".{fmt_lower} files accepted for e-filing",
                    mandatory=False,
                    source_url=source_url,
                    source_text=self._find_surrounding_text(text, f".{fmt_lower}", window=150),
                    reliability=reliability,
                )
                profile.add_requirement(req)

        # Font requirements
        font_matches = _FONT_PATTERN.findall(text)
        for font in font_matches:
            font = font.strip()
            if len(font) > 2 and font.lower() not in ("the", "and", "for", "use"):
                req = EFilingRequirement(
                    court_system_id=court.id,
                    jurisdiction=self.JURISDICTION,
                    category="font",
                    field="font_family",
                    value=font,
                    condition=None,
                    description=f"Font requirement: {font}",
                    mandatory=False,
                    source_url=source_url,
                    source_text=self._find_surrounding_text(text, font, window=150),
                    reliability=reliability,
                )
                profile.add_requirement(req)

        # File size limits
        size_match = re.search(
            r"(\d+)\s*(?:MB|megabyte)", text, re.IGNORECASE
        )
        if size_match:
            size_mb = int(size_match.group(1))
            req = EFilingRequirement(
                court_system_id=court.id,
                jurisdiction=self.JURISDICTION,
                category="general",
                field="max_file_size_mb",
                value=size_mb,
                condition=None,
                description=f"Maximum file size: {size_mb} MB",
                mandatory=True,
                source_url=source_url,
                source_text=self._find_surrounding_text(text, f"{size_mb}", window=150),
                reliability=reliability,
            )
            profile.add_requirement(req)

    def _extract_linked_resources(
        self,
        soup: BeautifulSoup,
        base_url: str,
        profile: JurisdictionProfile,
        court: CourtSystem,
    ) -> None:
        """Find links to additional requirement pages or documents."""
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"]
            text = link.get_text(strip=True).lower()

            # Look for links to formatting guides, rules, etc.
            if any(
                keyword in text
                for keyword in [
                    "format", "requirement", "guide", "rule",
                    "e-filing", "efiling", "instruction",
                ]
            ):
                # Resolve relative URLs
                if href.startswith("/"):
                    from urllib.parse import urlparse
                    parsed = urlparse(base_url)
                    href = f"{parsed.scheme}://{parsed.netloc}{href}"

                if href not in court.requirements_urls:
                    court.requirements_urls.append(href)
                    logger.info("Found linked resource: %s (%s)", href, text)

    @staticmethod
    def _find_surrounding_text(full_text: str, needle: str, window: int = 200) -> str:
        """Extract text surrounding a matched term for provenance tracking."""
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
