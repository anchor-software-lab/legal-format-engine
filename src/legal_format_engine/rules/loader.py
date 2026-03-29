"""Load and validate ruleset YAML files."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml

from legal_format_engine.rules.schema import Ruleset


def load_ruleset(
    jurisdiction: str,
    court_level: str,
    document_type: str,
    variant: str | None = None,
) -> Ruleset:
    """Load a ruleset from the bundled YAML files.

    Looks up: rulesets/{jurisdiction}/{variant}_{court_level}_{document_type}.yaml
    Falls back to: rulesets/{jurisdiction}/{court_level}_{document_type}.yaml

    Args:
        jurisdiction: e.g., "wisconsin"
        court_level: e.g., "appellate"
        document_type: e.g., "brief"
        variant: e.g., "spd" for State Public Defender format

    Returns:
        A validated Ruleset object.

    Raises:
        FileNotFoundError: If no matching ruleset file exists.
        ValueError: If the YAML is invalid or fails validation.
    """
    # Try variant-specific file first, then fall back to generic
    if variant:
        filenames = [
            f"{variant}_{court_level}_{document_type}.yaml",
            f"{court_level}_{document_type}.yaml",
        ]
    else:
        filenames = [f"{court_level}_{document_type}.yaml"]

    yaml_text = None
    for filename in filenames:
        # Try package resources first (works when installed)
        try:
            rulesets_pkg = resources.files("legal_format_engine.rules.rulesets")
            yaml_path = rulesets_pkg / jurisdiction / filename
            yaml_text = yaml_path.read_text(encoding="utf-8")
            break
        except (FileNotFoundError, TypeError, ModuleNotFoundError):
            # Fall back to filesystem path (development)
            base = Path(__file__).parent / "rulesets" / jurisdiction / filename
            if base.exists():
                yaml_text = base.read_text(encoding="utf-8")
                break

    if yaml_text is None:
        variant_label = f" (variant: {variant})" if variant else ""
        raise FileNotFoundError(
            f"No ruleset found for {jurisdiction}/{court_level}_{document_type}"
            f"{variant_label}. Tried: {filenames}"
        )

    data = yaml.safe_load(yaml_text)
    if not isinstance(data, dict):
        raise ValueError(f"Ruleset file must contain a YAML mapping, got {type(data)}")

    return Ruleset.model_validate(data)


def load_ruleset_from_file(path: str | Path) -> Ruleset:
    """Load a ruleset from an arbitrary YAML file path.

    Useful for custom/user-provided rulesets.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Ruleset file not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Ruleset file must contain a YAML mapping, got {type(data)}")

    return Ruleset.model_validate(data)
