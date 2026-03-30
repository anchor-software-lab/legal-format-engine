"""Brief analysis module for extracting formatting patterns from uploaded briefs.

Analyzes DOCX and PDF files to extract font usage, margins, heading styles,
section structure, indentation, and other formatting patterns that can be
learned and applied to future document formatting.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from legal_format_engine.models.patterns import (
    BriefAnalysis,
    FontPattern,
    HeadingPattern,
    MarginPattern,
    SectionPattern,
)

# Common legal brief section names for matching
_LEGAL_SECTIONS = {
    "table_of_contents": [
        "table of contents", "contents",
    ],
    "table_of_authorities": [
        "table of authorities", "authorities cited",
    ],
    "statement_of_issues": [
        "statement of issues", "issues presented", "questions presented",
        "statement of the issues", "issues for review",
    ],
    "statement_of_case": [
        "statement of the case", "statement of case",
        "nature of the case", "procedural history",
    ],
    "statement_of_facts": [
        "statement of facts", "factual background", "facts",
        "statement of the facts",
    ],
    "summary_of_argument": [
        "summary of argument", "summary of the argument",
    ],
    "argument": [
        "argument", "arguments",
    ],
    "conclusion": [
        "conclusion", "relief requested",
    ],
    "certificate_of_compliance": [
        "certificate of compliance", "certification of compliance",
        "word count certification",
    ],
    "certificate_of_service": [
        "certificate of service", "proof of service",
    ],
    "appendix": [
        "appendix", "addendum",
    ],
    "introduction": [
        "introduction", "preliminary statement",
    ],
    "standard_of_review": [
        "standard of review", "standards of review",
    ],
    "jurisdictional_statement": [
        "jurisdictional statement", "statement of jurisdiction",
        "basis for jurisdiction",
    ],
}


def analyze_brief(
    path: str | Path,
    jurisdiction: str | None = None,
    court_level: str | None = None,
) -> BriefAnalysis:
    """Analyze a brief file and extract formatting patterns.

    Supports DOCX and PDF files. Extracts fonts, margins, heading styles,
    section structure, indentation, and other formatting patterns.

    Args:
        path: Path to the brief file (DOCX or PDF).
        jurisdiction: Optional jurisdiction tag.
        court_level: Optional court level tag.

    Returns:
        A BriefAnalysis with all detected patterns.

    Raises:
        ValueError: If file type is unsupported.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Brief file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _analyze_docx(path, jurisdiction, court_level)
    elif suffix == ".pdf":
        return _analyze_pdf(path, jurisdiction, court_level)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use .docx or .pdf")


