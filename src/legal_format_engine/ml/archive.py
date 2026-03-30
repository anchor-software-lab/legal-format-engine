"""Archive extraction - handles ZIP, RAR, and Adobe Portfolio files."""

from __future__ import annotations
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Optional
import io
import zipfile
import re

SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".doc", ".html", ".htm", ".rtf"}


def extract_archive(
    data: bytes,
    filename: str,
) -> list[tuple[str, bytes]]:
    """Extract supported documents from an archive.

    Returns list of (filename, file_bytes) tuples.
    Handles: ZIP, RAR, Adobe Portfolio (PDF with attachments).
    """
    ext = Path(filename).suffix.lower()

    if ext == ".zip":
        return _extract_zip(data)
    elif ext == ".rar":
        return _extract_rar(data)
    elif ext == ".pdf":
        return _extract_pdf_portfolio(data)
    else:
        # Try as ZIP first (most common)
        try:
            return _extract_zip(data)
        except (zipfile.BadZipFile, Exception):
            return []


def _extract_zip(data: bytes) -> list[tuple[str, bytes]]:
    """Extract from a ZIP archive."""
    results = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            safe_name = _safe_filename(info.filename)
            ext = Path(safe_name).suffix.lower()
            if ext in SUPPORTED_EXTENSIONS:
                results.append((safe_name, zf.read(info.filename)))
    return _deduplicate(results)


def _extract_rar(data: bytes) -> list[tuple[str, bytes]]:
    """Extract from a RAR archive."""
    try:
        import rarfile
        results = []
        with rarfile.RarFile(io.BytesIO(data)) as rf:
            for info in rf.infolist():
                if info.is_dir():
                    continue
                safe_name = _safe_filename(info.filename)
                ext = Path(safe_name).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    results.append((safe_name, rf.read(info.filename)))
        return _deduplicate(results)
    except ImportError:
        return []


def _extract_pdf_portfolio(data: bytes) -> list[tuple[str, bytes]]:
    """Extract embedded files from an Adobe Portfolio (PDF with attachments)."""
    try:
        import fitz
        results = []
        doc = fitz.open(stream=data, filetype="pdf")

        # Check for embedded files
        if doc.embfile_count() > 0:
            for i in range(doc.embfile_count()):
                info = doc.embfile_info(i)
                name = info.get("name", f"embedded_{i}")
                safe_name = _safe_filename(name)
                ext = Path(safe_name).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    file_data = doc.embfile_get(i)
                    results.append((safe_name, file_data))

        doc.close()
        return _deduplicate(results)
    except Exception:
        return []


def _safe_filename(path_str: str) -> str:
    """Extract safe filename from a path, handling both Unix and Windows paths."""
    # Handle Windows backslash paths
    if "\\" in path_str:
        name = PureWindowsPath(path_str).name
    else:
        name = PurePosixPath(path_str).name

    # Remove path traversal
    name = name.replace("..", "").strip("/\\")
    return name or "unknown"


def _deduplicate(files: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    """Deduplicate filenames by adding _1, _2, etc."""
    seen: dict[str, int] = {}
    results = []
    for name, data in files:
        if name in seen:
            seen[name] += 1
            stem = Path(name).stem
            ext = Path(name).suffix
            name = f"{stem}_{seen[name]}{ext}"
        else:
            seen[name] = 0
        results.append((name, data))
    return results
