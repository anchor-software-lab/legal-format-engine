"""End-to-end tests for the `lqg` CLI via Typer's CliRunner."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legal_cli import app


@pytest.fixture
def runner() -> CliRunner:
    # mix_stderr=False puts stderr in result.stderr separately so we can
    # assert against stdout without Typer's exit messages getting in the way.
    return CliRunner()


def test_check_runs_with_default_settings(runner, sample_brief_docx):
    result = runner.invoke(app, ["check", str(sample_brief_docx)])
    # Default config has no font-size rule, so no ERROR findings → exit 0.
    assert result.exit_code == 0
    assert "Anchor Quality Gate" in result.stdout
    assert sample_brief_docx.name in result.stdout


def test_check_exits_nonzero_when_errors_present(runner, sample_brief_docx, tmp_path):
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text(
        textwrap.dedent(
            """
            page_format:
              font_size_pt: 13.0
            """
        )
    )
    result = runner.invoke(
        app, ["check", str(sample_brief_docx), "--rules", str(rules_path)]
    )
    # Body paragraph is 12pt vs the 13pt rule → ERROR → exit 1.
    assert result.exit_code == 1
    assert "FORMAT.FONT.SIZE" in result.stdout
    assert "ERROR" in result.stdout


def test_check_json_output(runner, sample_brief_docx, tmp_path):
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text("page_format:\n  font_size_pt: 13.0\n")
    result = runner.invoke(
        app,
        [
            "check",
            str(sample_brief_docx),
            "--rules",
            str(rules_path),
            "--output",
            "json",
        ],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["document_id"]
    assert any(f["rule_id"] == "FORMAT.FONT.SIZE" for f in payload["findings"])
    assert payload["score"] < 100


def test_check_respects_policy_severity_override(runner, sample_brief_docx, tmp_path):
    """Demote BB.PINPOINT to info via a policy and verify exit code reflects it."""
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text("page_format:\n  font_size_pt: 13.0\n")

    # Restrict checkers to bluebook.pinpoint only, no formatting checker.
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        textwrap.dedent(
            """
            name: pinpoint_only
            enabled:
              - bluebook.pinpoint
            severity_overrides:
              bluebook.pinpoint: info
            """
        )
    )
    result = runner.invoke(
        app,
        [
            "check",
            str(sample_brief_docx),
            "--rules",
            str(rules_path),
            "--policy",
            str(policy_path),
        ],
    )
    # With formatting checker disabled and pinpoint demoted to info,
    # there should be no errors.
    assert result.exit_code == 0
    assert "INFO" in result.stdout
    assert "FORMAT.FONT.SIZE" not in result.stdout


def test_cites_command_prints_table(runner, sample_brief_docx):
    result = runner.invoke(app, ["cites", str(sample_brief_docx)])
    assert result.exit_code == 0
    # The body paragraph has at least Tews and Brown.
    assert "Tews" in result.stdout
    assert "Brown" in result.stdout


def test_cites_command_json(runner, sample_brief_docx):
    result = runner.invoke(app, ["cites", str(sample_brief_docx), "--output", "json"])
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    case_names = {r["case_name"] for r in rows if r["case_name"]}
    assert any("Tews" in name for name in case_names)
    assert any("Brown" in name for name in case_names)


def test_check_rejects_missing_file(runner, tmp_path):
    missing = tmp_path / "nope.docx"
    result = runner.invoke(app, ["check", str(missing)])
    assert result.exit_code != 0


def test_fix_applies_safe_suggestions(runner, sample_brief_docx, tmp_path):
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text("page_format:\n  font_size_pt: 13.0\n")
    out_path = tmp_path / "fixed.docx"

    result = runner.invoke(
        app,
        [
            "fix",
            str(sample_brief_docx),
            "--rules",
            str(rules_path),
            "--out",
            str(out_path),
        ],
    )
    assert result.exit_code == 0
    assert out_path.exists()
    assert "Applied" in result.stdout
    assert "FORMAT.FONT.SIZE" in result.stdout

    # Re-check the fixed docx: no more FORMAT.FONT.SIZE errors.
    recheck = runner.invoke(
        app, ["check", str(out_path), "--rules", str(rules_path)]
    )
    assert "FORMAT.FONT.SIZE" not in recheck.stdout or "ERROR" not in recheck.stdout


def test_fix_with_no_safe_suggestions_exits_zero(runner, sample_brief_docx, tmp_path):
    # No rules → no rule-sourced ERROR findings → all suggestions are
    # ML/default-sourced and not auto_apply_safe → nothing to fix.
    result = runner.invoke(app, ["fix", str(sample_brief_docx)])
    assert result.exit_code == 0
    assert "No auto-safe suggestions" in result.stdout


def test_fix_rejects_conflicting_in_place_and_out(runner, sample_brief_docx, tmp_path):
    result = runner.invoke(
        app,
        [
            "fix",
            str(sample_brief_docx),
            "--in-place",
            "--out",
            str(tmp_path / "x.docx"),
        ],
    )
    assert result.exit_code == 2
    assert "mutually exclusive" in result.stdout


def test_fix_in_place_overwrites_original(runner, tmp_path, sample_brief_docx):
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text("page_format:\n  font_size_pt: 13.0\n")

    result = runner.invoke(
        app,
        [
            "fix",
            str(sample_brief_docx),
            "--rules",
            str(rules_path),
            "--in-place",
        ],
    )
    assert result.exit_code == 0
    # The original docx itself should now pass the rule.
    recheck = runner.invoke(
        app, ["check", str(sample_brief_docx), "--rules", str(rules_path)]
    )
    # No FORMAT.FONT.SIZE ERROR after in-place fix.
    assert not (
        "FORMAT.FONT.SIZE" in recheck.stdout and "ERROR" in recheck.stdout
    )


def test_fix_policy_auto_fix_allow_globs(runner, sample_brief_docx, tmp_path):
    """A policy that doesn't allow FORMAT.* in auto_fix should skip those fixes."""
    rules_path = tmp_path / "rules.yaml"
    rules_path.write_text("page_format:\n  font_size_pt: 13.0\n")

    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        "name: pinpoint_only_fixes\n"
        "auto_fix:\n"
        "  allow:\n"
        "    - BB.*\n"
    )
    out_path = tmp_path / "fixed.docx"
    result = runner.invoke(
        app,
        [
            "fix",
            str(sample_brief_docx),
            "--rules",
            str(rules_path),
            "--policy",
            str(policy_path),
            "--out",
            str(out_path),
        ],
    )
    # FORMAT.* findings filtered out; BB.* findings don't have
    # auto_apply_safe suggestions in v0 → nothing applied.
    assert result.exit_code == 0
    assert "No auto-safe suggestions" in result.stdout
