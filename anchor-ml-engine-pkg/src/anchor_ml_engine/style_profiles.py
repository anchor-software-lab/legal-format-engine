"""Style profiles: learned formatting preferences per author or organization.

Authors and organizations develop distinct formatting styles within the bounds
of rules. This module tracks those preferences so the engine can:

1. Apply an author's/org's preferred style when formatting new documents
2. Detect when a formatting choice is a deliberate style vs. a mistake
3. Offer "format like [organization]" as a feature

Style profiles are built from ingested documents tagged with author/organization.
They capture ONLY discretionary choices -- things the rules don't specify.
If a rule mandates 1" margins, the profile doesn't store margins.
If the rule is silent on first-line indent, the profile learns it.

Example discretionary choices:
- First-line paragraph indent (0.5" vs 0.3")
- Block quote indent depth
- Heading numbering style when rule doesn't specify
- Spacing between sections
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anchor_ml_engine.models import (
    NormalizedDocument,
    StylePreference,
    StyleProfile,
)


# Discretionary formatting fields -- things rules typically DON'T specify.
# These are safe to learn from individual authors/organizations.
DISCRETIONARY_FIELDS = {
    # Paragraph formatting
    "body_first_line_indent",
    "body_space_after_pt",
    "body_space_before_pt",
    "body_alignment",

    # Block quote formatting
    "block_quote_left_indent",
    "block_quote_right_indent",
    "block_quote_font_size_offset",  # relative to body (e.g., -1pt)
    "block_quote_line_spacing",

    # Footnote formatting
    "footnote_font_size_pt",
    "footnote_line_spacing",

    # Heading details (when rules specify level but not all details)
    "heading_space_before_pt",
    "heading_space_after_pt",

    # Caption preferences
    "caption_party_separator_caps",  # "v." vs "V." vs "vs."
    "caption_extra_spacing",

    # Signature block preferences
    "signature_line_style",  # "Respectfully submitted," vs alternatives
    "signature_date_format",

    # Section ordering preferences (for optional sections)
    "introduction_included",
    "summary_of_argument_included",
    "standard_of_review_separate",
}


class StyleProfileStore:
    """Manages style profiles on disk."""

    def __init__(self, store_dir: Path | None = None):
        self._dir = store_dir or Path.home() / ".anchor-ml-engine" / "style_profiles"
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, profile: StyleProfile) -> None:
        """Save or update a style profile."""
        safe_name = profile.name.lower().replace(" ", "_").replace(",", "")
        filename = f"{profile.profile_type}_{safe_name}.json"
        path = self._dir / filename
        path.write_text(json.dumps(profile.to_dict(), indent=2, default=str))

    def load(self, profile_type: str, name: str) -> StyleProfile | None:
        """Load a profile by type and name."""
        safe_name = name.lower().replace(" ", "_").replace(",", "")
        filename = f"{profile_type}_{safe_name}.json"
        path = self._dir / filename
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return StyleProfile.from_dict(data)

    def list_all(self) -> list[StyleProfile]:
        """List all saved profiles."""
        profiles = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                profiles.append(StyleProfile.from_dict(data))
            except Exception:
                continue
        return profiles

    def delete(self, profile_type: str, name: str) -> bool:
        safe_name = name.lower().replace(" ", "_").replace(",", "")
        filename = f"{profile_type}_{safe_name}.json"
        path = self._dir / filename
        if path.exists():
            path.unlink()
            return True
        return False


def build_style_profile(
    documents: list[tuple[NormalizedDocument, dict]],
    profile_type: str,
    name: str,
    rule_governed_fields: set[str] | None = None,
) -> StyleProfile:
    """Build a style profile from a set of documents by the same author/org.

    Args:
        documents: List of (NormalizedDocument, storage_record_dict) tuples
        profile_type: "author" or "organization"
        name: Author or organization name
        rule_governed_fields: Set of field names that are governed by
            rules for these documents. These will NOT be included in the
            profile -- only discretionary fields are learned.

    Returns:
        StyleProfile with learned discretionary preferences.
    """
    rule_governed = rule_governed_fields or set()
    profile = StyleProfile(
        profile_type=profile_type,
        name=name,
        document_count=len(documents),
    )

    # Collect categories
    categories = set()
    for doc, _ in documents:
        if doc.category:
            categories.add(doc.category)
    profile.categories = sorted(categories)

    # Extract discretionary feature values from each document
    field_values: dict[str, list[Any]] = {}

    for doc, _ in documents:
        # Body paragraph formatting
        for ps in doc.paragraph_styles:
            if ps.context == "body":
                _collect(field_values, "body_first_line_indent",
                         ps.first_line_indent, rule_governed)
                _collect(field_values, "body_space_after_pt",
                         ps.space_after_pt, rule_governed)
                _collect(field_values, "body_space_before_pt",
                         ps.space_before_pt, rule_governed)
                _collect(field_values, "body_alignment",
                         ps.alignment, rule_governed)

            elif ps.context == "block_quote":
                _collect(field_values, "block_quote_left_indent",
                         ps.left_indent, rule_governed)
                _collect(field_values, "block_quote_line_spacing",
                         ps.line_spacing, rule_governed)

            elif ps.context == "footnote":
                _collect(field_values, "footnote_font_size_pt",
                         ps.font_size_pt, rule_governed)
                _collect(field_values, "footnote_line_spacing",
                         ps.line_spacing, rule_governed)

        # Section inclusion preferences
        section_ids = {s.id for s in doc.sections}
        _collect(field_values, "introduction_included",
                 "introduction" in section_ids, rule_governed)
        _collect(field_values, "summary_of_argument_included",
                 "summary_of_argument" in section_ids, rule_governed)
        _collect(field_values, "standard_of_review_separate",
                 "standard_of_review" in section_ids, rule_governed)

    # Build preferences from collected values
    for field_name, values in field_values.items():
        if not values:
            continue

        # For numerical values: use most common (mode)
        # For categorical/bool: use majority vote
        counter = Counter(str(v) for v in values)
        most_common_str, count = counter.most_common(1)[0]
        consistency = count / len(values)

        # Convert back to original type
        value: Any = most_common_str
        if most_common_str in ("True", "False"):
            value = most_common_str == "True"
        else:
            try:
                value = float(most_common_str)
                if value == int(value):
                    value = int(value)
            except ValueError:
                pass

        # Only include if reasonably consistent (>50% agreement)
        if consistency >= 0.5:
            profile.preferences.append(StylePreference(
                field=field_name,
                value=value,
                sample_count=len(values),
                consistency=round(consistency, 3),
            ))

    profile.updated_at = datetime.now(timezone.utc).isoformat()
    return profile


def _collect(
    field_values: dict[str, list],
    field_name: str,
    value: Any,
    rule_governed: set[str],
) -> None:
    """Collect a value only if the field is discretionary (not rule-governed)."""
    if field_name in rule_governed:
        return
    if field_name not in DISCRETIONARY_FIELDS:
        return
    if value is None:
        return
    field_values.setdefault(field_name, []).append(value)
