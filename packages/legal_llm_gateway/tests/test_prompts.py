"""Tests for the prompt loader."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from legal_llm_gateway import (
    ModelClass,
    PromptNotFound,
    PromptParseError,
    load_prompt,
)


def _write_prompt(dir_: Path, filename: str, content: str) -> Path:
    path = dir_ / filename
    path.write_text(textwrap.dedent(content).lstrip())
    return path


def test_load_well_formed_prompt(tmp_path):
    _write_prompt(
        tmp_path,
        "test.example.md",
        """
        ---
        id: test.example@v1
        model_class: cheap_fast
        temperature: 0.2
        max_tokens: 256
        cache_segments: [SYSTEM]
        ---

        SYSTEM:

        You are a test assistant.

        USER:

        Input: {x}
        """,
    )
    spec = load_prompt("test.example@v1", search_dirs=[tmp_path])
    assert spec.id == "test.example@v1"
    assert spec.system_template == "You are a test assistant."
    assert spec.user_template == "Input: {x}"
    assert spec.model_class is ModelClass.CHEAP_FAST
    assert spec.temperature == 0.2
    assert spec.max_tokens == 256
    assert spec.cache_segments == ["SYSTEM"]


def test_render_substitutes_variables(tmp_path):
    _write_prompt(
        tmp_path,
        "test.render.md",
        """
        ---
        id: test.render@v1
        ---

        SYSTEM:

        Be helpful.

        USER:

        Normalize: {raw}
        """,
    )
    spec = load_prompt("test.render@v1", search_dirs=[tmp_path])
    system, user = spec.render({"raw": "2010 WI 137"})
    assert system == "Be helpful."
    assert user == "Normalize: 2010 WI 137"


def test_load_without_version_picks_first_match(tmp_path):
    _write_prompt(
        tmp_path,
        "test.unver.md",
        """
        ---
        id: test.unver@v3
        ---

        USER:

        Hello.
        """,
    )
    spec = load_prompt("test.unver", search_dirs=[tmp_path])
    assert spec.id == "test.unver@v3"


def test_missing_prompt_raises(tmp_path):
    with pytest.raises(PromptNotFound):
        load_prompt("does.not.exist@v1", search_dirs=[tmp_path])


def test_missing_frontmatter_raises(tmp_path):
    p = tmp_path / "bad.md"
    p.write_text("USER:\n\nNo frontmatter.\n")
    with pytest.raises(PromptParseError, match="frontmatter"):
        load_prompt("bad@v1", search_dirs=[tmp_path])


def test_missing_user_section_raises(tmp_path):
    _write_prompt(
        tmp_path,
        "test.no_user.md",
        """
        ---
        id: test.no_user@v1
        ---

        SYSTEM:

        Only system.
        """,
    )
    with pytest.raises(PromptParseError, match="USER"):
        load_prompt("test.no_user@v1", search_dirs=[tmp_path])


def test_real_bluebook_prompt_loads():
    """The checked-in schemas/prompts/bluebook.normalize_case.md must
    parse cleanly using the default search dir — proves the v1
    LiteLLMClient can load it without help."""
    spec = load_prompt("bluebook.normalize_case@v1")
    assert spec.system_template.startswith("You are a Bluebook")
    assert "{raw}" in spec.user_template
    assert "{context}" in spec.user_template
    assert "SYSTEM" in spec.cache_segments