def _analyze_docx(
    path: Path,
    jurisdiction: str | None,
    court_level: str | None,
) -> BriefAnalysis:
    """Extract formatting patterns from a DOCX file."""
    from docx import Document as DocxDocument
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches

    try:
        docx = DocxDocument(str(path))
    except Exception as exc:
        raise ValueError(f"Could not open DOCX file: {exc}") from exc

    # -- Page layout / margins --
    margin_pattern = None
    if docx.sections:
        sec = docx.sections[0]
        margin_pattern = MarginPattern(
            top=round(sec.top_margin / 914400, 2),
            bottom=round(sec.bottom_margin / 914400, 2),
            left=round(sec.left_margin / 914400, 2),
            right=round(sec.right_margin / 914400, 2),
        )

    # -- Font analysis (sample body paragraphs) --
    font_counts: dict[str, int] = {}
    size_counts: dict[float, int] = {}
    line_spacings: list[float] = []
    indent_values: list[float] = []
    block_quote_indents: list[float] = []
    heading_infos: list[dict] = []
    section_names: list[str] = []

    for para in docx.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Collect font info from runs
        for run in para.runs:
            run_text = run.text.strip()
            if not run_text:
                continue
            if run.font.name:
                font_counts[run.font.name] = (
                    font_counts.get(run.font.name, 0) + len(run_text)
                )
            if run.font.size:
                size_pt = round(run.font.size / 12700, 1)
                size_counts[size_pt] = size_counts.get(size_pt, 0) + len(run_text)

        # Line spacing
        pf = para.paragraph_format
        if pf.line_spacing is not None:
            try:
                spacing_val = float(pf.line_spacing)
                # python-docx returns line_spacing as a float multiplier
                # or as EMU for exact spacing
                if spacing_val < 10:
                    line_spacings.append(spacing_val)
                else:
                    # EMU value; convert to approximate multiplier
                    # 240 twips = single, 480 = double
                    line_spacings.append(round(spacing_val / 914400 * 72 / 12, 1))
            except (TypeError, ValueError):
                pass

        # Indentation
        is_body = len(text) > 100  # heuristic: body paragraphs are longer
        if is_body and pf.first_line_indent is not None:
            try:
                indent_in = round(pf.first_line_indent / 914400, 2)
                if 0 < indent_in < 2:
                    indent_values.append(indent_in)
            except (TypeError, ValueError):
                pass

        # Block quote detection: left indent > 0 and text is medium-length
        if pf.left_indent is not None:
            try:
                left_in = round(pf.left_indent / 914400, 2)
                if 0.3 < left_in < 3.0 and 30 < len(text) < 500:
                    block_quote_indents.append(left_in)
            except (TypeError, ValueError):
                pass

        # Heading detection
        is_bold = bool(para.runs and all(
            run.bold for run in para.runs if run.text.strip()
        ))
        is_centered = para.alignment == WD_ALIGN_PARAGRAPH.CENTER
        alpha_chars = [c for c in text if c.isalpha()]
        is_all_caps = bool(alpha_chars) and all(c.isupper() for c in alpha_chars)
        is_short = len(text) < 120

        if is_short and (is_bold or is_centered or is_all_caps):
            # Determine font size for this heading
            h_size = None
            for run in para.runs:
                if run.font.size and run.text.strip():
                    h_size = round(run.font.size / 12700, 1)
                    break

            heading_infos.append({
                "text": text,
                "bold": is_bold,
                "centered": is_centered,
                "all_caps": is_all_caps,
                "font_size": h_size,
            })

            # Track section names
            section_names.append(text)

    # -- Build font patterns --
    font_patterns = []
    if font_counts:
        dominant_font = max(font_counts, key=font_counts.get)
        dominant_size = max(size_counts, key=size_counts.get) if size_counts else 12.0
        font_patterns.append(FontPattern(
            font_name=dominant_font,
            font_size_pt=dominant_size,
        ))
        # Add secondary fonts if significantly used
        total_chars = sum(font_counts.values())
        for fname, count in sorted(font_counts.items(), key=lambda x: -x[1]):
            if fname == dominant_font:
                continue
            ratio = count / total_chars
            if ratio > 0.1:
                # Find most common size for this font
                font_patterns.append(FontPattern(
                    font_name=fname,
                    font_size_pt=dominant_size,
                ))

    # -- Build heading patterns --
    heading_patterns = _classify_headings(heading_infos)

    # -- Build section patterns --
    section_patterns = _match_sections(section_names)

    # -- Line spacing --
    avg_spacing = None
    if line_spacings:
        avg_spacing = round(sum(line_spacings) / len(line_spacings), 1)

    # -- Paragraph indent --
    avg_indent = None
    if indent_values:
        avg_indent = round(sum(indent_values) / len(indent_values), 2)

    # -- Block quote indent --
    avg_bq_indent = None
    if block_quote_indents:
        avg_bq_indent = round(
            sum(block_quote_indents) / len(block_quote_indents), 2
        )

    return BriefAnalysis(
        id=str(uuid.uuid4()),
        source_filename=path.name,
        jurisdiction=jurisdiction,
        court_level=court_level,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        font_patterns=font_patterns,
        margin_pattern=margin_pattern,
        line_spacing=avg_spacing,
        heading_patterns=heading_patterns,
        section_patterns=section_patterns,
        paragraph_indent_inches=avg_indent,
        block_quote_indent_inches=avg_bq_indent,
    )


def _analyze_pdf(
    path: Path,
    jurisdiction: str | None,
    court_level: str | None,
) -> BriefAnalysis:
    """Extract formatting patterns from a PDF file using PyMuPDF."""
    import fitz

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        raise ValueError(f"Could not open PDF file: {exc}") from exc

    try:
        return _analyze_pdf_doc(doc, path, jurisdiction, court_level)
    finally:
        doc.close()


