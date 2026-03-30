"""Archive extraction: unpack collections of documents from ZIP, RAR, and Adobe Portfolio.

Attorneys may upload a collection of briefs as:
- ZIP file containing DOCX/PDF files
- RAR archive containing DOCX/PDF files
- Adobe Portfolio (a PDF containing embedded file attachments)
- A plain directory of files (for programmatic use)

This module extracts individual documents from these containers into a
temporary directory, filtering to only supported document types.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path


# File extensions the ML pipeline can process
SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".doc", ".html", ".htm", ".rtf"}

# Archive extensions this module can unpack
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".pdf"}


def is_archive(path: Path) -> bool:
    """Check if a file is a supported archive/collection format.

    For PDF, we check if it contains embedded file attachments (Adobe Portfolio).
    For ZIP/RAR, we check by extension.
    """
    ext = path.suffix.lower()
    if ext in (".zip", ".rar"):
        return True
    if ext == ".pdf":
        return _is_pdf_portfolio(path)
    return False


def extract_archive(path: Path, output_dir: Path | None = None) -> list[Path]:
    """Extract documents from an archive into a directory.

    Returns a list of paths to extracted document files (only supported types).
    Creates a temp directory if output_dir is not specified.

    Args:
        path: Path to the archive file (ZIP, RAR, or Adobe Portfolio PDF).
        output_dir: Directory to extract into. Created if needed.

    Returns:
        List of Paths to extracted document files.

    Raises:
        ValueError: If the archive format is unsupported or corrupt.
    """
    ext = path.suffix.lower()

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="legal_archive_"))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    if ext == ".zip":
        return _extract_zip(path, output_dir)
    elif ext == ".rar":
        return _extract_rar(path, output_dir)
    elif ext == ".pdf":
        return _extract_pdf_portfolio(path, output_dir)
    else:
        raise ValueError(f"Unsupported archive format: {ext}")


def _extract_zip(path: Path, output_dir: Path) -> list[Path]:
    """Extract documents from a ZIP archive."""
    try:
        with zipfile.ZipFile(str(path), "r") as zf:
            # Security: check for path traversal attacks
            for info in zf.infolist():
                if info.filename.startswith("/") or ".." in info.filename:
                    continue  # skip suspicious paths
                if info.is_dir():
                    continue

                file_ext = Path(info.filename).suffix.lower()
                if file_ext not in SUPPORTED_EXTENSIONS:
                    continue

                # Extract to flat directory with safe filename
                safe_name = _safe_filename(info.filename)
                target = output_dir / safe_name

                # Handle duplicates
                target = _unique_path(target)

                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    except zipfile.BadZipFile:
        raise ValueError("Corrupt or invalid ZIP file")

    return _collect_supported_files(output_dir)


def _extract_rar(path: Path, output_dir: Path) -> list[Path]:
    """Extract documents from a RAR archive.

    Tries the `rarfile` Python package first, then falls back to
    `unrar` command-line tool.
    """
    # Try rarfile package
    try:
        import rarfile
        with rarfile.RarFile(str(path), "r") as rf:
            for info in rf.infolist():
                if info.is_dir():
                    continue
                file_ext = Path(info.filename).suffix.lower()
                if file_ext not in SUPPORTED_EXTENSIONS:
                    continue

                safe_name = _safe_filename(info.filename)
                target = output_dir / safe_name
                target = _unique_path(target)

                with rf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

        return _collect_supported_files(output_dir)
    except ImportError:
        pass
    except Exception as exc:
        raise ValueError(f"Failed to extract RAR with rarfile: {exc}")

    # Fallback: try unrar command line
    import subprocess
    try:
        subprocess.run(
            ["unrar", "e", "-o+", str(path), str(output_dir) + "/"],
            capture_output=True, timeout=60, check=True,
        )
        # Remove non-supported files
        for f in output_dir.iterdir():
            if f.suffix.lower() not in SUPPORTED_EXTENSIONS:
                f.unlink()
        return _collect_supported_files(output_dir)
    except FileNotFoundError:
        raise ValueError(
            "RAR extraction requires either the 'rarfile' Python package "
            "(pip install rarfile) or the 'unrar' command-line tool"
        )
    except subprocess.SubprocessError as exc:
        raise ValueError(f"Failed to extract RAR: {exc}")


def _is_pdf_portfolio(path: Path) -> bool:
    """Check if a PDF contains embedded file attachments (Adobe Portfolio)."""
    try:
        import fitz
        doc = fitz.open(str(path))
        try:
            # Check for embedded files in the PDF catalog
            count = doc.embfile_count()
            return count > 0
        finally:
            doc.close()
    except Exception:
        return False


def _extract_pdf_portfolio(path: Path, output_dir: Path) -> list[Path]:
    """Extract embedded files from an Adobe Portfolio PDF.

    Adobe Portfolios are PDFs that contain other files as embedded attachments.
    These are commonly used by attorneys to bundle multiple documents.
    """
    try:
        import fitz
    except ImportError:
        raise ValueError("PDF portfolio extraction requires PyMuPDF (pip install pymupdf)")

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        raise ValueError(f"Could not open PDF: {exc}")

    try:
        count = doc.embfile_count()
        if count == 0:
            raise ValueError(
                "This PDF does not contain embedded files. "
                "It may be a regular PDF — upload it directly instead."
            )

        for i in range(count):
            name = doc.embfile_info(i).get("name", f"file_{i}")
            file_ext = Path(name).suffix.lower()

            if file_ext not in SUPPORTED_EXTENSIONS:
                continue

            data = doc.embfile_get(i)
            safe_name = _safe_filename(name)
            target = output_dir / safe_name
            target = _unique_path(target)
            target.write_bytes(data)

    finally:
        doc.close()

    return _collect_supported_files(output_dir)


def _safe_filename(original: str) -> str:
    """Create a safe filename from a potentially nested archive path.

    "folder/subfolder/brief.docx" -> "brief.docx"
    "folder\\subfolder\\brief.docx" -> "brief.docx"
    "../../../etc/passwd" -> "passwd"
    """
    # Normalize Windows-style backslashes to forward slashes first
    normalized = original.replace("\\", "/")
    # Take just the final component
    name = normalized.rsplit("/", 1)[-1]
    # Ensure it's not empty
    if not name or name.startswith("."):
        name = f"extracted_{name}"
    return name


def _unique_path(path: Path) -> Path:
    """If path already exists, append a counter to make it unique."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def _collect_supported_files(directory: Path) -> list[Path]:
    """Collect all supported document files from a directory."""
    files = []
    for f in sorted(directory.iterdir()):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(f)
    return files


def cleanup_extraction(directory: Path) -> None:
    """Clean up a temporary extraction directory."""
    if directory.exists() and directory.is_dir():
        shutil.rmtree(directory, ignore_errors=True)
