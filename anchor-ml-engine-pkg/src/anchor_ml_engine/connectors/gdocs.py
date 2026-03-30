"""Google Docs connector for importing documents.

Supports three modes of importing Google Docs content:

1. **HTML upload**: Parse a Google Docs HTML export to extract formatting.
2. **URL-based export**: Download a publicly shared Google Doc as DOCX
   via the export URL pattern.
3. **API integration** (future): Placeholder structure for full Google
   Docs API / OAuth integration.

Uses only stdlib modules (urllib.request, html.parser) to avoid extra
dependencies.
"""

from __future__ import annotations

import logging
import re
import tempfile
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from anchor_ml_engine.models import NormalizedDocument
from anchor_ml_engine.normalizer import (
    NormalizedFont,
    NormalizedMargins,
    build_normalized_document,
    canonicalize_font_name,
    snap_font_size,
    snap_margin,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex for extracting a Google Docs document ID from various URL forms.
# ---------------------------------------------------------------------------
_DOC_ID_RE = re.compile(
    r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)"
)

_GOOGLE_DOCS_HOST_RE = re.compile(
    r"^https?://docs\.google\.com/document/d/"
)


class GoogleDocsConnector:
    """Handle Google Docs content for analysis.

    All public methods are static so the class can be used without
    instantiation. A future OAuth-based integration can subclass and
    store credentials as instance state.
    """

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_google_docs_url(url: str) -> bool:
        """Check if a URL is a Google Docs URL."""
        return bool(_GOOGLE_DOCS_HOST_RE.search(url))

    @staticmethod
    def extract_doc_id(url: str) -> str:
        """Extract the document ID from a Google Docs URL.

        Raises:
            ValueError: If the URL does not contain a recognisable doc ID.
        """
        match = _DOC_ID_RE.search(url)
        if not match:
            raise ValueError(
                f"Could not extract a document ID from URL: {url}"
            )
        return match.group(1)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    @staticmethod
    def download_as_docx(share_url: str, output_path: Path | None = None) -> Path:
        """Download a publicly shared Google Doc as DOCX.

        Only works for documents shared as *anyone with the link*.

        Args:
            share_url: A Google Docs sharing / edit URL.
            output_path: Where to write the DOCX file. If ``None`` a
                temporary file is created.

        Returns:
            Path to the downloaded DOCX file.

        Raises:
            ValueError: If the URL is not a valid Google Docs URL.
            ConnectionError: If the download fails.
        """
        doc_id = GoogleDocsConnector.extract_doc_id(share_url)
        export_url = (
            f"https://docs.google.com/document/d/{doc_id}/export?format=docx"
        )

        if output_path is None:
            output_path = Path(tempfile.mktemp(suffix=".docx"))

        try:
            req = urllib.request.Request(
                export_url,
                headers={"User-Agent": "AnchorMLEngine/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if len(data) == 0:
                    raise ConnectionError(
                        "Received empty response -- document may not be shared publicly."
                    )
                output_path.write_bytes(data)
        except urllib.error.HTTPError as exc:
            if exc.code == 401 or exc.code == 403:
                raise ConnectionError(
                    "Access denied -- the document is not shared publicly "
                    "(anyone with the link)."
                ) from exc
            raise ConnectionError(
                f"Failed to download Google Doc (HTTP {exc.code}): {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Network error downloading Google Doc: {exc.reason}"
            ) from exc

        logger.info("Downloaded Google Doc %s to %s", doc_id, output_path)
        return output_path

    # ------------------------------------------------------------------
    # HTML export parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_html_export(html_path: Path) -> dict:
        """Parse a Google Docs HTML export to extract formatting info.

        Returns:
            A dict with keys:
            - ``paragraphs``: list of paragraph dicts (text, styles)
            - ``page_settings``: dict of page-level CSS (margins, size)
            - ``font_summary``: dominant font information
            - ``heading_candidates``: paragraphs detected as headings
        """
        html_text = html_path.read_text(encoding="utf-8", errors="replace")
        parser = _GoogleDocsHTMLParser()
        parser.feed(html_text)
        return parser.result()

    @staticmethod
    def normalize_html_export(
        html_path: Path,
        category: str | None = None,
        subcategory: str | None = None,
    ) -> NormalizedDocument:
        """Parse and normalize a Google Docs HTML export."""
        try:
            result = GoogleDocsConnector.parse_html_export(html_path)
        except Exception:
            return NormalizedDocument(
                source_filename=html_path.name,
                source_format="html",
                extraction_confidence=0.3,
            )

        # Extract font info
        font_counts: dict[str, int] = {}
        size_counts: dict[float, int] = {}
        for para in result.get("paragraphs", []):
            fname = para.get("font_family")
            fsize = para.get("font_size_pt")
            text_len = len(para.get("text", ""))
            if fname and text_len:
                font_counts[fname] = font_counts.get(fname, 0) + text_len
            if fsize and text_len:
                size_counts[fsize] = size_counts.get(fsize, 0) + text_len

        fonts = None
        if font_counts and size_counts:
            top_font = max(font_counts, key=font_counts.get)
            top_size = max(size_counts, key=size_counts.get)
            fonts = [{"font_name": top_font, "font_size_pt": top_size}]

        # Extract margins
        margins = None
        page = result.get("page_settings", {})
        if page.get("margin_top") is not None:
            margins = {
                "top": page.get("margin_top", 1.0),
                "bottom": page.get("margin_bottom", 1.0),
                "left": page.get("margin_left", 1.0),
                "right": page.get("margin_right", 1.0),
            }

        return build_normalized_document(
            source_filename=html_path.name,
            source_format="html",
            fonts=fonts,
            margins=margins,
            category=category,
            subcategory=subcategory,
        )


# -----------------------------------------------------------------------
# Internal HTML parser
# -----------------------------------------------------------------------

class _GoogleDocsHTMLParser(HTMLParser):
    """stdlib HTMLParser subclass that extracts formatting from a Google
    Docs HTML export."""

    def __init__(self) -> None:
        super().__init__()
        self._css_classes: dict[str, dict[str, str]] = {}
        self._page_settings: dict[str, str] = {}
        self._in_style = False
        self._style_content = ""
        self._in_body = False
        self._current_tag: str | None = None
        self._tag_stack: list[str] = []
        self._class_stack: list[list[str]] = []
        self._paragraphs: list[dict] = []
        self._current_para: dict | None = None
        self._current_spans: list[dict] = []
        self._current_span_text = ""
        self._current_span_classes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        classes = (attr_dict.get("class") or "").split()
        self._tag_stack.append(tag)
        self._class_stack.append(classes)

        if tag == "style":
            self._in_style = True
            self._style_content = ""
        if tag == "body":
            self._in_body = True
        if self._in_body and tag == "p":
            self._current_para = {"classes": classes, "spans": [], "text": ""}
            self._current_spans = []
        if self._in_body and tag == "span":
            self._flush_span()
            self._current_span_classes = classes
            self._current_span_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self._in_style = False
            self._parse_css(self._style_content)
        if self._in_body and tag == "span":
            self._flush_span()
        if self._in_body and tag == "p" and self._current_para is not None:
            self._flush_span()
            self._current_para["spans"] = list(self._current_spans)
            self._current_para["text"] = "".join(s["text"] for s in self._current_spans)
            self._paragraphs.append(self._current_para)
            self._current_para = None
            self._current_spans = []
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        if self._class_stack:
            self._class_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self._style_content += data
            return
        if self._in_body and self._current_para is not None:
            self._current_span_text += data

    def _flush_span(self) -> None:
        text = self._current_span_text
        if text:
            self._current_spans.append({
                "text": text,
                "classes": list(self._current_span_classes),
            })
        self._current_span_text = ""
        self._current_span_classes = []

    _CSS_CLASS_RE = re.compile(r"\.(c\d+)\s*\{([^}]*)\}", re.DOTALL)
    _CSS_PAGE_RE = re.compile(r"@page\s*\{([^}]*)\}", re.DOTALL)
    _CSS_PROP_RE = re.compile(r"([\w-]+)\s*:\s*([^;]+);?")

    def _parse_css(self, css_text: str) -> None:
        for match in self._CSS_CLASS_RE.finditer(css_text):
            class_name = match.group(1)
            props_raw = match.group(2)
            props = {}
            for prop_match in self._CSS_PROP_RE.finditer(props_raw):
                props[prop_match.group(1).strip()] = prop_match.group(2).strip()
            self._css_classes[class_name] = props

        page_match = self._CSS_PAGE_RE.search(css_text)
        if page_match:
            for prop_match in self._CSS_PROP_RE.finditer(page_match.group(1)):
                self._page_settings[prop_match.group(1).strip()] = (
                    prop_match.group(2).strip()
                )

    def _resolve_styles(self, classes: list[str]) -> dict[str, str]:
        merged: dict[str, str] = {}
        for cls in classes:
            if cls in self._css_classes:
                merged.update(self._css_classes[cls])
        return merged

    def result(self) -> dict:
        paragraphs = self._build_paragraphs()
        font_summary = self._build_font_summary(paragraphs)
        heading_candidates = self._detect_headings(paragraphs)
        page_settings = self._build_page_settings()
        return {
            "paragraphs": paragraphs,
            "page_settings": page_settings,
            "font_summary": font_summary,
            "heading_candidates": heading_candidates,
        }

    def _build_paragraphs(self) -> list[dict]:
        results: list[dict] = []
        for raw in self._paragraphs:
            text = raw["text"].strip()
            if not text:
                continue
            para_styles = self._resolve_styles(raw["classes"])
            span_infos: list[dict] = []
            for span in raw["spans"]:
                span_styles = self._resolve_styles(span["classes"])
                span_infos.append({
                    "text": span["text"],
                    "font_family": span_styles.get("font-family", "").strip("'\""),
                    "font_size_pt": _css_size_to_pt(span_styles.get("font-size", "")),
                    "bold": _is_bold(span_styles),
                    "italic": _is_italic(span_styles),
                })

            font_family = _dominant_span_value(span_infos, "font_family") or para_styles.get("font-family", "").strip("'\"")
            font_size_pt = _dominant_span_value(span_infos, "font_size_pt") or _css_size_to_pt(para_styles.get("font-size", ""))
            is_bold = all(s["bold"] for s in span_infos if s["text"].strip()) if span_infos else _is_bold(para_styles)
            is_italic = all(s["italic"] for s in span_infos if s["text"].strip()) if span_infos else _is_italic(para_styles)
            text_align = para_styles.get("text-align", "left")
            margin_left_pt = _css_size_to_pt(para_styles.get("margin-left", "0"))
            margin_left_inches = round(margin_left_pt / 72, 2) if margin_left_pt else 0.0
            line_height_raw = para_styles.get("line-height", "")
            line_height = _parse_line_height(line_height_raw)

            results.append({
                "text": text,
                "font_family": font_family,
                "font_size_pt": font_size_pt,
                "bold": is_bold,
                "italic": is_italic,
                "text_align": text_align,
                "margin_left_inches": margin_left_inches,
                "line_height": line_height,
                "spans": span_infos,
            })
        return results

    def _build_font_summary(self, paragraphs: list[dict]) -> dict:
        font_counts: dict[str, int] = {}
        size_counts: dict[float, int] = {}
        for para in paragraphs:
            font = para.get("font_family")
            size = para.get("font_size_pt")
            text_len = len(para.get("text", ""))
            if font:
                font_counts[font] = font_counts.get(font, 0) + text_len
            if size and size > 0:
                size_counts[size] = size_counts.get(size, 0) + text_len
        dominant_font = max(font_counts, key=font_counts.get) if font_counts else None
        dominant_size = max(size_counts, key=size_counts.get) if size_counts else None
        return {
            "dominant_font": dominant_font,
            "dominant_size_pt": dominant_size,
            "font_counts": font_counts,
            "size_counts": {str(k): v for k, v in size_counts.items()},
        }

    def _detect_headings(self, paragraphs: list[dict]) -> list[dict]:
        candidates: list[dict] = []
        body_sizes = [
            p["font_size_pt"]
            for p in paragraphs
            if p.get("font_size_pt") and len(p["text"]) > 100
        ]
        body_size = max(set(body_sizes), key=body_sizes.count) if body_sizes else 12.0
        for idx, para in enumerate(paragraphs):
            text = para["text"]
            if len(text) > 150:
                continue
            is_bold = para.get("bold", False)
            is_centered = para.get("text_align") == "center"
            alpha_chars = [c for c in text if c.isalpha()]
            is_all_caps = bool(alpha_chars) and all(c.isupper() for c in alpha_chars)
            font_size = para.get("font_size_pt") or 0
            is_larger = font_size > body_size
            if is_bold or is_centered or is_all_caps or is_larger:
                candidates.append({
                    "index": idx,
                    "text": text,
                    "bold": is_bold,
                    "centered": is_centered,
                    "all_caps": is_all_caps,
                    "font_size_pt": font_size,
                    "larger_than_body": is_larger,
                })
        return candidates

    def _build_page_settings(self) -> dict:
        result: dict[str, object] = {}
        margin = self._page_settings.get("margin")
        if margin:
            parts = margin.split()
            if len(parts) == 1:
                val = _css_size_to_inches(parts[0])
                result["margin_top"] = val
                result["margin_right"] = val
                result["margin_bottom"] = val
                result["margin_left"] = val
            elif len(parts) == 2:
                tb = _css_size_to_inches(parts[0])
                lr = _css_size_to_inches(parts[1])
                result["margin_top"] = tb
                result["margin_bottom"] = tb
                result["margin_left"] = lr
                result["margin_right"] = lr
            elif len(parts) == 4:
                result["margin_top"] = _css_size_to_inches(parts[0])
                result["margin_right"] = _css_size_to_inches(parts[1])
                result["margin_bottom"] = _css_size_to_inches(parts[2])
                result["margin_left"] = _css_size_to_inches(parts[3])

        for side in ("top", "right", "bottom", "left"):
            key = f"margin-{side}"
            if key in self._page_settings:
                result[f"margin_{side}"] = _css_size_to_inches(self._page_settings[key])
        size = self._page_settings.get("size")
        if size:
            result["page_size"] = size
        return result


# -----------------------------------------------------------------------
# CSS value helpers
# -----------------------------------------------------------------------

_CSS_SIZE_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(pt|px|in|cm|mm|em|rem|%)?")


def _css_size_to_pt(value: str) -> float:
    if not value:
        return 0.0
    m = _CSS_SIZE_RE.search(value)
    if not m:
        return 0.0
    num = float(m.group(1))
    unit = m.group(2) or "pt"
    if unit == "pt":
        return num
    if unit == "px":
        return num * 0.75
    if unit == "in":
        return num * 72
    if unit == "cm":
        return num * 28.3465
    if unit == "mm":
        return num * 2.83465
    if unit in ("em", "rem"):
        return num * 12
    return num


def _css_size_to_inches(value: str) -> float:
    pt = _css_size_to_pt(value)
    return round(pt / 72, 2)


def _is_bold(styles: dict[str, str]) -> bool:
    weight = styles.get("font-weight", "").lower()
    return weight in ("bold", "700", "800", "900")


def _is_italic(styles: dict[str, str]) -> bool:
    style = styles.get("font-style", "").lower()
    return style in ("italic", "oblique")


def _parse_line_height(raw: str) -> float | None:
    if not raw or raw.strip().lower() == "normal":
        return None
    raw = raw.strip()
    try:
        val = float(raw)
        return round(val, 2)
    except ValueError:
        pass
    pt = _css_size_to_pt(raw)
    if pt > 0:
        return round(pt / 12, 2)
    return None


def _dominant_span_value(spans: list[dict], key: str) -> object | None:
    counts: dict[object, int] = {}
    for s in spans:
        val = s.get(key)
        if val:
            counts[val] = counts.get(val, 0) + len(s.get("text", ""))
    if not counts:
        return None
    return max(counts, key=counts.get)
