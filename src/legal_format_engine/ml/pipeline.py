"""ML Pipeline orchestrator: end-to-end document processing and learning.

This is the single entry point for the ML system. It coordinates:
1. Document ingestion (any format)
2. Normalization (strip format quirks)
3. Feature extraction
4. Storage of normalized documents
5. Learning from stored documents
6. Synthesizing formatting specs

Usage:
    pipeline = MLPipeline()

    # Ingest a document
    result = pipeline.ingest("brief.docx", jurisdiction="wisconsin")

    # Learn from all Wisconsin documents
    learned = pipeline.learn(jurisdiction="wisconsin")

    # Get a suggested ruleset
    ruleset = pipeline.suggest_ruleset(jurisdiction="wisconsin")

    # Compare against existing ruleset
    recs = pipeline.recommend(jurisdiction="wisconsin")

    # Ingest an archive (ZIP, RAR, Adobe Portfolio)
    results = pipeline.ingest_archive("briefs.zip", jurisdiction="wisconsin")
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal_format_engine.ml.normalizer import (
    NormalizedDocument,
    normalize_document,
)
from legal_format_engine.ml.features import DocumentFeatures, extract_features
from legal_format_engine.ml.learner import FormatLearner, LearnedFormat
from legal_format_engine.ml.synthesizer import (
    FormatRecommendation,
    diff_against_ruleset,
    synthesize_ruleset,
)


_DEFAULT_STORE_DIR = Path.home() / ".legal-format-engine" / "ml_documents"


class MLPipeline:
    """End-to-end ML pipeline for legal document formatting."""

    def __init__(self, store_dir: Path | None = None):
        self._store_dir = store_dir or _DEFAULT_STORE_DIR
        self._store_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Ingest: normalize and store a document
    # ------------------------------------------------------------------

    def ingest(
        self,
        file_path: str | Path,
        jurisdiction: str | None = None,
        court_level: str | None = None,
        document_type: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> NormalizedDocument:
        """Ingest a document: normalize it and store for learning.

        Accepts: .docx, .pdf, .doc, .html, .rtf
        Returns the NormalizedDocument.
        """
        file_path = Path(file_path)

        # Normalize
        doc = normalize_document(
            str(file_path),
            jurisdiction=jurisdiction,
            court_level=court_level,
            document_type=document_type,
        )

        # Store
        self._save_normalized(doc, tags=tags, notes=notes)

        return doc

    def ingest_batch(
        self,
        file_paths: list[str | Path],
        jurisdiction: str | None = None,
        court_level: str | None = None,
        document_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[NormalizedDocument]:
        """Ingest multiple documents at once."""
        results = []
        for fp in file_paths:
            try:
                doc = self.ingest(
                    fp,
                    jurisdiction=jurisdiction,
                    court_level=court_level,
                    document_type=document_type,
                    tags=tags,
                )
                results.append(doc)
            except Exception:
                # Skip failed documents but don't stop batch
                continue
        return results

    def ingest_archive(
        self,
        archive_path: str | Path,
        jurisdiction: str | None = None,
        court_level: str | None = None,
        document_type: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> dict:
        """Ingest all documents from an archive (ZIP, RAR, Adobe Portfolio).

        Extracts the archive, filters to supported document types, and
        ingests each one through the full normalization pipeline.

        Returns a summary dict with processed/failed counts and details.
        """
        from legal_format_engine.ml.archive import (
            cleanup_extraction,
            extract_archive,
            is_archive,
        )

        archive_path = Path(archive_path)
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        # Extract files from archive
        extracted_dir = None
        try:
            extracted_files = extract_archive(archive_path)
            # The extraction creates a temp dir; infer it from the first file
            if extracted_files:
                extracted_dir = extracted_files[0].parent

            results = []
            errors = []

            for file_path in extracted_files:
                try:
                    doc = self.ingest(
                        file_path,
                        jurisdiction=jurisdiction,
                        court_level=court_level,
                        document_type=document_type,
                        tags=tags,
                        notes=notes,
                    )
                    results.append({
                        "id": doc.id,
                        "source_filename": file_path.name,
                        "source_format": doc.source_format,
                        "extraction_confidence": doc.extraction_confidence,
                        "primary_font": doc.primary_font.family if doc.primary_font else None,
                        "font_size_pt": doc.primary_font.size_pt if doc.primary_font else None,
                    })
                except Exception as exc:
                    errors.append({
                        "filename": file_path.name,
                        "error": str(exc),
                    })

            return {
                "archive_filename": archive_path.name,
                "total_files_found": len(extracted_files),
                "processed": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors,
            }

        finally:
            if extracted_dir is not None:
                cleanup_extraction(extracted_dir)

    # ------------------------------------------------------------------
    # Learn: run the learner on stored documents
    # ------------------------------------------------------------------

    def learn(
        self,
        jurisdiction: str | None = None,
        court_level: str | None = None,
        document_type: str | None = None,
        tags: list[str] | None = None,
    ) -> LearnedFormat:
        """Learn formatting patterns from stored documents matching the filter.

        Returns a LearnedFormat with confidence-weighted patterns.
        """
        docs = self._load_matching(jurisdiction, court_level, document_type, tags)

        if not docs:
            return LearnedFormat(
                jurisdiction=jurisdiction,
                court_level=court_level,
                document_type=document_type,
            )

        # Extract features from each normalized document
        features_list = [extract_features(doc) for doc in docs]

        # Run the learner
        learner = FormatLearner()
        learner.add_all(features_list)
        return learner.learn()

    # ------------------------------------------------------------------
    # Synthesize: generate formatting specs
    # ------------------------------------------------------------------

    def suggest_ruleset(
        self,
        jurisdiction: str | None = None,
        court_level: str = "appellate",
        document_type: str = "brief",
        tags: list[str] | None = None,
    ) -> dict:
        """Generate a suggested YAML-compatible ruleset from learned patterns."""
        learned = self.learn(jurisdiction, court_level, document_type, tags)
        return synthesize_ruleset(learned, jurisdiction, court_level, document_type)

    def recommend(
        self,
        jurisdiction: str,
        court_level: str = "appellate",
        document_type: str = "brief",
        tags: list[str] | None = None,
    ) -> list[dict]:
        """Compare learned patterns against existing ruleset and recommend changes.

        Returns a list of recommendation dicts.
        """
        # Load existing ruleset
        existing = self._load_existing_ruleset(jurisdiction, court_level, document_type)
        if not existing:
            return []

        # Learn patterns
        learned = self.learn(jurisdiction, court_level, document_type, tags)

        # Diff
        recs = diff_against_ruleset(learned, existing)
        return [r.to_dict() for r in recs]

    # ------------------------------------------------------------------
    # Query stored documents
    # ------------------------------------------------------------------

    def list_documents(
        self,
        jurisdiction: str | None = None,
        court_level: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """List stored normalized documents matching a filter."""
        docs = self._load_matching(jurisdiction, court_level, tags=tags)
        return [
            {
                "id": d.id,
                "source_filename": d.source_filename,
                "source_format": d.source_format,
                "jurisdiction": d.jurisdiction,
                "court_level": d.court_level,
                "document_type": d.document_type,
                "extraction_confidence": d.extraction_confidence,
                "normalized_at": d.normalized_at,
                "primary_font": d.primary_font.family if d.primary_font else None,
                "font_size": d.primary_font.size_pt if d.primary_font else None,
            }
            for d in docs
        ]

    def get_document(self, doc_id: str) -> NormalizedDocument | None:
        """Load a specific normalized document by ID."""
        doc_path = self._store_dir / f"{doc_id}.json"
        if not doc_path.exists():
            return None
        data = json.loads(doc_path.read_text())
        return NormalizedDocument.model_validate(data.get("document", data))

    def delete_document(self, doc_id: str) -> bool:
        """Delete a stored document."""
        doc_path = self._store_dir / f"{doc_id}.json"
        if doc_path.exists():
            doc_path.unlink()
            return True
        return False

    def get_stats(self) -> dict:
        """Get statistics about stored documents."""
        docs = self._load_all()
        jurisdictions: dict[str, int] = {}
        formats: dict[str, int] = {}
        for d in docs:
            j = d.jurisdiction or "untagged"
            jurisdictions[j] = jurisdictions.get(j, 0) + 1
            formats[d.source_format] = formats.get(d.source_format, 0) + 1

        return {
            "total_documents": len(docs),
            "by_jurisdiction": jurisdictions,
            "by_format": formats,
        }

    # ------------------------------------------------------------------
    # Storage internals
    # ------------------------------------------------------------------

    def _save_normalized(
        self,
        doc: NormalizedDocument,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> None:
        """Save a NormalizedDocument to disk."""
        record = {
            "document": doc.model_dump(),
            "tags": tags or [],
            "notes": notes,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        out_path = self._store_dir / f"{doc.id}.json"
        out_path.write_text(json.dumps(record, indent=2, default=str))

    def _load_all(self) -> list[NormalizedDocument]:
        """Load all stored normalized documents."""
        docs = []
        for f in self._store_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                doc_data = data.get("document", data)
                docs.append(NormalizedDocument.model_validate(doc_data))
            except Exception:
                continue
        return docs

    def _load_matching(
        self,
        jurisdiction: str | None = None,
        court_level: str | None = None,
        document_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[NormalizedDocument]:
        """Load documents matching the given filter criteria."""
        all_docs = []
        for f in self._store_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                doc_data = data.get("document", data)
                doc = NormalizedDocument.model_validate(doc_data)
                stored_tags = data.get("tags", [])

                # Apply filters
                if jurisdiction and doc.jurisdiction != jurisdiction:
                    continue
                if court_level and doc.court_level != court_level:
                    continue
                if document_type and doc.document_type != document_type:
                    continue
                if tags and not any(t in stored_tags for t in tags):
                    continue

                all_docs.append(doc)
            except Exception:
                continue

        return all_docs

    def _load_existing_ruleset(
        self,
        jurisdiction: str,
        court_level: str,
        document_type: str,
    ) -> dict | None:
        """Load an existing YAML ruleset as a dict for comparison."""
        try:
            from legal_format_engine.rules.loader import load_ruleset
            ruleset = load_ruleset(jurisdiction, court_level, document_type)
            return ruleset.model_dump()
        except FileNotFoundError:
            return None
