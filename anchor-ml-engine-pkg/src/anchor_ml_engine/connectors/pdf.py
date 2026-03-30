"""PDF connector: extract formatting profile from PDF files.

Uses PyMuPDF (fitz) to analyze text spans, fonts, margins, headings,
and section structure from PDF documents.
"""

from __future__ import annotations

from pathlib import Path

from anchor_ml_engine.models import NormalizedDocument
from anchor_ml_engine.normalizer import build_normalized_document


def extract_from_pdf(
    path: str | Path,
    category: str | None = None,
    subcategory: str | None = None,
    document_type: str | None = None,
    author: str | None = None,
    organization: str | None = None,
) -> NormalizedDocument:
    """Analyze a PDF file and return a NormalizedDocument.

    Extracts fonts, margins (estimated from text bounding boxes),
    heading candidates, and section structure.

    Requires PyMuPDF (pip install pymupdf).
    """
    import fitz

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        raise ValueError(f"Could not open PDF file: {exc}") from exc

    try:
        return _extract_from_pdf_doc(
            doc, path, category, subcategory, document_type, author, organization,
        )
    finally:
        doc.close()


def _extract_from_pdf_doc(
    doc,
    path: Path,
    category: str | None,
    subcategory: str | None,
    document_type: str | None,
    author: str | None,
    organization: str | None,
) -> NormalizedDocument:
    """Internal PDF extraction from an open fitz.Document."""
    import fitz

    font_counts: dict[str, int] = {}
    size_counts: dict[float, int] = {}

    # Margin estimation
    min_x = float("inf")
    max_x = 0.0
    min_y = float("inf")
    max_y = 0.0

    page_rect = doc[0].rect if len(doc) > 0 else fitz.Rect(0, 0, 612, 792)

    # Line spacing estimation
    prev_line_bottom: float | None = None
    prev_line_height: float | None = None
    line_gaps: list[float] = []

    for page in doc:
        text_dict = page.get_text("dict")
        page_rect = page.rect

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue

                line_text = "".join(
                    span.get("text", "") for span in spans
                ).strip()
                if not line_text:
                    continue

                bbox = line.get("bbox", (0, 0, 0, 0))

                # Font analysis
                for span in spans:
                    span_text = span.get("text", "").strip()
                    if not span_text:
                        continue
                    font_name = span.get("font", "Unknown")
                    font_size = round(span.get("size", 0), 1)
                    font_counts[font_name] = (
                        font_counts.get(font_name, 0) + len(span_text)
                    )
                    if font_size > 0:
                        size_counts[font_size] = (
                            size_counts.get(font_size, 0) + len(span_text)
                        )

                # Margin estimation
                if len(line_text) > 5:
                    min_x = min(min_x, bbox[0])
                    max_x = max(max_x, bbox[2])
                    min_y = min(min_y, bbox[1])
                    max_y = max(max_y, bbox[3])

                # Line spacing estimation
                line_height = bbox[3] - bbox[1]
                if prev_line_bottom is not None and prev_line_height is not None:
                    gap = bbox[1] - prev_line_bottom
                    if 0 < gap < prev_line_height * 4:
                        spacing_ratio = (line_height + gap) / line_height if line_height > 0 else 0
                        if 0.5 < spacing_ratio < 5:
                            line_gaps.append(spacing_ratio)
                prev_line_bottom = bbox[3]
                prev_line_height = line_height

    # Build results
    margins = None
    if min_x < float("inf"):
        margins = {
            "top": round(min_y / 72, 2),
            "bottom": round((page_rect.height - max_y) / 72, 2),
            "left": round(min_x / 72, 2),
            "right": round((page_rect.width - max_x) / 72, 2),
        }

    fonts = []
    if font_counts:
        dominant_font = max(font_counts, key=font_counts.get)
        dominant_size = max(size_counts, key=size_counts.get) if size_counts else 12.0
        fonts.append({"font_name": dominant_font, "font_size_pt": dominant_size})

    # Line spacing
    avg_spacing = None
    if line_gaps:
        raw_avg = sum(line_gaps) / len(line_gaps)
        for candidate in [1.0, 1.15, 1.5, 2.0, 2.5, 3.0]:
            if abs(raw_avg - candidate) < 0.3:
                avg_spacing = candidate
                break
        if avg_spacing is None:
            avg_spacing = round(raw_avg, 1)

    return build_normalized_document(
        source_filename=path.name,
        source_format="pdf",
        fonts=fonts or None,
        margins=margins,
        line_spacing=avg_spacing,
        category=category,
        subcategory=subcategory,
        document_type=document_type,
        author=author,
        organization=organization,
    )
