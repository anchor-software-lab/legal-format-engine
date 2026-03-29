"""Tests for archive extraction: ZIP, RAR, and Adobe Portfolio."""

import tempfile
import zipfile
from pathlib import Path

import pytest

from legal_format_engine.ml.archive import (
    SUPPORTED_EXTENSIONS,
    _collect_supported_files,
    _safe_filename,
    _unique_path,
    extract_archive,
    is_archive,
)


class TestSafeFilename:
    def test_simple_filename(self):
        assert _safe_filename("brief.docx") == "brief.docx"

    def test_nested_path(self):
        assert _safe_filename("folder/subfolder/brief.docx") == "brief.docx"

    def test_windows_path(self):
        assert _safe_filename("folder\\subfolder\\brief.docx") == "brief.docx"

    def test_path_traversal(self):
        name = _safe_filename("../../../etc/passwd")
        assert ".." not in name

    def test_dotfile(self):
        name = _safe_filename(".hidden")
        assert name.startswith("extracted_")

    def test_empty_after_strip(self):
        name = _safe_filename("")
        assert len(name) > 0


class TestUniquePath:
    def test_no_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.docx"
            assert _unique_path(path) == path

    def test_conflict_resolved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.docx"
            path.write_bytes(b"existing")
            result = _unique_path(path)
            assert result.name == "test_1.docx"
            assert result != path

    def test_multiple_conflicts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.docx"
            path.write_bytes(b"existing")
            (Path(tmpdir) / "test_1.docx").write_bytes(b"existing")
            result = _unique_path(path)
            assert result.name == "test_2.docx"


class TestCollectSupportedFiles:
    def test_collects_supported_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / "brief.docx").write_bytes(b"docx")
            (d / "motion.pdf").write_bytes(b"pdf")
            (d / "readme.txt").write_bytes(b"txt")
            (d / "photo.jpg").write_bytes(b"jpg")

            files = _collect_supported_files(d)
            names = {f.name for f in files}
            assert "brief.docx" in names
            assert "motion.pdf" in names
            assert "readme.txt" not in names
            assert "photo.jpg" not in names

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = _collect_supported_files(Path(tmpdir))
            assert files == []


class TestIsArchive:
    def test_zip_is_archive(self):
        with tempfile.NamedTemporaryFile(suffix=".zip") as f:
            assert is_archive(Path(f.name))

    def test_rar_is_archive(self):
        with tempfile.NamedTemporaryFile(suffix=".rar") as f:
            assert is_archive(Path(f.name))

    def test_docx_not_archive(self):
        with tempfile.NamedTemporaryFile(suffix=".docx") as f:
            assert not is_archive(Path(f.name))

    def test_regular_pdf_not_archive(self):
        # A regular PDF (not a portfolio) should not be treated as archive
        import fitz
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), "Test document")
            doc.save(f.name)
            doc.close()
            assert not is_archive(Path(f.name))
            Path(f.name).unlink()


