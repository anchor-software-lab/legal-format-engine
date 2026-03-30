"""Tests for CLI interface."""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from legal_format_engine.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


class TestCLI:
    def test_format_docx(self):
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            result = runner.invoke(main, [
                "format",
                str(FIXTURES / "sample_brief.txt"),
                "-o", f.name,
                "-m", str(FIXTURES / "metadata.json"),
            ])
        assert result.exit_code == 0
        assert "DOCX written to" in result.output

    def test_format_markdown(self):
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            result = runner.invoke(main, [
                "format",
                str(FIXTURES / "sample_brief.txt"),
                "-o", f.name,
                "-m", str(FIXTURES / "metadata.json"),
                "--format", "markdown",
            ])
        assert result.exit_code == 0
        assert "Markdown written to" in result.output
        content = Path(f.name).read_text()
        assert "Argument" in content

    def test_caption_command(self):
        runner = CliRunner()
        result = runner.invoke(main, [
            "caption",
            "-m", str(FIXTURES / "metadata.json"),
        ])
        assert result.exit_code == 0
        assert "COURT OF APPEALS" in result.output

    def test_validate_command(self):
        runner = CliRunner()
        result = runner.invoke(main, [
            "validate",
            "-m", str(FIXTURES / "metadata.json"),
            "-i", str(FIXTURES / "sample_brief.txt"),
        ])
        # May have warnings but should not crash
        assert result.exit_code in (0, 1)
