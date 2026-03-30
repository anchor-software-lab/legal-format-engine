"""Rules loader - loads YAML rulesets into Ruleset models."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import yaml

from legal_format_engine.models.section import (
    CertificationTemplate,
    HeadingLevel,
    HeadingRule,
    PageFormat,
    Ruleset,
    SectionRule,
)

RULESETS_DIR = Path(__file__).parent / "rulesets"


def load_ruleset(
    jurisdiction: str,
    document_type: str,
    variant: Optional[str] = None,
) -> Ruleset:
    """Load a ruleset from YAML file.

    Args:
        jurisdiction: e.g. 'wisconsin', 'california', 'seventh_circuit'
        document_type: e.g. 'appellate_brief', 'circuit_motion'
        variant: optional variant name
    """
    # Try jurisdiction-specific directory first
    if variant:
        filename = f"{variant}_{document_type}.yaml"
    else:
        filename = f"{document_type}.yaml"

    path = RULESETS_DIR / jurisdiction / filename
    if not path.exists():
        raise FileNotFoundError(f"Ruleset not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    return _parse_ruleset(data)


def _parse_ruleset(data: dict) -> Ruleset:
    """Parse raw YAML data into a Ruleset model."""
    page_format = PageFormat(**data.get("page_format", {}))

    heading_rules = []
    for hr in data.get("heading_rules", []):
        heading_rules.append(HeadingRule(
            level=hr["level"],
            style=HeadingLevel(hr["style"]),
            bold=hr.get("bold", True),
            centered=hr.get("centered", False),
            indent_inches=hr.get("indent_inches", 0.0),
        ))

    section_rules = []
    for sr in data.get("section_rules", []):
        section_rules.append(SectionRule(
            section_type=sr["section_type"],
            title=sr.get("title"),
            required=sr.get("required", True),
            order=sr.get("order", 0),
            heading_level=sr.get("heading_level", 1),
            aliases=sr.get("aliases", []),
            group=sr.get("group"),
        ))

    cert_templates = []
    for ct in data.get("certification_templates", []):
        cert_templates.append(CertificationTemplate(
            cert_type=ct["cert_type"],
            title=ct.get("title"),
            template=ct["template"],
            required=ct.get("required", True),
        ))

    return Ruleset(
        name=data.get("name", ""),
        jurisdiction=data.get("jurisdiction", ""),
        court_level=data.get("court_level", ""),
        document_type=data.get("document_type", ""),
        description=data.get("description"),
        statute_reference=data.get("statute_reference"),
        page_format=page_format,
        heading_rules=heading_rules,
        section_rules=section_rules,
        certification_templates=cert_templates,
        page_limit=data.get("page_limit"),
        word_limit=data.get("word_limit"),
        allow_combined_case_facts=data.get("allow_combined_case_facts", False),
    )


def list_rulesets() -> list[dict[str, str]]:
    """List all available rulesets."""
    results = []
    for jurisdiction_dir in sorted(RULESETS_DIR.iterdir()):
        if not jurisdiction_dir.is_dir():
            continue
        for yaml_file in sorted(jurisdiction_dir.glob("*.yaml")):
            results.append({
                "jurisdiction": jurisdiction_dir.name,
                "document_type": yaml_file.stem,
                "path": str(yaml_file),
            })
    return results
