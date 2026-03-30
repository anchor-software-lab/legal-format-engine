"""Auto-detect authorship attribution from documents.

Examines multiple sources to identify the author and organization that
authored a document:

1. Document metadata (DOCX core properties: author, company)
2. Signature block text patterns ("Respectfully submitted," blocks)
3. Letterhead / first page content (organization name, address, phone)
4. Certificate of service (filing author identification)
5. Caption page (author identification lines)

When multiple authors are listed, the first one found is treated as the
primary author.
"""

from __future__ import annotations

import re
from pathlib import Path

from anchor_ml_engine.models import DetectedAttribution


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Bar number patterns (state-specific and generic)
_BAR_NUMBER_RE = re.compile(
    r"(?:(?:State\s+)?Bar\s+No\.?\s*:?\s*|"
    r"WSBA\s+No\.?\s*:?\s*|"
    r"SBN\s*:?\s*|"
    r"Bar\s+#\s*|"
    r"Bar\s+I\.?D\.?\s*:?\s*)"
    r"(\d[\d\-]+\d)",
    re.IGNORECASE,
)

# Organization name suffixes that identify a legal entity
_ORG_SUFFIX_RE = re.compile(
    r"\b(LLP|LLC|P\.?C\.?|PLLC|P\.?A\.?|S\.?C\.?|Ltd\.?|Inc\.?|Corp\.?)\b",
    re.IGNORECASE,
)

# Broader organization name patterns (for letterhead detection)
_ORG_NAME_PATTERNS = re.compile(
    r"(?:Law\s+(?:Firm|Offices?|Group)|& Associates|Group|Partners)\b",
    re.IGNORECASE,
)

# Email in document context
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

# Phone number pattern
_PHONE_RE = re.compile(
    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}",
)

# "Electronically signed by" pattern
_ESIGNED_RE = re.compile(
    r"(?:/s/\s*|Electronically\s+(?:signed|filed)\s+by\s+)(.+)",
    re.IGNORECASE,
)

# "Attorney for" / "Counsel for" pattern
_ATTORNEY_FOR_RE = re.compile(
    r"(?:Attorneys?|Counsel)\s+for\s+(.+)",
    re.IGNORECASE,
)

# "Respectfully submitted" marker
_RESPECTFULLY_RE = re.compile(
    r"Respectfully\s+submitted[,.]?",
    re.IGNORECASE,
)

# Certificate of service marker
_CERT_SERVICE_RE = re.compile(
    r"Certificate\s+of\s+Service",
    re.IGNORECASE,
)

# Esquire suffix on attorney names
_ESQUIRE_RE = re.compile(
    r",?\s*Esq(?:uire)?\.?\s*$",
    re.IGNORECASE,
)

# State ZIP pattern (for address line detection)
_STATE_ZIP_RE = re.compile(
    r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b",
)

# Lines that are likely author names: title-case or ALL CAPS, relatively
# short, no punctuation other than period/comma, not a common heading.
_COMMON_HEADINGS = {
    "argument", "conclusion", "introduction", "statement of the case",
    "statement of facts", "table of contents", "table of authorities",
    "certificate of service", "certificate of compliance",
    "respectfully submitted", "summary of argument", "relief requested",
    "questions presented", "issues presented", "jurisdictional statement",
    "brief of defendant-appellant", "brief of plaintiff-appellee",
    "brief of appellant", "brief of appellee", "brief of respondent",
    "brief of petitioner", "reply brief", "opening brief",
    "answering brief", "amicus curiae brief", "memorandum of law",
    "motion to dismiss", "motion for summary judgment",
    "notice of appeal", "notice of motion", "points and authorities",
}

