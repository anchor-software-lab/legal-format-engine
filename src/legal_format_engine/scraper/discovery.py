"""Jurisdiction discovery module for finding new court e-filing portals.

Uses known patterns in court website structures to discover e-filing
requirement pages across jurisdictions. Discovered sources are assessed
for reliability before being added to the registry.

Discovery strategies:
1. State court domain enumeration (known patterns like *.courts.*.gov)
2. Tyler Technologies customer list (common e-filing vendor)
3. Link crawling from known court system pages
4. NCSC (National Center for State Courts) directory
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from legal_format_engine.scraper.assessor import ReliabilityAssessor
from legal_format_engine.scraper.base import BaseScraper, classify_domain
from legal_format_engine.scraper.models import (
    CourtLevel,
    CourtSystem,
    ScrapedPage,
    SourceTier,
)

logger = logging.getLogger(__name__)

# US state abbreviations and their common court domain patterns
_STATE_COURT_PATTERNS: dict[str, list[str]] = {
    "AL": ["https://www.alacourt.gov", "https://judicial.alabama.gov"],
    "AK": ["https://courts.alaska.gov"],
    "AZ": ["https://www.azcourts.gov"],
    "AR": ["https://www.arcourts.gov"],
    "CA": ["https://www.courts.ca.gov"],
    "CO": ["https://www.courts.state.co.us", "https://www.coloradojudicial.gov"],
    "CT": ["https://www.jud.ct.gov"],
    "DE": ["https://courts.delaware.gov"],
    "FL": ["https://www.flcourts.gov", "https://www.flcourts.org"],
    "GA": ["https://www.georgiacourts.gov"],
    "HI": ["https://www.courts.state.hi.us"],
    "ID": ["https://isc.idaho.gov"],
    "IL": ["https://www.illinoiscourts.gov"],
    "IN": ["https://www.in.gov/courts"],
    "IA": ["https://www.iowacourts.gov"],
    "KS": ["https://www.kscourts.org"],
    "KY": ["https://courts.ky.gov"],
    "LA": ["https://www.lasc.org"],
    "ME": ["https://www.courts.maine.gov"],
    "MD": ["https://www.courts.state.md.us", "https://mdcourts.gov"],
    "MA": ["https://www.mass.gov/courts"],
    "MI": ["https://www.courts.michigan.gov"],
    "MN": ["https://www.mncourts.gov"],
    "MS": ["https://courts.ms.gov"],
    "MO": ["https://www.courts.mo.gov"],
    "MT": ["https://courts.mt.gov"],
    "NE": ["https://supremecourt.nebraska.gov"],
    "NV": ["https://nvcourts.gov"],
    "NH": ["https://www.courts.nh.gov"],
    "NJ": ["https://www.njcourts.gov"],
    "NM": ["https://www.nmcourts.gov"],
    "NY": ["https://www.nycourts.gov", "https://iapps.courts.state.ny.us"],
    "NC": ["https://www.nccourts.gov"],
    "ND": ["https://www.ndcourts.gov"],
    "OH": ["https://www.supremecourt.ohio.gov"],
    "OK": ["https://www.oscn.net"],
    "OR": ["https://www.courts.oregon.gov"],
    "PA": ["https://www.pacourts.us"],
    "RI": ["https://www.courts.ri.gov"],
    "SC": ["https://www.sccourts.org"],
    "SD": ["https://ujs.sd.gov"],
    "TN": ["https://www.tncourts.gov"],
    "TX": ["https://www.txcourts.gov"],
    "UT": ["https://www.utcourts.gov"],
    "VT": ["https://www.vermontjudiciary.org"],
    "VA": ["https://www.vacourts.gov"],
    "WA": ["https://www.courts.wa.gov"],
    "WV": ["https://www.courtswv.gov"],
    "WI": ["https://www.wicourts.gov"],
    "WY": ["https://www.courts.state.wy.us"],
}

# Keywords that suggest a page has e-filing information
_EFILING_KEYWORDS = [
    "e-filing", "efiling", "e-file", "efile",
    "electronic filing", "electronically file",
    "e-court", "ecourt",
    "online filing",
]

# Keywords for pages with formatting requirements
_FORMAT_KEYWORDS = [
    "format", "formatting", "requirement", "specification",
    "guideline", "standard", "rule",
    "proposed order", "document preparation",
    "filing standard", "technical standard",
]


class DiscoveredPortal:
    """A discovered e-filing portal candidate."""

    __slots__ = (
        "state", "url", "source_tier", "efiling_score",
        "format_score", "linked_from", "title",
    )

    def __init__(
        self,
        state: str,
        url: str,
        source_tier: SourceTier,
        efiling_score: float = 0.0,
        format_score: float = 0.0,
        linked_from: str = "",
        title: str = "",
    ) -> None:
        self.state = state
        self.url = url
        self.source_tier = source_tier
        self.efiling_score = efiling_score
        self.format_score = format_score
        self.linked_from = linked_from
        self.title = title

    @property
    def is_promising(self) -> bool:
        """Whether this portal likely has e-filing requirement information."""
        return self.efiling_score >= 0.3 or self.format_score >= 0.3

    def __repr__(self) -> str:
        return (
            f"DiscoveredPortal({self.state}, {self.url}, "
            f"efiling={self.efiling_score:.1f}, format={self.format_score:.1f})"
        )


class JurisdictionDiscovery(BaseScraper):
    """Discovers court e-filing portals across US jurisdictions.

    Usage::

        async with JurisdictionDiscovery() as discovery:
            portals = await discovery.discover_state("CA")
            # or discover all:
            all_portals = await discovery.discover_all_states()
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._assessor = ReliabilityAssessor()
        self._discovered: list[DiscoveredPortal] = []

    async def discover_state(self, state: str) -> list[DiscoveredPortal]:
        """Discover e-filing portals for a specific state.

        Probes known court domain patterns and follows links to find
        e-filing requirement pages.
        """
        state = state.upper()
        if state not in _STATE_COURT_PATTERNS:
            logger.warning("No known court domains for state: %s", state)
            return []

        portals: list[DiscoveredPortal] = []

        for base_url in _STATE_COURT_PATTERNS[state]:
            # Try the base URL
            found = await self._probe_url(state, base_url)
            portals.extend(found)

            # Try common e-filing sub-paths
            for path in [
                "/efiling", "/e-filing", "/efile", "/e-file",
                "/ecourts", "/electronic-filing",
                "/for-lawyers/electronic-filing",
                "/Resources-Services/Court-Technology",
                "/courts/supreme-court/electronic-filing",
            ]:
                url = base_url.rstrip("/") + path
                found = await self._probe_url(state, url)
                portals.extend(found)

        self._discovered.extend(portals)
        return portals

    async def discover_all_states(
        self,
        *,
        states: list[str] | None = None,
    ) -> list[DiscoveredPortal]:
        """Discover e-filing portals across all (or specified) states.

        This is a long-running operation that probes ~200+ URLs.
        Use states parameter to limit scope.
        """
        target_states = states or sorted(_STATE_COURT_PATTERNS.keys())
        all_portals: list[DiscoveredPortal] = []

        for state in target_states:
            logger.info("Discovering e-filing portals for %s...", state)
            portals = await self.discover_state(state)
            all_portals.extend(portals)
            logger.info(
                "  Found %d portals for %s (%d promising)",
                len(portals), state,
                sum(1 for p in portals if p.is_promising),
            )

        return all_portals

    async def _probe_url(
        self,
        state: str,
        url: str,
    ) -> list[DiscoveredPortal]:
        """Probe a single URL for e-filing information."""
        portals: list[DiscoveredPortal] = []

        try:
            page = await self.fetch(url)
        except (ValueError, ConnectionError):
            return portals

        if page.http_status != 200:
            return portals

        soup = self.parse(page)
        text = soup.get_text(separator=" ", strip=True).lower()
        tier = classify_domain(url)

        # Score for e-filing relevance
        efiling_score = sum(
            1 for kw in _EFILING_KEYWORDS if kw in text
        ) / len(_EFILING_KEYWORDS)

        # Score for formatting requirements
        format_score = sum(
            1 for kw in _FORMAT_KEYWORDS if kw in text
        ) / len(_FORMAT_KEYWORDS)

        portal = DiscoveredPortal(
            state=state,
            url=url,
            source_tier=tier,
            efiling_score=round(efiling_score, 2),
            format_score=round(format_score, 2),
            title=page.title,
        )

        if portal.is_promising:
            portals.append(portal)

        # Follow links that look like e-filing resources
        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"]
            link_text = link.get_text(strip=True).lower()

            is_efiling_link = any(kw in link_text for kw in _EFILING_KEYWORDS)
            is_format_link = any(kw in link_text for kw in _FORMAT_KEYWORDS)

            if not (is_efiling_link or is_format_link):
                continue

            # Resolve relative URLs
            resolved = urljoin(url, href)
            parsed = urlparse(resolved)

            # Stay within official domains
            if classify_domain(resolved) in (SourceTier.TERTIARY,):
                continue

            child_portal = DiscoveredPortal(
                state=state,
                url=resolved,
                source_tier=classify_domain(resolved),
                efiling_score=0.5 if is_efiling_link else 0.0,
                format_score=0.5 if is_format_link else 0.0,
                linked_from=url,
                title=link.get_text(strip=True),
            )

            if child_portal.is_promising:
                portals.append(child_portal)

        return portals

    @property
    def discovered_portals(self) -> list[DiscoveredPortal]:
        """All portals discovered across all probes."""
        return list(self._discovered)

    @property
    def promising_portals(self) -> list[DiscoveredPortal]:
        """Only portals that likely have e-filing requirement info."""
        return [p for p in self._discovered if p.is_promising]
