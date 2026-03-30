"""ML Pipeline orchestrator - ties all ML components together."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import json
import hashlib
from datetime import datetime

from legal_format_engine.ml.normalizer import NormalizedDocument, normalize_document
from legal_format_engine.ml.features import FeatureVector, extract_features
from legal_format_engine.ml.learner import LearnedPatterns, learn_patterns
from legal_format_engine.ml.synthesizer import synthesize_ruleset, recommend_changes
from legal_format_engine.ml.attribution import detect_attribution, detect_from_docx_metadata
from legal_format_engine.ml.firm_database import FirmDatabase
from legal_format_engine.ml.style_profiles import StyleProfile, build_style_profile, resolve_format
from legal_format_engine.ml.archive import extract_archive, SUPPORTED_EXTENSIONS

STORAGE_DIR = Path.home() / ".legal-format-engine" / "ml_documents"


class MLPipeline:
    """Main ML pipeline orchestrator."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or STORAGE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.firm_db = FirmDatabase()
        self._documents: list[dict] = []
        self._load_index()

    def _load_index(self):
        """Load document index from storage."""
        index_path = self.storage_dir / "index.json"
        if index_path.exists():
            self._documents = json.loads(index_path.read_text())

    def _save_index(self):
        """Save document index to storage."""
        index_path = self.storage_dir / "index.json"
        index_path.write_text(json.dumps(self._documents, indent=2))

    def ingest(
        self,
        data: bytes,
        filename: str,
        jurisdiction: Optional[str] = None,
        court_level: Optional[str] = None,
        document_type: Optional[str] = None,
        author: Optional[str] = None,
        firm: Optional[str] = None,
    ) -> dict:
        """Ingest a document for ML processing.

        1. Detect format and parse
        2. Extract format profile
        3. Auto-detect attribution if not provided
        4. Normalize firm name via database
        5. Store normalized representation
        """
        ext = Path(filename).suffix.lower()

        # Check if it's an archive
        if ext in (".zip", ".rar") or (ext == ".pdf" and self._looks_like_portfolio(data)):
            return self.ingest_archive(data, filename, jurisdiction, author, firm)

        # Parse and extract profile
        profile = self._extract_profile(data, ext, filename)

        # Auto-detect attribution
        if not author or not firm:
            text = self._extract_text(data, ext)
            if text:
                attr = detect_attribution(text)
                if not author and attr.author:
                    author = attr.author
                if not firm and attr.firm:
                    firm = attr.firm

        # Normalize firm via database
        if firm:
            match = self.firm_db.lookup(firm)
            if match:
                firm = match.canonical_name

        # Build profile dict
        profile_dict = {
            "fonts": [{"font_name": f.font_name, "font_size_pt": f.font_size_pt}
                      for f in (profile.fonts if hasattr(profile, 'fonts') else [])],
            "margins": {
                "top_inches": profile.margins.top_inches,
                "bottom_inches": profile.margins.bottom_inches,
                "left_inches": profile.margins.left_inches,
                "right_inches": profile.margins.right_inches,
            } if hasattr(profile, 'margins') and profile.margins else {},
            "headings": [{"text": h.text, "level": h.level, "bold": h.bold}
                        for h in (profile.headings if hasattr(profile, 'headings') else [])],
            "jurisdiction": jurisdiction,
            "court_level": court_level,
            "document_type": document_type,
        }

        # Normalize
        normalized = normalize_document(
            profile_dict,
            source_format=ext.lstrip("."),
            file_name=filename,
            author=author,
            firm=firm,
        )

        # Store
        doc_id = hashlib.md5(data).hexdigest()[:12]
        doc_record = {
            "id": doc_id,
            "filename": filename,
            "format": ext,
            "jurisdiction": jurisdiction,
            "court_level": court_level,
            "document_type": document_type,
            "author": author,
            "firm": firm,
            "ingested_at": datetime.utcnow().isoformat(),
            "normalized": {
                "font_name": normalized.font_name,
                "font_size_pt": normalized.font_size_pt,
                "margin_top": normalized.margin_top,
                "margin_bottom": normalized.margin_bottom,
                "margin_left": normalized.margin_left,
                "margin_right": normalized.margin_right,
                "line_spacing": normalized.line_spacing,
                "confidence": normalized.confidence,
            },
        }

        # Save raw file
        (self.storage_dir / f"{doc_id}{ext}").write_bytes(data)

        self._documents.append(doc_record)
        self._save_index()

        return {"id": doc_id, "filename": filename, "author": author, "firm": firm}

    def ingest_archive(
        self,
        data: bytes,
        filename: str,
        jurisdiction: Optional[str] = None,
        author: Optional[str] = None,
        firm: Optional[str] = None,
    ) -> list[dict]:
        """Ingest all documents from an archive."""
        extracted = extract_archive(data, filename)
        results = []
        for name, file_data in extracted:
            r = self.ingest(
                data=file_data,
                filename=name,
                jurisdiction=jurisdiction,
                author=author,
                firm=firm,
            )
            if isinstance(r, dict):
                results.append(r)
            elif isinstance(r, list):
                results.extend(r)
        return results

    def learn(self, jurisdiction: Optional[str] = None) -> dict:
        """Run the learner on stored documents."""
        docs = self._documents
        if jurisdiction:
            docs = [d for d in docs if d.get("jurisdiction") == jurisdiction]

        if not docs:
            return {"message": "No documents to learn from", "document_count": 0}

        # Build feature vectors from stored normalized data
        vectors = []
        for doc in docs:
            n = doc.get("normalized", {})
            fv = FeatureVector(
                source_format=doc.get("format", "").lstrip("."),
                confidence=n.get("confidence", 0.5),
                author=doc.get("author"),
                firm=doc.get("firm"),
                jurisdiction=doc.get("jurisdiction"),
            )
            if n.get("font_size_pt"):
                fv.font_size = (n["font_size_pt"], n.get("confidence", 0.5))
            if n.get("margin_top"):
                fv.margin_top = (n["margin_top"], n.get("confidence", 0.5))
            if n.get("margin_bottom"):
                fv.margin_bottom = (n["margin_bottom"], n.get("confidence", 0.5))
            if n.get("margin_left"):
                fv.margin_left = (n["margin_left"], n.get("confidence", 0.5))
            if n.get("margin_right"):
                fv.margin_right = (n["margin_right"], n.get("confidence", 0.5))
            if n.get("line_spacing"):
                fv.line_spacing = (n["line_spacing"], n.get("confidence", 0.5))
            if n.get("font_name"):
                fv.font_name = (n["font_name"], n.get("confidence", 0.5))
            vectors.append(fv)

        patterns = learn_patterns(vectors)
        return {
            "document_count": patterns.document_count,
            "font_name": patterns.font_name,
            "font_size_pt": patterns.font_size_pt,
            "margin_top": patterns.margin_top,
            "margin_bottom": patterns.margin_bottom,
            "margin_left": patterns.margin_left,
            "margin_right": patterns.margin_right,
            "line_spacing": patterns.line_spacing,
            "first_line_indent": patterns.first_line_indent,
        }

    def suggest_ruleset(self, jurisdiction: str = "wisconsin") -> str:
        """Generate a YAML ruleset from learned patterns."""
        learned = self.learn(jurisdiction)
        patterns = LearnedPatterns(
            font_name=learned.get("font_name"),
            font_size_pt=learned.get("font_size_pt"),
            margin_top=learned.get("margin_top"),
            margin_bottom=learned.get("margin_bottom"),
            margin_left=learned.get("margin_left"),
            margin_right=learned.get("margin_right"),
            line_spacing=learned.get("line_spacing"),
            first_line_indent=learned.get("first_line_indent"),
            document_count=learned.get("document_count", 0),
            jurisdiction=jurisdiction,
        )
        return synthesize_ruleset(patterns)

    def recommend(self, jurisdiction: str = "wisconsin") -> list[dict]:
        """Compare ML patterns against existing ruleset."""
        learned = self.learn(jurisdiction)
        patterns = LearnedPatterns(
            font_name=learned.get("font_name"),
            font_size_pt=learned.get("font_size_pt"),
            margin_top=learned.get("margin_top"),
            margin_bottom=learned.get("margin_bottom"),
            margin_left=learned.get("margin_left"),
            margin_right=learned.get("margin_right"),
            document_count=learned.get("document_count", 0),
            first_line_indent=learned.get("first_line_indent"),
        )
        return recommend_changes(patterns, jurisdiction)

    def list_documents(self) -> list[dict]:
        return self._documents

    def stats(self) -> dict:
        jurisdictions = {}
        formats = {}
        firms = {}
        for d in self._documents:
            j = d.get("jurisdiction", "unknown")
            jurisdictions[j] = jurisdictions.get(j, 0) + 1
            f = d.get("format", "unknown")
            formats[f] = formats.get(f, 0) + 1
            firm = d.get("firm", "unknown")
            if firm:
                firms[firm] = firms.get(firm, 0) + 1
        return {
            "total_documents": len(self._documents),
            "by_jurisdiction": jurisdictions,
            "by_format": formats,
            "by_firm": firms,
        }

    def list_styles(self) -> list[dict]:
        """List learned style profiles by author/firm."""
        authors = {}
        firms = {}
        for d in self._documents:
            if d.get("author"):
                authors.setdefault(d["author"], []).append(d)
            if d.get("firm"):
                firms.setdefault(d["firm"], []).append(d)

        styles = []
        for name, docs in {**authors, **firms}.items():
            styles.append({
                "identifier": name,
                "document_count": len(docs),
            })
        return styles

    def get_style(self, identifier: str) -> Optional[dict]:
        """Get a specific style profile."""
        docs = [d for d in self._documents if d.get("author") == identifier or d.get("firm") == identifier]
        if not docs:
            return None
        return {
            "identifier": identifier,
            "document_count": len(docs),
            "documents": [{"id": d["id"], "filename": d["filename"]} for d in docs],
        }

    def resolve_format(
        self,
        jurisdiction: str = "wisconsin",
        document_type: str = "appellate_brief",
        author: Optional[str] = None,
        firm: Optional[str] = None,
    ) -> dict:
        """Resolve final format using rule hierarchy."""
        from legal_format_engine.rules.base import load_ruleset

        try:
            ruleset = load_ruleset(jurisdiction, document_type)
            court_rules = {
                "font": ruleset.page_format.font,
                "font_size_pt": ruleset.page_format.font_size_pt,
                "margin_top_inches": ruleset.page_format.margin_top_inches,
                "margin_bottom_inches": ruleset.page_format.margin_bottom_inches,
                "margin_left_inches": ruleset.page_format.margin_left_inches,
                "margin_right_inches": ruleset.page_format.margin_right_inches,
                "line_spacing": ruleset.page_format.line_spacing,
            }
        except FileNotFoundError:
            court_rules = {}

        ml_patterns = self.learn(jurisdiction)
        ml_dict = {
            "first_line_indent_inches": ml_patterns.get("first_line_indent"),
        }

        style = None
        defaults = {
            "font": "Times New Roman",
            "font_size_pt": 12,
            "margin_top_inches": 1.0,
            "margin_bottom_inches": 1.0,
            "margin_left_inches": 1.0,
            "margin_right_inches": 1.0,
            "line_spacing": "double",
            "first_line_indent_inches": 0.5,
        }

        return resolve_format(court_rules, ml_dict, style, defaults)

    def _extract_profile(self, data: bytes, ext: str, filename: str):
        """Extract format profile from file data."""
        if ext == ".docx":
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
                f.write(data)
                f.flush()
                from legal_format_engine.parsers.docx_parser import extract_format_profile
                profile = extract_format_profile(f.name)
                os.unlink(f.name)
                return profile
        elif ext == ".pdf":
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(data)
                f.flush()
                from legal_format_engine.parsers.pdf_parser import extract_format_profile
                profile = extract_format_profile(f.name)
                os.unlink(f.name)
                return profile

        # Fallback: empty profile
        from legal_format_engine.models.patterns import FormatProfile
        return FormatProfile()

    def _extract_text(self, data: bytes, ext: str) -> Optional[str]:
        """Extract text from file data."""
        if ext == ".docx":
            from legal_format_engine.parsers.docx_parser import parse_docx_bytes
            doc = parse_docx_bytes(data)
            parts = []
            for s in doc.sections:
                parts.append(s.heading)
                for b in s.content:
                    parts.append(b.text)
            return "\n".join(parts)
        elif ext in (".txt", ".html", ".htm"):
            return data.decode("utf-8", errors="replace")
        return None

    def _looks_like_portfolio(self, data: bytes) -> bool:
        """Check if PDF might be an Adobe Portfolio."""
        try:
            import fitz
            doc = fitz.open(stream=data, filetype="pdf")
            has_files = doc.embfile_count() > 0
            doc.close()
            return has_files
        except Exception:
            return False
