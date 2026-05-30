"""Builds the distributable Claude skill bundle.

Public surface:
- `build_skill_bundle(out_dir, *, api_base_url, name, version, archive)`
  renders the templates in `legal_skill_kit/templates/` into
  `<out_dir>/<name>/` and optionally zips them into
  `<out_dir>/<name>.zip`.
- `SkillBundle` — dataclass returned by build_skill_bundle.
- Module-level defaults: `DEFAULT_API_BASE_URL`, `DEFAULT_SKILL_NAME`,
  `DEFAULT_SKILL_VERSION`.

The bundle is self-contained: SKILL.md describes the skill's
triggers and behavior; `scripts/qg_check.py` is a stdlib + httpx
helper that talks to the Anchor SaaS API.
"""

from legal_skill_kit.build import (
    DEFAULT_API_BASE_URL,
    DEFAULT_SKILL_NAME,
    DEFAULT_SKILL_VERSION,
    SkillBundle,
    build_skill_bundle,
)

__all__ = [
    "DEFAULT_API_BASE_URL",
    "DEFAULT_SKILL_NAME",
    "DEFAULT_SKILL_VERSION",
    "SkillBundle",
    "build_skill_bundle",
]