# Pattern for document title lines that should not be treated as names
_DOC_TITLE_RE = re.compile(
    r"^(?:brief|motion|memorandum|notice|petition|reply|response|"
    r"opposition|order|stipulation|declaration|affidavit)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Attribution detector
# ---------------------------------------------------------------------------


class AttributionDetector:
    """Detect author and organization attribution from documents."""

    def detect(self, file_path: Path) -> DetectedAttribution:
        """Auto-detect attribution from any supported file."""
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        if suffix == ".docx":
            return self.detect_from_docx(file_path)
        elif suffix == ".pdf":
            return self.detect_from_pdf(file_path)
        else:
            # Try text extraction as fallback
            try:
                text = file_path.read_text(errors="ignore")
                return self.detect_from_text(text)
            except Exception:
                return DetectedAttribution()

    def detect_from_docx(self, file_path: Path) -> DetectedAttribution:
        """Detect from DOCX (richest source: metadata + text).

        Extracts metadata from core_properties and also analyzes the
        full document text for signature blocks, letterhead, etc.
        """
        from docx import Document as DocxDocument

        file_path = Path(file_path)
        result = DetectedAttribution()

        try:
            docx = DocxDocument(str(file_path))
        except Exception:
            return result

        # --- Source 1: DOCX metadata ---
        meta_author = None
        meta_org = None
        try:
            props = docx.core_properties
            if props.author and props.author.strip():
                meta_author = props.author.strip()
            if hasattr(props, "company") and props.company and props.company.strip():
                meta_org = props.company.strip()
        except Exception:
            pass

        # Try to get company from the extended properties (app.xml)
        if meta_org is None:
            try:
                import lxml.etree as ET
                app_part = docx.part.package.part_related_by(
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"
                )
                if app_part is not None:
                    tree = ET.fromstring(app_part.blob)
                    ns = {"ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"}
                    company_el = tree.find("ep:Company", ns)
                    if company_el is not None and company_el.text and company_el.text.strip():
                        meta_org = company_el.text.strip()
            except Exception:
                pass

        if meta_author:
            result.author = self._normalize_author_name(meta_author)
            result.author_confidence = 0.5  # metadata alone is moderate
            result.sources.append("metadata")
        if meta_org:
            result.organization = self._normalize_org_name(meta_org)
            result.organization_confidence = 0.5
            if "metadata" not in result.sources:
                result.sources.append("metadata")

        # --- Source 2-5: text analysis ---
        text = "\n".join(para.text for para in docx.paragraphs)
        text_result = self.detect_from_text(text)

        # Merge: text-detected values can boost or override metadata
        result = self._merge_results(result, text_result)

        return result

    def detect_from_pdf(self, file_path: Path) -> DetectedAttribution:
        """Detect from PDF (text analysis only)."""
        import fitz

        file_path = Path(file_path)
        try:
            doc = fitz.open(str(file_path))
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
        except Exception:
            return DetectedAttribution()

        result = self.detect_from_text(text)

        # PDF metadata sometimes has author info too
        try:
            doc = fitz.open(str(file_path))
            metadata = doc.metadata
            doc.close()
            if metadata:
                pdf_author = metadata.get("author", "")
                if pdf_author and pdf_author.strip():
                    clean = self._normalize_author_name(pdf_author.strip())
                    if clean and not result.author:
                        result.author = clean
                        result.author_confidence = max(result.author_confidence, 0.4)
                        if "metadata" not in result.sources:
                            result.sources.append("metadata")
                    elif clean and result.author and clean.lower() == result.author.lower():
                        # Corroborating evidence
                        result.author_confidence = min(1.0, result.author_confidence + 0.15)
        except Exception:
            pass

        return result

    def detect_from_text(self, text: str) -> DetectedAttribution:
        """Detect from raw text content.

        Examines signature blocks, letterhead, certificate of service,
        and caption page for attribution information.
        """
        if not text or not text.strip():
            return DetectedAttribution()

        result = DetectedAttribution()
        lines = text.split("\n")

        # Try each source, accumulating evidence
        sig_info = self._extract_signature_block(text)
        if sig_info:
            if sig_info.get("author"):
                result.author = sig_info["author"]
                result.author_confidence = 0.85
            if sig_info.get("organization"):
                result.organization = sig_info["organization"]
                result.organization_confidence = 0.85
            if sig_info.get("identifier"):
                result.identifier = sig_info["identifier"]
            result.sources.append("signature_block")

        letterhead_info = self._extract_letterhead(lines)
        if letterhead_info:
            if letterhead_info.get("organization"):
                if not result.organization:
                    result.organization = letterhead_info["organization"]
                    result.organization_confidence = 0.7
                elif result.organization.lower() == letterhead_info["organization"].lower():
                    result.organization_confidence = min(1.0, result.organization_confidence + 0.1)
            if letterhead_info.get("author") and not result.author:
                result.author = letterhead_info["author"]
                result.author_confidence = 0.5
            if letterhead_info.get("identifier") and not result.identifier:
                result.identifier = letterhead_info["identifier"]
            result.sources.append("letterhead")

        cert_info = self._extract_cert_of_service(text)
        if cert_info:
            if cert_info.get("author"):
                if not result.author:
                    result.author = cert_info["author"]
                    result.author_confidence = 0.7
                elif result.author.lower() == cert_info["author"].lower():
                    result.author_confidence = min(1.0, result.author_confidence + 0.1)
            if cert_info.get("organization"):
                if not result.organization:
                    result.organization = cert_info["organization"]
                    result.organization_confidence = 0.65
                elif result.organization.lower() == cert_info["organization"].lower():
                    result.organization_confidence = min(1.0, result.organization_confidence + 0.1)
            if cert_info.get("identifier") and not result.identifier:
                result.identifier = cert_info["identifier"]
            result.sources.append("certificate_of_service")

        caption_info = self._extract_caption_author(text)
        if caption_info:
            if caption_info.get("author") and not result.author:
                result.author = caption_info["author"]
                result.author_confidence = 0.6
            if caption_info.get("organization") and not result.organization:
                result.organization = caption_info["organization"]
                result.organization_confidence = 0.6
            if caption_info.get("identifier") and not result.identifier:
                result.identifier = caption_info["identifier"]
            result.sources.append("caption")

        return result

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_signature_block(self, text: str) -> dict | None:
        """Find and parse the signature block.

        Looks for "Respectfully submitted" or "/s/" markers, then parses
        the block that follows for author name, organization, identifier, etc.
        """
        # Find "Respectfully submitted" marker
        match = _RESPECTFULLY_RE.search(text)
        if match:
            block_start = match.end()
            # Take next ~20 lines after the marker
            remainder = text[block_start:]
            block_lines = remainder.split("\n")[:25]
            return self._parse_author_block(block_lines)

        # Look for /s/ or "Electronically signed by" anywhere
        esign_match = _ESIGNED_RE.search(text)
        if esign_match:
            name_raw = esign_match.group(1).strip()
            # The lines following the e-signature often have org info
            block_start = esign_match.end()
            remainder = text[block_start:]
            block_lines = remainder.split("\n")[:20]
            info = self._parse_author_block(block_lines)
            if info is None:
                info = {}
            if not info.get("author"):
                info["author"] = self._normalize_author_name(name_raw)
            return info

        return None

    def _parse_author_block(self, lines: list[str]) -> dict | None:
        """Parse a block of lines (after signature marker) for author info.

        Expected structure (with variations):
            [blank lines]
            /s/ Author Name  OR  AUTHOR NAME
            Organization Name, LLP
            123 Main Street
            City, State ZIP
            (555) 555-5555
            author@org.com
            State Bar No. 1234567
            Attorney for Defendant-Appellant
        """
        result: dict = {}
        non_blank_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped:
                non_blank_lines.append(stripped)

        if not non_blank_lines:
            return None

        # Check for e-signature on first non-blank line
        first_line = non_blank_lines[0]
        esign = _ESIGNED_RE.match(first_line)
        if esign:
            result["author"] = self._normalize_author_name(esign.group(1).strip())
            non_blank_lines = non_blank_lines[1:]
        elif first_line.startswith("/s/"):
            name_part = first_line[3:].strip()
            if name_part:
                result["author"] = self._normalize_author_name(name_part)
            non_blank_lines = non_blank_lines[1:]

        for line in non_blank_lines:
            # Bar number / identifier
            bar_match = _BAR_NUMBER_RE.search(line)
            if bar_match:
                result["identifier"] = bar_match.group(1)
                continue

            # Email -- skip as attribution source but note it
            if _EMAIL_RE.match(line.strip()):
                continue

            # Phone number line -- skip
            if _PHONE_RE.match(line.strip()):
                continue

            # Address line (state + ZIP) -- skip
            if _STATE_ZIP_RE.search(line):
                continue

            # "Attorney for" / "Counsel for" line
            atty_for = _ATTORNEY_FOR_RE.match(line)
            if atty_for:
                continue

            # Organization name detection (line contains org suffix)
            if not result.get("organization") and _ORG_SUFFIX_RE.search(line):
                result["organization"] = self._normalize_org_name(line)
                continue

            if not result.get("organization") and _ORG_NAME_PATTERNS.search(line):
                result["organization"] = self._normalize_org_name(line)
                continue

            # Author name detection: first name-like line we haven't
            # classified as something else
            if not result.get("author") and self._looks_like_author_name(line):
                result["author"] = self._normalize_author_name(line)
                continue

        return result if result else None

    def _extract_letterhead(self, lines: list[str]) -> dict | None:
        """Check first ~10 lines for organization letterhead patterns.

        Letterhead typically appears at the very top of page 1 and contains
        the organization name (often with LLP/LLC/P.C.), address, and phone number.
        """
        result: dict = {}
        # Look at up to the first 15 non-blank lines
        header_lines: list[str] = []
        for line in lines[:30]:
            stripped = line.strip()
            if stripped:
                header_lines.append(stripped)
            if len(header_lines) >= 15:
                break

        if not header_lines:
            return None

        for line in header_lines:
            # Check for organization name patterns
            if not result.get("organization"):
                if _ORG_SUFFIX_RE.search(line):
                    result["organization"] = self._normalize_org_name(line)
                    continue
                if _ORG_NAME_PATTERNS.search(line):
                    result["organization"] = self._normalize_org_name(line)
                    continue

            # Bar number / identifier in header area
            bar_match = _BAR_NUMBER_RE.search(line)
            if bar_match and not result.get("identifier"):
                result["identifier"] = bar_match.group(1)

            # Author name in header (usually near a bar number or org)
            if not result.get("author") and self._looks_like_author_name(line):
                # Only count as author if we also found an org or identifier nearby
                if result.get("organization") or result.get("identifier"):
                    result["author"] = self._normalize_author_name(line)

        return result if result else None

    def _extract_cert_of_service(self, text: str) -> dict | None:
        """Find author info in certificate of service.

        The certificate of service often names the filing author:
        "I, [author name], hereby certify..."
        or ends with the author's signature block.
        """
        match = _CERT_SERVICE_RE.search(text)
        if not match:
            return None

        cert_text = text[match.start():]
        # Limit to ~40 lines of the certificate section
        cert_lines = cert_text.split("\n")[:40]
        result: dict = {}

        # Look for "I, [Name], hereby certify" pattern
        i_certify_re = re.compile(
            r"I,\s+([A-Z][a-zA-Z\-']+(?:\s+[A-Z][a-zA-Z\-']+)+)\s*,\s*(?:hereby\s+)?certif",
            re.IGNORECASE,
        )
        for line in cert_lines:
            m = i_certify_re.search(line)
            if m:
                result["author"] = self._normalize_author_name(m.group(1))
                break

        # Also look for a mini signature block within the cert
        for i, line in enumerate(cert_lines):
            stripped = line.strip()
            if not stripped:
                continue

            bar_match = _BAR_NUMBER_RE.search(stripped)
            if bar_match:
                result["identifier"] = bar_match.group(1)

            if not result.get("organization") and _ORG_SUFFIX_RE.search(stripped):
                result["organization"] = self._normalize_org_name(stripped)

            if not result.get("organization") and _ORG_NAME_PATTERNS.search(stripped):
                result["organization"] = self._normalize_org_name(stripped)

            # /s/ in cert of service
            esign = _ESIGNED_RE.match(stripped)
            if esign and not result.get("author"):
                result["author"] = self._normalize_author_name(esign.group(1))

            if stripped.startswith("/s/") and not result.get("author"):
                name_part = stripped[3:].strip()
                if name_part:
                    result["author"] = self._normalize_author_name(name_part)

        return result if result else None

    def _extract_caption_author(self, text: str) -> dict | None:
        """Extract author identification from the caption page.

        Below the caption block, authors are often listed with their
        identifiers and organization names.
        """
        result: dict = {}

        # Look for "Attorney for" or "Counsel for" lines
        for match in _ATTORNEY_FOR_RE.finditer(text):
            # The lines just before "Attorney for" often contain the
            # author name and organization.
            line_start = text.rfind("\n", 0, match.start())
            if line_start == -1:
                line_start = 0
            # Look at the ~10 lines before this marker
            preceding = text[max(0, line_start - 500):match.start()]
            preceding_lines = [l.strip() for l in preceding.split("\n") if l.strip()]

            # Scan preceding lines (bottom-up) for name/org
            for pline in reversed(preceding_lines[-10:]):
                bar_match = _BAR_NUMBER_RE.search(pline)
                if bar_match and not result.get("identifier"):
                    result["identifier"] = bar_match.group(1)
                    continue

                if not result.get("organization") and _ORG_SUFFIX_RE.search(pline):
                    result["organization"] = self._normalize_org_name(pline)
                    continue

                if not result.get("organization") and _ORG_NAME_PATTERNS.search(pline):
                    result["organization"] = self._normalize_org_name(pline)
                    continue

                if not result.get("author") and self._looks_like_author_name(pline):
                    result["author"] = self._normalize_author_name(pline)
                    continue

            # Only need the first "Attorney for" block
            if result:
                break

        return result if result else None

    # ------------------------------------------------------------------
    # Name normalization and classification
    # ------------------------------------------------------------------

    def _normalize_org_name(self, raw: str) -> str:
        """Clean up a detected organization name.

        Removes trailing commas, excess whitespace, common non-org
        prefixes/suffixes. Preserves the entity suffix (LLP, etc.).
        """
        name = raw.strip()
        # Remove leading "By:" or "By :"
        name = re.sub(r"^By\s*:\s*", "", name, flags=re.IGNORECASE)
        # Remove trailing commas and semicolons
        name = name.rstrip(",;")
        # Remove leading/trailing quotes
        name = name.strip("\"'")
        # Collapse whitespace
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def _normalize_author_name(self, raw: str) -> str:
        """Clean up a detected author name.

        Removes Esq. suffix, bar number references, leading /s/ markers,
        and other artifacts. Returns a clean proper-case name.
        """
        name = raw.strip()
        # Remove /s/ prefix
        if name.startswith("/s/"):
            name = name[3:].strip()
        # Remove "By:" prefix
        name = re.sub(r"^By\s*:\s*", "", name, flags=re.IGNORECASE)
        # Remove Esquire suffix
        name = _ESQUIRE_RE.sub("", name).strip()
        # Remove bar number from the end
        name = _BAR_NUMBER_RE.sub("", name).strip()
        # Remove trailing comma
        name = name.rstrip(",").strip()
        # Remove underscores used as signature lines
        name = name.strip("_").strip()
        # Remove leading/trailing quotes
        name = name.strip("\"'")
        # If ALL CAPS, convert to title case
        if name == name.upper() and len(name) > 2:
            name = name.title()
        # Collapse whitespace
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def _looks_like_author_name(self, line: str) -> bool:
        """Heuristic: does this line look like a person's name?

        Checks for:
        - 2-5 words, mostly alphabetic
        - Title case or ALL CAPS
        - Not a known section heading
        - Not an address, phone, or email
        - Has Esq. suffix, or matches name-like pattern
        """
        stripped = line.strip()
        if not stripped or len(stripped) > 80:
            return False

        # Reject lines that are clearly not names
        if _EMAIL_RE.search(stripped):
            return False
        if _PHONE_RE.match(stripped):
            return False
        if _STATE_ZIP_RE.search(stripped):
            return False
        if _ATTORNEY_FOR_RE.match(stripped):
            return False
        if _ORG_SUFFIX_RE.search(stripped):
            return False
        if _ORG_NAME_PATTERNS.search(stripped):
            return False
        if _BAR_NUMBER_RE.search(stripped):
            return False

        # Check against known section headings
        if stripped.lower().rstrip(":., ") in _COMMON_HEADINGS:
            return False

        # Reject document title lines ("Brief of ...", "Motion to ...", etc.)
        if _DOC_TITLE_RE.match(stripped):
            return False

        # Remove Esq. for analysis
        clean = _ESQUIRE_RE.sub("", stripped).strip()

        # If it has Esq. suffix, strong signal it's a name
        has_esquire = _ESQUIRE_RE.search(stripped) is not None

        # Count words
        words = clean.split()
        if len(words) < 2 or len(words) > 6:
            return False

        # All words should start with uppercase (title case or ALL CAPS)
        alpha_words = [w for w in words if w[0].isalpha()]
        if not alpha_words:
            return False
        if not all(w[0].isupper() for w in alpha_words):
            return False

        # Most characters should be alphabetic (allow hyphens, apostrophes, periods)
        alpha_ratio = sum(1 for c in clean if c.isalpha()) / max(len(clean), 1)
        if alpha_ratio < 0.7:
            return False

        # Esquire suffix is a strong positive signal
        if has_esquire:
            return True

        # Heuristic: short title-case line with 2-4 words is likely a name
        if 2 <= len(alpha_words) <= 4:
            # Reject if it looks like a sentence (has common verbs/articles as non-first word)
            lowered = [w.lower() for w in alpha_words]
            sentence_words = {"the", "a", "an", "is", "are", "was", "were", "of",
                              "and", "or", "in", "on", "at", "to", "for", "with",
                              "this", "that", "by", "from", "has", "have", "not"}
            # Allow "of" and "de" in names but reject if too many common words
            common_count = sum(1 for w in lowered[1:] if w in sentence_words)
            if common_count > 1:
                return False
            return True

        return False

    # ------------------------------------------------------------------
    # Merging results from multiple sources
    # ------------------------------------------------------------------

    def _merge_results(
        self,
        primary: DetectedAttribution,
        secondary: DetectedAttribution,
    ) -> DetectedAttribution:
        """Merge two DetectedAttribution results.

        Primary (e.g., metadata) is used as base; secondary (e.g., text
        analysis) can override if it has higher confidence, or boost
        confidence if values agree.
        """
        merged = DetectedAttribution()
        merged.sources = list(set(primary.sources + secondary.sources))

        # Author
        if primary.author and secondary.author:
            if primary.author.lower() == secondary.author.lower():
                # Corroboration: boost confidence
                merged.author = primary.author
                merged.author_confidence = min(1.0, max(
                    primary.author_confidence, secondary.author_confidence
                ) + 0.15)
            elif secondary.author_confidence > primary.author_confidence:
                # Text analysis is more confident (e.g., signature block)
                merged.author = secondary.author
                merged.author_confidence = secondary.author_confidence
            else:
                merged.author = primary.author
                merged.author_confidence = primary.author_confidence
        elif primary.author:
            merged.author = primary.author
            merged.author_confidence = primary.author_confidence
        elif secondary.author:
            merged.author = secondary.author
            merged.author_confidence = secondary.author_confidence

        # Organization
        if primary.organization and secondary.organization:
            if primary.organization.lower() == secondary.organization.lower():
                merged.organization = primary.organization
                merged.organization_confidence = min(1.0, max(
                    primary.organization_confidence, secondary.organization_confidence
                ) + 0.15)
            elif secondary.organization_confidence > primary.organization_confidence:
                merged.organization = secondary.organization
                merged.organization_confidence = secondary.organization_confidence
            else:
                merged.organization = primary.organization
                merged.organization_confidence = primary.organization_confidence
        elif primary.organization:
            merged.organization = primary.organization
            merged.organization_confidence = primary.organization_confidence
        elif secondary.organization:
            merged.organization = secondary.organization
            merged.organization_confidence = secondary.organization_confidence

        # Identifier: prefer the one from the most reliable source
        merged.identifier = primary.identifier or secondary.identifier

        return merged
