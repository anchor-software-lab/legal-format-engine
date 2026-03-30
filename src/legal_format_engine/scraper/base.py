"""Base scraper with robots.txt compliance, rate limiting, and polite crawling.

All court scrapers inherit from BaseScraper, which enforces:
- robots.txt checking before every request
- Configurable rate limiting (default: 2 seconds between requests per domain)
- User-Agent identification
- Response caching to avoid redundant fetches
- Structured logging of all scrape activity
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from legal_format_engine.scraper.models import ScrapedPage, SourceReliability, SourceTier

logger = logging.getLogger(__name__)

# Domains known to be official court systems
OFFICIAL_DOMAINS: set[str] = {
    # Federal
    "uscourts.gov",
    "supremecourt.gov",
    "pacer.uscourts.gov",
    # State patterns (checked via endswith)
}

OFFICIAL_SUFFIXES: tuple[str, ...] = (
    ".gov",
    ".courts.state.",
    "courts.gov",
)

# Court-contracted e-filing vendors (quasi-official)
QUASI_OFFICIAL_DOMAINS: set[str] = {
    "efilinghelp.zendesk.com",  # Tyler Technologies e-filing help portal
    "tylertech.com",
    "tylerodyssey.com",
    "fileandserve.com",
    "fileandservexpress.com",
    "myfilerunner.com",
    "greenfilingportal.com",
    "onelegal.com",
    "infotrack.com",
}

# Known legal secondary sources
SECONDARY_DOMAINS: set[str] = {
    "westlaw.com",
    "lexisnexis.com",
    "justia.com",
    "law.cornell.edu",
    "americanbar.org",
}


def classify_domain(url: str) -> SourceTier:
    """Classify a URL's domain into a source tier."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Strip www. prefix for matching
    bare_domain = domain.removeprefix("www.")

    # Check exact matches first
    if domain in OFFICIAL_DOMAINS or bare_domain in OFFICIAL_DOMAINS:
        return SourceTier.OFFICIAL
    if domain in QUASI_OFFICIAL_DOMAINS or bare_domain in QUASI_OFFICIAL_DOMAINS:
        return SourceTier.QUASI_OFFICIAL
    if domain in SECONDARY_DOMAINS or bare_domain in SECONDARY_DOMAINS:
        return SourceTier.SECONDARY

    # Check suffix patterns for official government domains
    for suffix in OFFICIAL_SUFFIXES:
        if domain.endswith(suffix):
            return SourceTier.OFFICIAL

    # State court patterns: *courts.*.gov, wicourts.gov, etc.
    if "courts" in domain and ".gov" in domain:
        return SourceTier.OFFICIAL
    # State-specific patterns
    if domain.endswith(".us") and ("court" in domain or "judicial" in domain):
        return SourceTier.OFFICIAL

    # Bar associations
    if "bar.org" in domain or "bar.com" in domain:
        return SourceTier.QUASI_OFFICIAL

    return SourceTier.TERTIARY


