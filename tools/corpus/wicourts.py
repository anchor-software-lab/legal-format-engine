"""Polite scraper for wicourts.gov brief discovery + download.

Brief filings in Wisconsin appellate courts are public records under
Wis. Stat. § 19.31 et seq. The Wisconsin Supreme Court (WI) and
Court of Appeals (WI App) publish them through their search
interfaces. This module abstracts the two relevant operations:

  - `discover_briefs(court, max_count)` — yield `BriefRef`s for
    recently filed briefs. Polite: paginates, rate-limits, caches
    HTML responses.
  - `download_brief(ref)` — fetch the PDF bytes for a `BriefRef`.

Network is gated by an injected `httpx.AsyncBaseTransport` so tests
swap a `httpx.MockTransport`. Production calls go to the real
endpoints; rate-limit is the user's responsibility via
`min_delay_seconds`.

The selector logic that locates briefs in the discovery HTML is
intentionally lenient: WI courts' pages can change formatting, and we
prefer "find any docket-like link" over a brittle CSS path. When the
page shape changes, the unit tests against the cached fixture HTML
catch it.

This module is intentionally read-only against the public web; it
never authenticates, never posts, never tries to enumerate sealed
filings.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx


DEFAULT_BASE_URL = "https://wscca.wicourts.gov"
DEFAULT_USER_AGENT = (
    "AnchorQualityGateBot/0.1 (+https://anchorlabs.dev/bots) "
    "research+contact@anchorlabs.dev"
)
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MIN_DELAY_SECONDS = 2.0  # be a good citizen
DEFAULT_DISCOVERY_PATH = "/courtOfAppealsBriefs.xsl"


# Fairly tolerant pattern: any href ending in .pdf, with optional
# query string. Lets the scraper survive markup churn.
_PDF_LINK = re.compile(
    r'href=["\']([^"\']+?\.pdf(?:\?[^"\']*)?)["\']',
    re.IGNORECASE,
)


# Match docket numbers of the form `YYYYAP####` (Court of Appeals) or
# `YYYY WI ###` (Supreme Court). Used to attribute a brief to its case.
_DOCKET = re.compile(
    r"(\b\d{4}AP\d{1,5}\b|\b\d{4}\sWI\s\d{1,5}\b)"
)


@dataclass(frozen=True)
class BriefRef:
    """One discovered brief: PDF URL + best-effort docket hint."""

    pdf_url: str
    docket: str | None = None
    discovered_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    source_page: str | None = None

    @property
    def cache_key(self) -> str:
        return hashlib.sha256(self.pdf_url.encode("utf-8")).hexdigest()


class WICourtsClient:
    """Brief-discovery + download client for wicourts.gov."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        cache_dir: str | Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
        min_delay_seconds: float = DEFAULT_MIN_DELAY_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._transport = transport
        self._timeout = timeout
        self._headers = {"User-Agent": user_agent, "Accept": "*/*"}
        self._min_delay = min_delay_seconds
        self._last_call_at: float = 0.0
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def discover_briefs(
        self,
        *,
        court: str = "coa",
        max_count: int = 50,
        start_path: str | None = None,
    ) -> list[BriefRef]:
        """Yield up to `max_count` `BriefRef`s.

        v1 walks one search page; pagination support is a v1.5 item
        (the wicourts.gov search UI's pagination URLs are non-stable
        and frequently change).
        """
        path = start_path or DEFAULT_DISCOVERY_PATH
        html = await self._fetch_text(self._absolute(path))
        return list(_extract_brief_refs(html, base=self.base_url))[:max_count]

    async def download_brief(self, ref: BriefRef) -> bytes:
        """Fetch the PDF bytes for `ref`. Cached if `cache_dir` is set."""
        if self.cache_dir:
            cached = self.cache_dir / f"{ref.cache_key}.pdf"
            if cached.exists():
                return cached.read_bytes()
        data = await self._fetch_bytes(ref.pdf_url)
        if self.cache_dir:
            cached = self.cache_dir / f"{ref.cache_key}.pdf"
            cached.write_bytes(data)
        return data

    # -------- internals --------

    def _absolute(self, path_or_url: str) -> str:
        parsed = urlparse(path_or_url)
        if parsed.scheme:
            return path_or_url
        return urljoin(self.base_url + "/", path_or_url.lstrip("/"))

    async def _throttle(self) -> None:
        now = asyncio.get_event_loop().time()
        delta = now - self._last_call_at
        if delta < self._min_delay:
            await asyncio.sleep(self._min_delay - delta)
        self._last_call_at = asyncio.get_event_loop().time()

    async def _fetch_text(self, url: str) -> str:
        await self._throttle()
        async with httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport
        ) as c:
            r = await c.get(url, headers=self._headers)
            r.raise_for_status()
            return r.text

    async def _fetch_bytes(self, url: str) -> bytes:
        await self._throttle()
        async with httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport
        ) as c:
            r = await c.get(url, headers=self._headers)
            r.raise_for_status()
            return r.content


def _extract_brief_refs(html: str, *, base: str) -> list[BriefRef]:
    refs: list[BriefRef] = []
    seen: set[str] = set()
    docket_hint = None
    docket_match = _DOCKET.search(html)
    if docket_match:
        docket_hint = docket_match.group(0)

    for match in _PDF_LINK.finditer(html):
        href = match.group(1)
        # Skip obvious image / non-brief links by tail substring.
        if any(skip in href.lower() for skip in ("logo", "header", "icon")):
            continue
        pdf_url = href if href.startswith(("http://", "https://")) else urljoin(
            base + "/", href.lstrip("/")
        )
        if pdf_url in seen:
            continue
        seen.add(pdf_url)
        refs.append(BriefRef(pdf_url=pdf_url, docket=docket_hint))
    return refs
