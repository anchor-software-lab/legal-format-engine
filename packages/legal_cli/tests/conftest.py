"""Shared fixtures for legal_cli tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from legal_docx.testing import make_sample_brief


@pytest.fixture
def sample_brief_docx(tmp_path: Path) -> Path:
    return make_sample_brief(tmp_path / "sample_brief.docx")