class BaseScraper:
    """Polite web scraper for court e-filing requirement pages.

    Usage::

        async with BaseScraper() as scraper:
            page = await scraper.fetch("https://wicourts.gov/efiling")
            soup = scraper.parse(page)
    """

    DEFAULT_DELAY_SECONDS: float = 2.0
    DEFAULT_TIMEOUT_SECONDS: float = 30.0
    USER_AGENT: str = (
        "LegalFormatEngine/0.1 "
        "(+https://github.com/anchor-software-lab/legal-format-engine; "
        "legal-formatting-research; respectful-scraper)"
    )

    def __init__(
        self,
        *,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        respect_robots: bool = True,
        max_retries: int = 2,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.respect_robots = respect_robots
        self.max_retries = max_retries

        self._client: httpx.AsyncClient | None = None
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._last_request_time: dict[str, float] = {}  # per-domain
        self._page_cache: dict[str, ScrapedPage] = {}
        self._scrape_log: list[ScrapedPage] = []

    async def __aenter__(self) -> BaseScraper:
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    async def _check_robots(self, url: str) -> bool:
        """Check robots.txt for the given URL. Returns True if allowed."""
        if not self.respect_robots:
            return True

        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        domain = self._get_domain(url)

        if domain not in self._robots_cache:
            rp = RobotFileParser()
            try:
                assert self._client is not None
                resp = await self._client.get(robots_url)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    # No robots.txt = everything allowed
                    rp.allow_all = True
            except (httpx.HTTPError, AssertionError):
                # Network error fetching robots.txt = assume allowed
                rp = RobotFileParser()
                rp.allow_all = True
            self._robots_cache[domain] = rp

        rp = self._robots_cache[domain]
        return rp.can_fetch(self.USER_AGENT, url)

    async def _rate_limit(self, domain: str) -> None:
        """Enforce per-domain rate limiting."""
        last = self._last_request_time.get(domain, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < self.delay_seconds:
            wait = self.delay_seconds - elapsed
            logger.debug("Rate limiting: waiting %.1fs for %s", wait, domain)
            # Use asyncio.sleep in real async context; time.sleep as fallback
            import asyncio
            await asyncio.sleep(wait)
        self._last_request_time[domain] = time.monotonic()

    async def fetch(self, url: str) -> ScrapedPage:
        """Fetch a URL with robots.txt and rate-limit compliance.

        Returns a ScrapedPage with metadata. Raises ValueError if
        robots.txt disallows access.
        """
        assert self._client is not None, "Use 'async with BaseScraper() as scraper:'"

        domain = self._get_domain(url)

        # Check cache
        if url in self._page_cache:
            logger.debug("Cache hit: %s", url)
            return self._page_cache[url]

        # Check robots.txt
        robots_allowed = await self._check_robots(url)
        if not robots_allowed:
            page = ScrapedPage(
                url=url,
                domain=domain,
                robots_txt_allowed=False,
                http_status=0,
            )
            self._scrape_log.append(page)
            logger.warning("robots.txt disallows: %s", url)
            raise ValueError(f"robots.txt disallows scraping: {url}")

        # Rate limit
        await self._rate_limit(domain)

        # Fetch with retries
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                start = time.monotonic()
                resp = await self._client.get(url)
                elapsed_ms = (time.monotonic() - start) * 1000

                content = resp.text
                content_hash = hashlib.sha256(content.encode()).hexdigest()

                page = ScrapedPage(
                    url=url,
                    domain=domain,
                    http_status=resp.status_code,
                    content_hash=content_hash,
                    last_modified=resp.headers.get("Last-Modified"),
                    robots_txt_allowed=True,
                    response_time_ms=round(elapsed_ms, 1),
                )

                # Store raw content for parsing
                page._content = content  # type: ignore[attr-defined]

                self._page_cache[url] = page
                self._scrape_log.append(page)
                logger.info(
                    "Fetched %s [%d] in %.0fms",
                    url, resp.status_code, elapsed_ms,
                )
                return page

            except httpx.HTTPError as e:
                last_error = e
                if attempt < self.max_retries:
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        "Fetch failed (attempt %d/%d): %s. Retrying in %ds",
                        attempt + 1, self.max_retries + 1, e, wait,
                    )
                    import asyncio
                    await asyncio.sleep(wait)

        raise ConnectionError(
            f"Failed to fetch {url} after {self.max_retries + 1} attempts: {last_error}"
        )

    def parse(self, page: ScrapedPage) -> BeautifulSoup:
        """Parse a fetched page into a BeautifulSoup tree."""
        content = getattr(page, "_content", "")
        soup = BeautifulSoup(content, "lxml")
        page.title = (soup.title.string or "").strip() if soup.title else ""
        return soup

    def assess_source(self, url: str, page: ScrapedPage) -> SourceReliability:
        """Build initial reliability assessment for a source URL.

        This provides automatic tier classification and authority scoring.
        Subclasses refine the other CRAAP dimensions based on content analysis.
        """
        domain = self._get_domain(url)
        tier = classify_domain(url)

        # Authority score based on tier
        authority_scores = {
            SourceTier.OFFICIAL: 1.0,
            SourceTier.QUASI_OFFICIAL: 0.7,
            SourceTier.SECONDARY: 0.4,
            SourceTier.TERTIARY: 0.15,
        }

        # Purpose score: official/quasi sources are informational
        purpose_scores = {
            SourceTier.OFFICIAL: 1.0,
            SourceTier.QUASI_OFFICIAL: 0.8,
            SourceTier.SECONDARY: 0.5,
            SourceTier.TERTIARY: 0.3,
        }

        return SourceReliability(
            source_url=url,
            domain=domain,
            tier=tier,
            authority=authority_scores[tier],
            purpose=purpose_scores[tier],
            # Currency, relevance, accuracy filled by subclass/assessor
            currency=0.5,  # default until page date is analyzed
            relevance=0.5,  # default until content is analyzed
            accuracy=0.5,  # default until cross-referenced
        )

    @property
    def scrape_log(self) -> list[ScrapedPage]:
        """All pages fetched during this session."""
        return list(self._scrape_log)
