"""Scraper tests with httpx.MockTransport."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from tools.corpus.wicourts import BriefRef, WICourtsClient, _extract_brief_refs


_FIXTURE_HTML = """
<html><body>
  <p>Recent court of appeals briefs (Docket 2024AP137)</p>
  <table>
    <tr><td>Case A</td><td><a href="/briefs/2024AP137/appellant.pdf">Appellant Brief</a></td></tr>
    <tr><td>Case A</td><td><a href="/briefs/2024AP137/respondent.pdf">Respondent Brief</a></td></tr>
    <tr><td>Case B</td><td><a href="https://wscca.wicourts.gov/briefs/2024AP200/appellant.pdf">Brief</a></td></tr>
  </table>
  <img src="/static/logo.pdf" alt="logo" />  <!-- should be skipped -->
</body></html>
"""


def _client_with_html(handler) -> WICourtsClient:
    transport = httpx.MockTransport(handler)
    return WICourtsClient(transport=transport, min_delay_seconds=0.0)


def test_extract_brief_refs_finds_three_unique_pdfs():
    refs = _extract_brief_refs(_FIXTURE_HTML, base="https://wscca.wicourts.gov")
    urls = [r.pdf_url for r in refs]
    assert len(urls) == 3
    assert "https://wscca.wicourts.gov/briefs/2024AP137/appellant.pdf" in urls
    assert "https://wscca.wicourts.gov/briefs/2024AP137/respondent.pdf" in urls
    assert "https://wscca.wicourts.gov/briefs/2024AP200/appellant.pdf" in urls


def test_extract_brief_refs_skips_static_assets():
    refs = _extract_brief_refs(_FIXTURE_HTML, base="https://wscca.wicourts.gov")
    assert not any("logo" in r.pdf_url for r in refs)


def test_extract_brief_refs_captures_docket_hint():
    refs = _extract_brief_refs(_FIXTURE_HTML, base="https://wscca.wicourts.gov")
    # All three share the same first-found docket.
    assert refs[0].docket == "2024AP137"


def test_extract_brief_refs_dedupes():
    html = '<html><a href="/x.pdf">a</a><a href="/x.pdf">b</a></html>'
    refs = _extract_brief_refs(html, base="https://example.test")
    assert len(refs) == 1


def test_discover_uses_html_to_find_briefs():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_FIXTURE_HTML)

    client = _client_with_html(handler)
    refs = asyncio.run(client.discover_briefs(max_count=10))
    assert len(refs) == 3


def test_discover_respects_max_count():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_FIXTURE_HTML)

    client = _client_with_html(handler)
    refs = asyncio.run(client.discover_briefs(max_count=2))
    assert len(refs) == 2


def test_download_caches_pdf_bytes(tmp_path: Path):
    body = b"%PDF-1.4 fake brief content"
    fetches = []

    def handler(req: httpx.Request) -> httpx.Response:
        fetches.append(req.url)
        return httpx.Response(200, content=body)

    client = WICourtsClient(
        cache_dir=tmp_path,
        transport=httpx.MockTransport(handler),
        min_delay_seconds=0.0,
    )
    ref = BriefRef(pdf_url="https://wscca.wicourts.gov/briefs/2024AP1/a.pdf")

    a = asyncio.run(client.download_brief(ref))
    b = asyncio.run(client.download_brief(ref))
    assert a == body
    assert b == body
    # Second call served from cache.
    assert len(fetches) == 1


def test_discover_raises_on_5xx():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream busy")

    client = _client_with_html(handler)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(client.discover_briefs())


def test_brief_ref_cache_key_is_sha256_of_url():
    ref = BriefRef(pdf_url="https://example/x.pdf")
    assert len(ref.cache_key) == 64
    assert all(c in "0123456789abcdef" for c in ref.cache_key)
