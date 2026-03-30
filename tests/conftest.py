"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from legal_format_engine.models.metadata import DocumentMetadata
from legal_format_engine.rules.loader import load_ruleset
from legal_format_engine.rules.schema import Ruleset

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_brief_text() -> str:
    return (FIXTURES_DIR / "sample_brief.txt").read_text(encoding="utf-8")


@pytest.fixture
def sample_metadata() -> DocumentMetadata:
    data = json.loads((FIXTURES_DIR / "metadata.json").read_text(encoding="utf-8"))
    return DocumentMetadata.model_validate(data)


@pytest.fixture
def wi_appellate_ruleset() -> Ruleset:
    return load_ruleset("wisconsin", "appellate", "brief")
