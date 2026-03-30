"""Tests for the archive module."""

import tempfile
import zipfile
from pathlib import Path

import pytest
from anchor_ml_engine.archive import (
    SUPPORTED_EXTENSIONS,
    _safe_filename,
    _unique_path,
    _collect_supported_files,
    extract_archive,
    cleanup_extraction,
)


class TestSafeFilename:
    def test_nested_path(self):
        assert _safe_filename("folder/subfolder/brief.docx") == "brief.docx"

    def test_windows_path(self):
        assert _safe_filename("folder\\subfolder\\brief.docx") == "brief.docx"

    def test_path_traversal(self):
        result = _safe_filename("../../../etc/passwd")
        assert ".." not in result

    def test_hidden_file(self):
        result = _safe_filename(".hidden")
        assert result.startswith("extracted_")


class TestUniquePath:
    def test_no_conflict(self, tmp_path):
        p = tmp_path / "test.docx"
        assert _unique_path(p) == p

    def test_with_conflict(self, tmp_path):
        p = tmp_path / "test.docx"
        p.write_text("existing")
        result = _unique_path(p)
        assert result.name == "test_1.docx"

    def test_multiple_conflicts(self, tmp_path):
        for i in range(3):
            name = "test.docx" if i == 0 else f"test_{i}.docx"
            (tmp_path / name).write_text("existing")
        result = _unique_path(tmp_path / "test.docx")
        assert result.name == "test_3.docx"


class TestCollectSupportedFiles:
    def test_collects_docx(self, tmp_path):
        (tmp_path / "test.docx").write_text("docx")
        (tmp_path / "test.txt").write_text("txt")
        files = _collect_supported_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "test.docx"

    def test_collects_multiple_types(self, tmp_path):
        for ext in (".docx", ".pdf", ".html"):
            (tmp_path / f"test{ext}").write_text("content")
        (tmp_path / "image.png").write_text("not supported")
        files = _collect_supported_files(tmp_path)
        assert len(files) == 3


class TestExtractZip:
    def test_extract_zip(self, tmp_path):
        # Create a ZIP with a DOCX file
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("brief.docx", "fake docx content")
            zf.writestr("readme.txt", "not supported")

        output_dir = tmp_path / "output"
        files = extract_archive(zip_path, output_dir)
        assert len(files) == 1
        assert files[0].name == "brief.docx"

    def test_extract_zip_nested(self, tmp_path):
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("folder/brief1.docx", "content1")
            zf.writestr("folder/subfolder/brief2.pdf", "content2")
            zf.writestr("folder/image.png", "not supported")

        output_dir = tmp_path / "output"
        files = extract_archive(zip_path, output_dir)
        assert len(files) == 2

    def test_corrupt_zip_raises(self, tmp_path):
        bad_zip = tmp_path / "bad.zip"
        bad_zip.write_text("not a zip file")
        with pytest.raises(ValueError, match="Corrupt"):
            extract_archive(bad_zip)


class TestCleanupExtraction:
    def test_cleanup(self, tmp_path):
        test_dir = tmp_path / "to_clean"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("data")
        cleanup_extraction(test_dir)
        assert not test_dir.exists()

    def test_cleanup_nonexistent(self, tmp_path):
        # Should not raise
        cleanup_extraction(tmp_path / "nonexistent")


class TestSupportedExtensions:
    def test_common_extensions_supported(self):
        assert ".docx" in SUPPORTED_EXTENSIONS
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".html" in SUPPORTED_EXTENSIONS
        assert ".rtf" in SUPPORTED_EXTENSIONS
