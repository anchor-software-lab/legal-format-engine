"""Tests for `build_skill_bundle` and the rendered helper script."""

from __future__ import annotations

import ast
import zipfile
from pathlib import Path

import pytest

from legal_skill_kit import (
    DEFAULT_API_BASE_URL,
    DEFAULT_SKILL_NAME,
    DEFAULT_SKILL_VERSION,
    build_skill_bundle,
)


def test_builds_expected_files(tmp_path: Path):
    bundle = build_skill_bundle(tmp_path)
    assert bundle.name == DEFAULT_SKILL_NAME
    assert bundle.root == tmp_path / DEFAULT_SKILL_NAME

    expected = {
        bundle.root / "SKILL.md",
        bundle.root / "scripts" / "qg_check.py",
    }
    assert set(bundle.files) == expected
    for f in bundle.files:
        assert f.exists()
        assert f.stat().st_size > 0


def test_skill_md_contains_required_metadata(tmp_path: Path):
    bundle = build_skill_bundle(tmp_path, version="9.9.9")
    content = (bundle.root / "SKILL.md").read_text()
    # Frontmatter delimited by ---.
    assert content.startswith("---\n")
    assert "version: 9.9.9" in content
    assert f"name: {DEFAULT_SKILL_NAME}" in content
    assert "trigger_phrases:" in content
    assert "cite check this brief" in content
    assert "is this case still good law" in content


def test_qg_check_script_is_valid_python(tmp_path: Path):
    """The rendered helper must parse — catches Jinja syntax mishaps."""
    bundle = build_skill_bundle(tmp_path)
    source = (bundle.root / "scripts" / "qg_check.py").read_text()
    ast.parse(source)  # raises SyntaxError if the template produced bad Python


def test_qg_check_script_is_executable(tmp_path: Path):
    bundle = build_skill_bundle(tmp_path)
    qg = bundle.root / "scripts" / "qg_check.py"
    # 0o755 = u+rwx, g+rx, o+rx; mask everything but the user-exec bit.
    assert qg.stat().st_mode & 0o100, "qg_check.py must be u+x"


def test_qg_check_baked_api_base_url(tmp_path: Path):
    bundle = build_skill_bundle(tmp_path, api_base_url="https://example.test/api/v9")
    src = (bundle.root / "scripts" / "qg_check.py").read_text()
    assert 'DEFAULT_BASE_URL = "https://example.test/api/v9"' in src


def test_default_api_base_url_when_unset(tmp_path: Path):
    bundle = build_skill_bundle(tmp_path)
    src = (bundle.root / "scripts" / "qg_check.py").read_text()
    assert f'DEFAULT_BASE_URL = "{DEFAULT_API_BASE_URL}"' in src


def test_default_version_when_unset(tmp_path: Path):
    bundle = build_skill_bundle(tmp_path)
    md = (bundle.root / "SKILL.md").read_text()
    assert f"version: {DEFAULT_SKILL_VERSION}" in md


def test_archive_produces_zip_alongside_directory(tmp_path: Path):
    bundle = build_skill_bundle(tmp_path)
    assert bundle.archive is not None
    assert bundle.archive.exists()
    assert bundle.archive.suffix == ".zip"
    with zipfile.ZipFile(bundle.archive) as zf:
        names = set(zf.namelist())
    # Files inside the zip are rooted at the bundle name.
    assert f"{DEFAULT_SKILL_NAME}/SKILL.md" in names
    assert f"{DEFAULT_SKILL_NAME}/scripts/qg_check.py" in names


def test_no_archive_skips_zip(tmp_path: Path):
    bundle = build_skill_bundle(tmp_path, archive=False)
    assert bundle.archive is None
    assert not (tmp_path / f"{DEFAULT_SKILL_NAME}.zip").exists()


def test_overwrite_replaces_existing_directory(tmp_path: Path):
    bundle1 = build_skill_bundle(tmp_path)
    # Touch a stale file inside the bundle dir.
    stale = bundle1.root / "STALE.txt"
    stale.write_text("leftover")
    bundle2 = build_skill_bundle(tmp_path, overwrite=True)
    # Stale file is gone after rebuild.
    assert not stale.exists()
    assert (bundle2.root / "SKILL.md").exists()


def test_no_overwrite_raises_when_directory_exists(tmp_path: Path):
    build_skill_bundle(tmp_path)
    with pytest.raises(FileExistsError):
        build_skill_bundle(tmp_path, overwrite=False)


def test_helper_script_uses_correct_api_endpoints(tmp_path: Path):
    """The helper must POST to /documents and /runs, GET /runs/{id}."""
    bundle = build_skill_bundle(tmp_path)
    src = (bundle.root / "scripts" / "qg_check.py").read_text()
    assert '"/documents"' in src
    assert '"/documents/encrypted"' in src
    assert '"/runs"' in src
    assert '/orgs/me/public-key' in src
    # And the auth header / env-var contract.
    assert "X-Anchor-API-Key" in src
    assert "ANCHOR_API_KEY" in src