def _analyze_pdf_doc(
    doc,
    path: Path,
    jurisdiction: str | None,
    court_level: str | None,
) -> BriefAnalysis:
    """Internal PDF analysis with an open fitz.Document."""
    import fitz

    font_counts: dict[str, int] = {}
    size_counts: dict[float, int] = {}
    heading_infos: list[dict] = []
    section_names: list[str] = []

    # Margin estimation
    min_x = float("inf")
    max_x = 0.0
    min_y = float("inf")
    max_y = 0.0

    page_rect = doc[0].rect if len(doc) > 0 else fitz.Rect(0, 0, 612, 792)

    # Line spacing estimation: track vertical gaps between text lines
    prev_line_bottom: float | None = None
    prev_line_height: float | None = None
    line_gaps: list[float] = []

    # Indentation estimation
    left_margins_body: list[float] = []

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

                # Font analysis from all spans
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

                # Margin estimation from text boundaries
                if len(line_text) > 5:
                    min_x = min(min_x, bbox[0])
                    max_x = max(max_x, bbox[2])
                    min_y = min(min_y, bbox[1])
                    max_y = max(max_y, bbox[3])

                # Line spacing estimation
                line_height = bbox[3] - bbox[1]
                if prev_line_bottom is not None and prev_line_height is not None:
                    gap = bbox[1] - prev_line_bottom
                    # Only consider reasonable gaps (same column, not page break)
                    if 0 < gap < prev_line_height * 4:
                        spacing_ratio = (line_height + gap) / line_height if line_height > 0 else 0
                        if 0.5 < spacing_ratio < 5:
                            line_gaps.append(spacing_ratio)
                prev_line_bottom = bbox[3]
                prev_line_height = line_height

                # Body text indentation (long lines)
                if len(line_text) > 80:
                    left_margins_body.append(bbox[0])

                # Heading detection
                first_span = spans[0]
                flags = first_span.get("flags", 0)
                is_bold = bool(flags & (1 << 4))
                font_size = round(first_span.get("size", 0), 1)

                line_center = (bbox[0] + bbox[2]) / 2
                page_center = page_rect.width / 2
                is_centered = abs(line_center - page_center) < 36

                alpha_chars = [c for c in line_text if c.isalpha()]
                is_all_caps = (
                    bool(alpha_chars)
                    and all(c.isupper() for c in alpha_chars)
                    and len(alpha_chars) >= 3
                )
                is_short = len(line_text) < 120

                if is_short and (is_bold or is_centered or is_all_caps):
                    heading_infos.append({
                        "text": line_text,
                        "bold": is_bold,
                        "centered": is_centered,
                        "all_caps": is_all_caps,
                        "font_size": font_size,
                    })
                    section_names.append(line_text)

    # -- Build results --
    margin_pattern = None
    if min_x < float("inf"):
        margin_pattern = MarginPattern(
            top=round(min_y / 72, 2),
            bottom=round((page_rect.height - max_y) / 72, 2),
            left=round(min_x / 72, 2),
            right=round((page_rect.width - max_x) / 72, 2),
        )

    font_patterns = []
    if font_counts:
        dominant_font = max(font_counts, key=font_counts.get)
        dominant_size = max(size_counts, key=size_counts.get) if size_counts else 12.0
        font_patterns.append(FontPattern(
            font_name=dominant_font,
            font_size_pt=dominant_size,
        ))
        total_chars = sum(font_counts.values())
        for fname, count in sorted(font_counts.items(), key=lambda x: -x[1]):
            if fname == dominant_font:
                continue
            if count / total_chars > 0.1:
                font_patterns.append(FontPattern(
                    font_name=fname,
                    font_size_pt=dominant_size,
                ))

    heading_patterns = _classify_headings(heading_infos)
    section_patterns = _match_sections(section_names)

    # Line spacing
    avg_spacing = None
    if line_gaps:
        # Round to nearest common value (1.0, 1.5, 2.0)
        raw_avg = sum(line_gaps) / len(line_gaps)
        for candidate in [1.0, 1.15, 1.5, 2.0, 2.5, 3.0]:
            if abs(raw_avg - candidate) < 0.3:
                avg_spacing = candidate
                break
        if avg_spacing is None:
            avg_spacing = round(raw_avg, 1)

    # Paragraph indent estimation from body text left margins
    avg_indent = None
    if left_margins_body:
        base_margin = min(left_margins_body)
        indents = [
            round((x - base_margin) / 72, 2)
            for x in left_margins_body
            if (x - base_margin) / 72 > 0.2
        ]
        if indents:
            avg_indent = round(sum(indents) / len(indents), 2)

    return BriefAnalysis(
        id=str(uuid.uuid4()),
        source_filename=path.name,
        jurisdiction=jurisdiction,
        court_level=court_level,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        font_patterns=font_patterns,
        margin_pattern=margin_pattern,
        line_spacing=avg_spacing,
        heading_patterns=heading_patterns,
        section_patterns=section_patterns,
        paragraph_indent_inches=avg_indent,
        block_quote_indent_inches=None,  # Hard to detect reliably from PDF
    )


