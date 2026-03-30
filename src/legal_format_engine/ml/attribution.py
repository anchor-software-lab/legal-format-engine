"""Auto-detection of author/firm from document content."""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Attribution:
    """Detected author/firm attribution."""
    author: Optional[str] = None
    firm: Optional[str] = None
    bar_number: Optional[str] = None
    source: str = ""  # Where the attribution was detected
    confidence: float = 0.0


# Firm suffixes for detection
_FIRM_SUFFIXES = re.compile(
    r"(?:LLP|LLC|P\.?C\.?|P\.?A\.?|PLLC|S\.?C\.?|PLC|"
    r"Law\s+(?:Firm|Office|Group|Offices)|"
    r"(?:&|and)\s+Associates|"
    r"Attorneys?\s+at\s+Law)\b",
    re.IGNORECASE,
)

# Signature block patterns
_SIGNATURE_PATTERNS = [
    re.compile(r"Respectfully\s+submitted", re.IGNORECASE),
    re.compile(r"Electronically\s+(?:signed|filed)\s+by\s+(.+)", re.IGNORECASE),
    re.compile(r"/s/\s*(.+)", re.IGNORECASE),
]

# Bar number pattern
_BAR_PATTERN = re.compile(r"(?:Bar|SBN|Attorney)\s*(?:No\.?|Number|#)\s*[:.]?\s*(\d+)", re.IGNORECASE)


def detect_attribution(text: str) -> Attribution:
    """Detect author and firm from document text.

    Searches (in order of reliability):
    1. Signature block
    2. Certificate of service
    3. Letterhead / first page
    """
    result = Attribution()

    # Try signature block
    sig = _detect_from_signature(text)
    if sig.author or sig.firm:
        return sig

    # Try certificate of service
    cert = _detect_from_certification(text)
    if cert.author or cert.firm:
        return cert

    # Try letterhead / first lines
    header = _detect_from_header(text)
    if header.firm:
        return header

    return result


def _detect_from_signature(text: str) -> Attribution:
    """Extract author/firm from signature block."""
    result = Attribution(source="signature_block")

    for pattern in _SIGNATURE_PATTERNS:
        m = pattern.search(text)
        if m:
            # Look at lines near the match
            pos = m.start()
            context = text[pos:min(pos + 500, len(text))]
            lines = [l.strip() for l in context.split("\n") if l.strip()]

            for i, line in enumerate(lines):
                # Electronic signature line
                esig = re.match(r"(?:Electronically\s+signed\s+by|/s/)\s*(.+)", line, re.IGNORECASE)
                if esig:
                    result.author = esig.group(1).strip().rstrip(",")
                    result.confidence = 0.9
                    continue

                # Bar number
                bar = _BAR_PATTERN.search(line)
                if bar:
                    result.bar_number = bar.group(1)
                    continue

                # Firm (line with firm suffix)
                if _FIRM_SUFFIXES.search(line) and not result.firm:
                    result.firm = line.strip().rstrip(",")
                    result.confidence = max(result.confidence, 0.8)

            break

    return result


def _detect_from_certification(text: str) -> Attribution:
    """Extract from certificate of service section."""
    result = Attribution(source="certification")

    cert_match = re.search(r"(?:CERTIFICATE|CERTIFICATION)\s+OF\s+SERVICE", text, re.IGNORECASE)
    if not cert_match:
        return result

    context = text[cert_match.start():min(cert_match.start() + 1000, len(text))]
    lines = [l.strip() for l in context.split("\n") if l.strip()]

    for line in lines:
        bar = _BAR_PATTERN.search(line)
        if bar:
            result.bar_number = bar.group(1)

        if _FIRM_SUFFIXES.search(line) and not result.firm:
            result.firm = line.strip()
            result.confidence = 0.6

    return result


def _detect_from_header(text: str) -> Attribution:
    """Extract firm from first few lines (letterhead)."""
    result = Attribution(source="header")

    lines = text.split("\n")[:15]
    for line in lines:
        line = line.strip()
        if _FIRM_SUFFIXES.search(line):
            result.firm = line
            result.confidence = 0.5
            break

    return result


def detect_from_docx_metadata(metadata: dict) -> Attribution:
    """Extract attribution from DOCX file metadata."""
    result = Attribution(source="docx_metadata", confidence=0.7)

    if "author" in metadata:
        result.author = metadata["author"]
    if "company" in metadata:
        result.firm = metadata["company"]

    return result
