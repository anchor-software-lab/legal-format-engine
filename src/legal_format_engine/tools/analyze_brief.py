"""Brief analysis tool.

Reads reference DOCX briefs and extracts formatting patterns
to refine rulesets. Run this after uploading briefs to reference/briefs/.

Usage:
    python -m legal_format_engine.tools.analyze_brief reference/briefs/christopherson.docx
    python -m legal_format_engine.tools.analyze_brief reference/briefs/  # all briefs in dir
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from legal_format_engine.parsers.docx_parser import extract_format_profile, parse_docx


def analyze_brief(path: Path) -> dict:
    """Analyze a single DOCX brief and return its formatting profile."""
    print(f"\n{'='*70}")
    print(f"Analyzing: {path.name}")
    print(f"{'='*70}")

    # Extract formatting profile
    profile = extract_format_profile(path)

    # Page layout
    page = profile["page"]
    print(f"\n--- Page Layout ---")
    print(f"  Size: {page['width_inches']}\" x {page['height_inches']}\"")
    print(f"  Margins: T={page['margin_top_inches']}\" B={page['margin_bottom_inches']}\" "
          f"L={page['margin_left_inches']}\" R={page['margin_right_inches']}\"")

    # Fonts
    fonts = profile["fonts"]
    print(f"\n--- Fonts ---")
    print(f"  Dominant: {fonts['dominant']}")
    for name, count in list(fonts["all"].items())[:5]:
        print(f"    {name}: {count} chars")

    # Font sizes
    sizes = profile["font_sizes"]
    print(f"\n--- Font Sizes ---")
    print(f"  Dominant: {sizes['dominant_pt']}pt")
    for size, count in list(sizes["all_pt"].items())[:5]:
        print(f"    {size}pt: {count} chars")

    # Headings detected
    print(f"\n--- Headings Detected ({len(profile['headings'])}) ---")
    for h in profile["headings"]:
        level = h.get("detected_level", "?")
        props = []
        if h["bold"]:
            props.append("bold")
        if h["centered"]:
            props.append("centered")
        if h["all_caps"]:
            props.append("ALL CAPS")
        if h.get("style"):
            props.append(f"style={h['style']}")
        props_str = ", ".join(props) if props else "plain"
        print(f"  L{level}: \"{h['text']}\" [{props_str}]")

    # Parse into sections
    doc = parse_docx(path)
    print(f"\n--- Sections Parsed ({len(doc.sections)}) ---")
    for s in doc.sections:
        prefix = f"  [{s.heading_level.name}]"
        content_len = sum(len(b.text) for b in s.content)
        print(f"{prefix} \"{s.heading_text}\" ({content_len} chars content)")

    # All caps lines (potential section headings)
    if profile["all_caps_lines"]:
        print(f"\n--- All-Caps Lines ({len(profile['all_caps_lines'])}) ---")
        for line in profile["all_caps_lines"]:
            print(f"  \"{line}\"")

    return profile


def analyze_directory(dir_path: Path) -> list[dict]:
    """Analyze all DOCX files in a directory."""
    profiles = []
    docx_files = sorted(dir_path.glob("*.docx"))

    if not docx_files:
        print(f"No .docx files found in {dir_path}")
        return profiles

    print(f"Found {len(docx_files)} DOCX file(s) in {dir_path}")

    for docx_path in docx_files:
        try:
            profile = analyze_brief(docx_path)
            profile["filename"] = docx_path.name
            profiles.append(profile)
        except Exception as e:
            print(f"\nError analyzing {docx_path.name}: {e}")

    # Summary across all briefs
    if len(profiles) > 1:
        print(f"\n{'='*70}")
        print(f"SUMMARY ACROSS {len(profiles)} BRIEFS")
        print(f"{'='*70}")

        # Common fonts
        all_fonts: dict[str, int] = {}
        for p in profiles:
            for font, count in p["fonts"]["all"].items():
                all_fonts[font] = all_fonts.get(font, 0) + count
        print(f"\n--- Fonts (aggregate) ---")
        for font, count in sorted(all_fonts.items(), key=lambda x: -x[1])[:5]:
            print(f"  {font}: {count} chars")

        # Common margins
        margins = [p["page"] for p in profiles]
        print(f"\n--- Margins ---")
        for key in ["margin_top_inches", "margin_bottom_inches",
                     "margin_left_inches", "margin_right_inches"]:
            values = [m[key] for m in margins]
            if len(set(values)) == 1:
                print(f"  {key}: {values[0]}\" (consistent)")
            else:
                print(f"  {key}: {values} (varies!)")

        # All section headings found across briefs
        all_headings: dict[str, int] = {}
        for p in profiles:
            for h in p["headings"]:
                text = h["text"].upper()
                all_headings[text] = all_headings.get(text, 0) + 1
        print(f"\n--- Section Headings (frequency across briefs) ---")
        for heading, count in sorted(all_headings.items(), key=lambda x: -x[1]):
            marker = " *" if count == len(profiles) else ""
            print(f"  \"{heading}\": {count}/{len(profiles)}{marker}")

    return profiles


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m legal_format_engine.tools.analyze_brief <path>")
        print("  <path> can be a .docx file or a directory containing .docx files")
        sys.exit(1)

    target = Path(sys.argv[1])

    if target.is_dir():
        profiles = analyze_directory(target)
    elif target.suffix == ".docx":
        profile = analyze_brief(target)
        profiles = [profile]
    else:
        print(f"Error: {target} is not a .docx file or directory")
        sys.exit(1)

    # Save analysis as JSON
    output_path = Path("reference") / "analysis.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(profiles, f, indent=2, default=str)
    print(f"\nFull analysis saved to: {output_path}")


if __name__ == "__main__":
    main()
