"""Tests for ml/archive.py."""

from __future__ import annotations

import io
import zipfile

import pytest

from legal_format_engine.ml.archive import (
    SUPPORTED_EXTENSIONS,
    _deduplicate,
    _safe_filename,
    extract_archive,
)


class TestExtractArchive:
    def test_extract_zip_with_docx(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("brief.docx", b"fake docx content")
            zf.writestr("notes.txt", b"unsupported in SUPPORTED_EXTENSIONS")
        data = buf.getvalue()
        result = extract_archive(data, "bundle.zip")
        names = [name for name, _ in result]
        assert "brief.docx" in names
        # .txt is not in SUPPORTED_EXTENSIONS
        assert "notes.txt" not in names

    def test_extract_zip_with_pdf(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("document.pdf", b"fake pdf")
        result = extract_archive(buf.getvalue(), "archive.zip")
        assert len(result) == 1
        assert result[0][0] == "document.pdf"

    def test_extract_zip_skips_directories(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("subdir/brief.docx", b"content")
        result = extract_archive(buf.getvalue(), "test.zip")
        names = [name for name, _ in result]
        assert "brief.docx" in names  # Directory stripped

    def test_extract_zip_multiple_files(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("a.docx", b"content1")
            zf.writestr("b.pdf", b"content2")
            zf.writestr("c.html", b"content3")
            zf.writestr("d.jpg", b"image")  # unsupported
        result = extract_archive(buf.getvalue(), "test.zip")
        assert len(result) == 3

    def test_extract_empty_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            pass
        result = extract_archive(buf.getvalue(), "empty.zip")
        assert result == []

    def test_extract_invalid_data(self):
        result = extract_archive(b"not a zip file", "test.xyz")
        assert result == []

    def test_extract_unknown_extension_tries_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("brief.docx", b"content")
        result = extract_archive(buf.getvalue(), "archive.bin")
        assert len(result) == 1

    def test_rar_without_library(self):
        # RAR extraction should return empty if rarfile not installed
        result = extract_archive(b"not rar data", "test.rar")
        assert isinstance(result, list)


class TestSafeFilename:
    def test_unix_path(self):
        assert _safe_filename("path/to/file.docx") == "file.docx"

    def test_windows_path(self):
        assert _safe_filename("C:\\Users\\docs\\file.docx") == "file.docx"

    def test_plain_filename(self):
        assert _safe_filename("document.pdf") == "document.pdf"

    def test_path_traversal(self):
        result = _safe_filename("../../etc/passwd")
        assert ".." not in result

    def test_empty_result(self):
        result = _safe_filename("..")
        assert result == "unknown"

    def test_nested_directories(self):
        assert _safe_filename("a/b/c/d.docx") == "d.docx"


class TestDeduplicate:
    def test_no_duplicates(self):
        files = [("a.docx", b"1"), ("b.docx", b"2")]
        result = _deduplicate(files)
        assert len(result) == 2

    def test_deduplicates_names(self):
        files = [("a.docx", b"1"), ("a.docx", b"2")]
        result = _deduplicate(files)
        assert len(result) == 2
        names = [n for n, _ in result]
        assert "a.docx" in names
        assert "a_1.docx" in names

    def test_triple_duplicate(self):
        files = [("x.pdf", b"1"), ("x.pdf", b"2"), ("x.pdf", b"3")]
        result = _deduplicate(files)
        assert len(result) == 3
        names = [n for n, _ in result]
        assert len(set(names)) == 3

    def test_empty(self):
        assert _deduplicate([]) == []


class TestSupportedExtensions:
    def test_docx_supported(self):
        assert ".docx" in SUPPORTED_EXTENSIONS

    def test_pdf_supported(self):
        assert ".pdf" in SUPPORTED_EXTENSIONS

    def test_doc_supported(self):
        assert ".doc" in SUPPORTED_EXTENSIONS

    def test_html_supported(self):
        assert ".html" in SUPPORTED_EXTENSIONS

    def test_rtf_supported(self):
        assert ".rtf" in SUPPORTED_EXTENSIONS

    def test_jpg_not_supported(self):
        assert ".jpg" not in SUPPORTED_EXTENSIONS
