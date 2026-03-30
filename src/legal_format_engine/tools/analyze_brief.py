"""Brief analysis tool - extracts formatting patterns from uploaded documents."""

from __future__ import annotations
from pathlib import Path


def analyze_directory(directory: str | Path) -> list[dict]:
    """Analyze all DOCX/PDF files in a directory."""
    dir_path = Path(directory)
    results = []

    for f in sorted(dir_path.iterdir()):
        if f.suffix.lower() == ".docx":
            results.append(_analyze_docx(f))
        elif f.suffix.lower() == ".pdf":
            results.append(_analyze_pdf(f))

    return results


def _analyze_docx(path: Path) -> dict:
    from legal_format_engine.parsers.docx_parser import extract_format_profile
    profile = extract_format_profile(path)
    return _profile_to_dict(path.name, profile)


def _analyze_pdf(path: Path) -> dict:
    from legal_format_engine.parsers.pdf_parser import extract_format_profile
    profile = extract_format_profile(path)
    return _profile_to_dict(path.name, profile)


def _profile_to_dict(file_name: str, profile) -> dict:
    result = {"file_name": file_name}

    if profile.fonts:
        dominant = profile.fonts[0]
        result["dominant_font"] = f"{dominant.font_name} {dominant.font_size_pt}pt"

    if profile.margins:
        result["margins"] = {
            "top": profile.margins.top_inches,
            "bottom": profile.margins.bottom_inches,
            "left": profile.margins.left_inches,
            "right": profile.margins.right_inches,
        }

    if profile.headings:
        result["headings"] = [
            {"text": h.text, "level": h.level, "bold": h.bold, "all_caps": h.all_caps}
            for h in profile.headings
        ]

    return result