def _classify_headings(heading_infos: list[dict]) -> list[HeadingPattern]:
    """Classify detected headings into level patterns."""
    level_groups: dict[int, list[dict]] = {}

    for info in heading_infos:
        text = info["text"]
        is_all_caps = info["all_caps"]
        is_centered = info["centered"]
        is_bold = info["bold"]

        # Determine level
        level = _detect_heading_level(text, is_all_caps, is_centered, is_bold)
        level_groups.setdefault(level, []).append(info)

    patterns = []
    for level, items in sorted(level_groups.items()):
        # Determine dominant case style
        caps_count = sum(1 for i in items if i["all_caps"])
        if caps_count > len(items) / 2:
            case_style = "upper"
        else:
            # Check if title case or sentence case
            title_count = sum(
                1 for i in items
                if not i["all_caps"] and _is_title_case(i["text"])
            )
            if title_count > len(items) / 3:
                case_style = "title"
            else:
                case_style = "sentence"

        # Dominant alignment
        centered_count = sum(1 for i in items if i["centered"])
        alignment = "center" if centered_count > len(items) / 2 else "left"

        # Dominant bold
        bold_count = sum(1 for i in items if i["bold"])
        bold = bold_count > len(items) / 2

        # Font size (most common among heading items with font info)
        sizes = [i["font_size"] for i in items if i.get("font_size")]
        font_size = None
        if sizes:
            # Most frequent size
            size_freq: dict[float, int] = {}
            for s in sizes:
                size_freq[s] = size_freq.get(s, 0) + 1
            font_size = max(size_freq, key=size_freq.get)

        # Numbering detection
        numbering = _detect_numbering_style(items)

        patterns.append(HeadingPattern(
            level=level,
            case_style=case_style,
            alignment=alignment,
            bold=bold,
            font_size_pt=font_size,
            numbering=numbering,
        ))

    return patterns


def _detect_heading_level(
    text: str, is_all_caps: bool, is_centered: bool, is_bold: bool
) -> int:
    """Assign a heading level based on formatting cues."""
    from legal_format_engine.utils.numbering import strip_numbering_prefix

    # Check for numbering prefix
    prefix, _ = strip_numbering_prefix(text)
    if prefix:
        prefix_clean = prefix.rstrip(".")
        if re.match(r"^[IVXLC]+$", prefix_clean, re.IGNORECASE):
            return 2
        elif re.match(r"^[A-Z]$", prefix_clean):
            return 3
        elif re.match(r"^\d+$", prefix_clean):
            return 4

    if is_all_caps:
        return 1
    if is_bold and is_centered:
        return 1
    if is_bold:
        return 2
    if is_centered:
        return 1
    return 2


def _detect_numbering_style(items: list[dict]) -> str | None:
    """Detect the numbering style used by a group of headings."""
    from legal_format_engine.utils.numbering import strip_numbering_prefix

    roman_count = 0
    alpha_upper_count = 0
    arabic_count = 0

    for item in items:
        prefix, _ = strip_numbering_prefix(item["text"])
        if not prefix:
            continue
        prefix_clean = prefix.rstrip(".")
        if re.match(r"^[IVXLC]+$", prefix_clean, re.IGNORECASE):
            roman_count += 1
        elif re.match(r"^[A-Z]$", prefix_clean):
            alpha_upper_count += 1
        elif re.match(r"^\d+$", prefix_clean):
            arabic_count += 1

    counts = {
        "roman": roman_count,
        "alpha_upper": alpha_upper_count,
        "arabic": arabic_count,
    }
    best = max(counts, key=counts.get)
    if counts[best] > 0:
        return best
    return None


def _is_title_case(text: str) -> bool:
    """Check if text is roughly in title case."""
    words = text.split()
    if len(words) < 2:
        return False
    # Minor words that may be lowercase in title case
    minor = {"a", "an", "the", "and", "but", "or", "nor", "for", "in", "on",
             "at", "to", "of", "by", "with", "from"}
    titled = 0
    for i, word in enumerate(words):
        clean = re.sub(r"[^\w]", "", word)
        if not clean:
            continue
        if clean[0].isupper():
            titled += 1
        elif i > 0 and clean.lower() in minor:
            titled += 1  # minor words are OK lowercase
    return titled >= len(words) * 0.6


def _match_sections(section_names: list[str]) -> list[SectionPattern]:
    """Match detected section names against known legal section patterns."""
    patterns: list[SectionPattern] = []
    seen_ids: set[str] = set()

    for order, name in enumerate(section_names):
        name_lower = name.lower().strip()
        # Strip numbering prefixes for matching
        from legal_format_engine.utils.numbering import strip_numbering_prefix
        _, stripped = strip_numbering_prefix(name)
        stripped_lower = stripped.lower().strip()

        matched_id = None
        for section_id, aliases in _LEGAL_SECTIONS.items():
            for alias in aliases:
                if alias in stripped_lower or stripped_lower in alias:
                    matched_id = section_id
                    break
            if matched_id:
                break

        if matched_id and matched_id not in seen_ids:
            seen_ids.add(matched_id)
            patterns.append(SectionPattern(
                id=matched_id,
                common_names=[name],
                frequency=1.0,
                typical_order=order,
            ))

    return patterns
