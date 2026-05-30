"""Build the distributable Claude skill bundle.

Renders the templates in `legal_skill_kit/templates/` into a directory
ready for distribution. The bundle is two files:

  <out>/
    SKILL.md          — frontmatter + triggers + description Claude reads
    scripts/qg_check.py — Python helper that calls the SaaS API

Optionally zips the directory into `<out>/anchor-quality-gate.zip` for
upload to claude.ai/code's skills page.

The bundle is self-contained: it imports only stdlib + `httpx`,
authenticates with `ANCHOR_API_KEY` from env, and talks to whatever
base URL the user passed at build time (defaults to the production
API).
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from importlib.resources import files as resource_files
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

DEFAULT_API_BASE_URL = "https://api.anchorlabs.dev/v1"
DEFAULT_SKILL_NAME = "anchor-quality-gate"
DEFAULT_SKILL_VERSION = "0.1.0"


@dataclass
class SkillBundle:
    """Result of `build_skill_bundle`. Paths are absolute."""

    name: str
    root: Path
    files: list[Path]
    archive: Path | None = None


def build_skill_bundle(
    out_dir: str | Path,
    *,
    api_base_url: str = DEFAULT_API_BASE_URL,
    name: str = DEFAULT_SKILL_NAME,
    version: str = DEFAULT_SKILL_VERSION,
    archive: bool = True,
    overwrite: bool = True,
) -> SkillBundle:
    """Render the skill templates into `<out_dir>/<name>/`.

    Args:
      out_dir: directory that will contain `<name>/` and (if `archive`)
        `<name>.zip`.
      api_base_url: base URL the skill's helper script will call.
      name: skill directory name (default `anchor-quality-gate`).
      version: rendered into SKILL.md frontmatter.
      archive: also write a zip alongside the directory.
      overwrite: remove an existing `<name>/` before rendering.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_root = out_dir / name
    if bundle_root.exists():
        if not overwrite:
            raise FileExistsError(f"{bundle_root} already exists and overwrite=False")
        shutil.rmtree(bundle_root)

    bundle_root.mkdir()
    scripts_dir = bundle_root / "scripts"
    scripts_dir.mkdir()

    env = Environment(
        loader=PackageLoader("legal_skill_kit", "templates"),
        autoescape=select_autoescape(disabled_extensions=("md", "py")),
        keep_trailing_newline=True,
    )
    context: dict[str, Any] = {
        "name": name,
        "version": version,
        "api_base_url": api_base_url,
    }

    skill_md_path = bundle_root / "SKILL.md"
    skill_md_path.write_text(env.get_template("SKILL.md.j2").render(**context))

    qg_check_path = scripts_dir / "qg_check.py"
    qg_check_path.write_text(env.get_template("qg_check.py.j2").render(**context))
    qg_check_path.chmod(0o755)

    files = [skill_md_path, qg_check_path]

    archive_path: Path | None = None
    if archive:
        archive_path = out_dir / f"{name}.zip"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in files:
                zf.write(file, arcname=file.relative_to(bundle_root.parent))

    return SkillBundle(name=name, root=bundle_root, files=files, archive=archive_path)