class TestExtractZip:
    def _make_zip_with_docs(self, tmpdir: str, files: dict[str, bytes]) -> Path:
        """Create a ZIP with the given filename->content mapping."""
        zip_path = Path(tmpdir) / "test.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        return zip_path

    def test_extract_basic_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = self._make_zip_with_docs(tmpdir, {
                "brief1.docx": b"docx content 1",
                "brief2.pdf": b"pdf content 2",
            })
            output_dir = Path(tmpdir) / "output"
            files = extract_archive(zip_path, output_dir)

            assert len(files) == 2
            names = {f.name for f in files}
            assert "brief1.docx" in names
            assert "brief2.pdf" in names

    def test_filters_unsupported_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = self._make_zip_with_docs(tmpdir, {
                "brief.docx": b"docx",
                "photo.jpg": b"jpg",
                "readme.txt": b"txt",
                "motion.pdf": b"pdf",
            })
            output_dir = Path(tmpdir) / "output"
            files = extract_archive(zip_path, output_dir)

            assert len(files) == 2
            names = {f.name for f in files}
            assert "brief.docx" in names
            assert "motion.pdf" in names
            assert "photo.jpg" not in names

    def test_handles_nested_folders_in_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = self._make_zip_with_docs(tmpdir, {
                "folder1/brief.docx": b"docx",
                "folder2/subfolder/motion.pdf": b"pdf",
            })
            output_dir = Path(tmpdir) / "output"
            files = extract_archive(zip_path, output_dir)

            # Should extract with flat filenames
            assert len(files) == 2

    def test_handles_duplicate_names(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = self._make_zip_with_docs(tmpdir, {
                "folder1/brief.docx": b"docx 1",
                "folder2/brief.docx": b"docx 2",
            })
            output_dir = Path(tmpdir) / "output"
            files = extract_archive(zip_path, output_dir)

            assert len(files) == 2

    def test_empty_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "empty.zip"
            with zipfile.ZipFile(str(zip_path), "w"):
                pass
            output_dir = Path(tmpdir) / "output"
            files = extract_archive(zip_path, output_dir)
            assert files == []

    def test_zip_with_no_supported_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = self._make_zip_with_docs(tmpdir, {
                "photo.jpg": b"jpg",
                "readme.txt": b"txt",
            })
            output_dir = Path(tmpdir) / "output"
            files = extract_archive(zip_path, output_dir)
            assert files == []

    def test_corrupt_zip_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_zip = Path(tmpdir) / "bad.zip"
            bad_zip.write_bytes(b"not a zip file")
            output_dir = Path(tmpdir) / "output"
            with pytest.raises(ValueError, match="Corrupt|invalid"):
                extract_archive(bad_zip, output_dir)

    def test_path_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "evil.zip"
            with zipfile.ZipFile(str(zip_path), "w") as zf:
                zf.writestr("../../evil.docx", b"evil")
                zf.writestr("safe.docx", b"safe")
            output_dir = Path(tmpdir) / "output"
            files = extract_archive(zip_path, output_dir)
            # Should only get the safe file
            names = {f.name for f in files}
            assert "safe.docx" in names

    def test_supported_extensions_complete(self):
        """Verify all expected extensions are supported."""
        assert ".docx" in SUPPORTED_EXTENSIONS
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".doc" in SUPPORTED_EXTENSIONS
        assert ".html" in SUPPORTED_EXTENSIONS
        assert ".htm" in SUPPORTED_EXTENSIONS
        assert ".rtf" in SUPPORTED_EXTENSIONS


class TestExtractPdfPortfolio:
    def test_pdf_portfolio_extraction(self):
        """Test extracting embedded files from a PDF portfolio."""
        import fitz

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a PDF with embedded files
            pdf_path = Path(tmpdir) / "portfolio.pdf"
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), "Portfolio cover page")

            # Embed a fake DOCX (just bytes for testing extraction)
            doc.embfile_add("brief.docx", b"fake docx content",
                           filename="brief.docx",
                           desc="Test brief")
            doc.embfile_add("motion.pdf", b"fake pdf content",
                           filename="motion.pdf",
                           desc="Test motion")
            # Embed unsupported type
            doc.embfile_add("photo.jpg", b"fake image",
                           filename="photo.jpg",
                           desc="Test image")

            doc.save(str(pdf_path))
            doc.close()

            # Extract
            output_dir = Path(tmpdir) / "output"
            files = extract_archive(pdf_path, output_dir)

            names = {f.name for f in files}
            assert "brief.docx" in names
            assert "motion.pdf" in names
            assert "photo.jpg" not in names

    def test_regular_pdf_raises(self):
        """A regular PDF (no attachments) should raise, not be treated as archive."""
        import fitz

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "regular.pdf"
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), "Just a regular PDF")
            doc.save(str(pdf_path))
            doc.close()

            output_dir = Path(tmpdir) / "output"
            with pytest.raises(ValueError, match="does not contain embedded"):
                extract_archive(pdf_path, output_dir)
