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
    result = pipeline.ingest("document.docx", category="reports")

    # Learn from all documents in a category
    learned = pipeline.learn(category="reports")

    # Get a suggested ruleset
    ruleset = pipeline.suggest_ruleset(category="reports")

    # Compare against existing ruleset
    recs = pipeline.recommend(category="reports")

    # Ingest an archive (ZIP, RAR, Adobe Portfolio)
    results = pipeline.ingest_archive("documents.zip", category="reports")
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anchor_ml_engine.normalizer import (
    NormalizedDocument,
    normalize_document,
)
from anchor_ml_engine.features import DocumentFeatures, extract_features
from anchor_ml_engine.learner import FormatLearner, LearnedFormat
from anchor_ml_engine.synthesizer import (
    FormatRecommendation,
    diff_against_ruleset,
    synthesize_ruleset,
)


_DEFAULT_STORE_DIR = Path.home() / ".anchor-ml-engine" / "ml_documents"


class MLPipeline:
    """End-to-end ML pipeline for document format learning."""

    def __init__(self, store_dir: Path | None = None):
        self._store_dir = store_dir or _DEFAULT_STORE_DIR
        self._store_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Ingest: normalize and store a document
    # ------------------------------------------------------------------

    def ingest(
        self,
        file_path: str | Path,
        category: str | None = None,
        subcategory: str | None = None,
        document_type: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        author: str | None = None,
        organization: str | None = None,
    ) -> NormalizedDocument:
        """Ingest a document: normalize it and store for learning.

        Accepts: .docx, .pdf, .doc, .html, .rtf
        Returns the NormalizedDocument.
        """
        file_path = Path(file_path)

        # Auto-detect attribution if user did not provide author/organization
        detected_author = author
        detected_org = organization
        if detected_author is None and detected_org is None:
            try:
                from anchor_ml_engine.attribution import AttributionDetector
                detector = AttributionDetector()
                attribution = detector.detect(file_path)
                if attribution.author:
                    detected_author = attribution.author
                if attribution.organization:
                    detected_org = attribution.organization
            except Exception:
                pass  # Attribution detection is best-effort

        # Normalize organization name via the firm database
        if detected_org and organization is None:
            try:
                from anchor_ml_engine.firm_database import FirmDatabase
                db = FirmDatabase()
                detected_org = db.normalize_name(detected_org)
            except Exception:
                pass  # Firm normalization is best-effort

        # User-provided values always override auto-detected ones
        final_author = author if author is not None else detected_author
        final_org = organization if organization is not None else detected_org

        # Normalize
        doc = normalize_document(
            str(file_path),
            category=category,
            subcategory=subcategory,
            document_type=document_type,
            author=final_author,
            organization=final_org,
        )

        # Store
        self._save_normalized(doc, tags=tags, notes=notes)

        return doc

    def ingest_batch(
        self,
        file_paths: list[str | Path],
        category: str | None = None,
        subcategory: str | None = None,
        document_type: str | None = None,
        tags: list[str] | None = None,
        author: str | None = None,
        organization: str | None = None,
    ) -> list[NormalizedDocument]:
        """Ingest multiple documents at once."""
        results = []
        for fp in file_paths:
            try:
                doc = self.ingest(
                    fp,
                    category=category,
                    subcategory=subcategory,
                    document_type=document_type,
                    tags=tags,
                    author=author,
                    organization=organization,
                )
                results.append(doc)
            except Exception:
                # Skip failed documents but don't stop batch
                continue
        return results

    def ingest_archive(
        self,
        archive_path: str | Path,
        category: str | None = None,
        subcategory: str | None = None,
        document_type: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        author: str | None = None,
        organization: str | None = None,
    ) -> dict:
        """Ingest all documents from an archive (ZIP, RAR, Adobe Portfolio).

        Extracts the archive, filters to supported document types, and
        ingests each one through the full normalization pipeline.

        Returns a summary dict with processed/failed counts and details.
        """
        from anchor_ml_engine.archive import (
            cleanup_extraction,
            extract_archive,
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
                        category=category,
                        subcategory=subcategory,
                        document_type=document_type,
                        tags=tags,
                        notes=notes,
                        author=author,
                        organization=organization,
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
        category: str | None = None,
        subcategory: str | None = None,
        document_type: str | None = None,
        tags: list[str] | None = None,
    ) -> LearnedFormat:
        """Learn formatting patterns from stored documents matching the filter.

        Returns a LearnedFormat with confidence-weighted patterns.
        """
        docs = self._load_matching(category, subcategory, document_type, tags)

        if not docs:
            return LearnedFormat(
                category=category,
                subcategory=subcategory,
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
        category: str | None = None,
        subcategory: str = "default",
        document_type: str = "document",
        tags: list[str] | None = None,
    ) -> dict:
        """Generate a suggested YAML-compatible ruleset from learned patterns."""
        learned = self.learn(category, subcategory, document_type, tags)
        return synthesize_ruleset(learned, category, subcategory, document_type)

    def recommend(
        self,
        category: str,
        existing_ruleset: dict,
        subcategory: str = "default",
        document_type: str = "document",
        tags: list[str] | None = None,
    ) -> list[dict]:
        """Compare learned patterns against existing ruleset and recommend changes.

        Returns a list of recommendation dicts.
        """
        # Learn patterns
        learned = self.learn(category, subcategory, document_type, tags)

        # Diff
        recs = diff_against_ruleset(learned, existing_ruleset)
        return [r.model_dump() for r in recs]

    # ------------------------------------------------------------------
    # Query stored documents
    # ------------------------------------------------------------------

    def list_documents(
        self,
        category: str | None = None,
        subcategory: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """List stored normalized documents matching a filter."""
        docs = self._load_matching(category, subcategory, tags=tags)
        return [
            {
                "id": d.id,
                "source_filename": d.source_filename,
                "source_format": d.source_format,
                "category": d.category,
                "subcategory": d.subcategory,
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
        categories: dict[str, int] = {}
        formats: dict[str, int] = {}
        for d in docs:
            cat = d.category or "untagged"
            categories[cat] = categories.get(cat, 0) + 1
            formats[d.source_format] = formats.get(d.source_format, 0) + 1

        return {
            "total_documents": len(docs),
            "by_category": categories,
            "by_format": formats,
        }

    # ------------------------------------------------------------------
    # Style profiles: author/organization preferences
    # ------------------------------------------------------------------

    def build_style_profile(
        self,
        profile_type: str,
        name: str,
        category: str | None = None,
    ) -> dict:
        """Build and save a style profile from all documents by an author/organization.

        Args:
            profile_type: "author" or "organization"
            name: Author name or organization name
            category: Optional filter to specific category

        Returns:
            The profile as a dict.
        """
        from anchor_ml_engine.style_profiles import (
            StyleProfileStore,
            build_style_profile,
        )

        # Load documents matching this author/organization
        all_records = self._load_all_records()
        matching = []
        for doc, record in all_records:
            attr = doc.author if profile_type == "author" else doc.organization
            if attr and attr.lower() == name.lower():
                if category and doc.category != category:
                    continue
                matching.append((doc, record))

        if not matching:
            return {"error": f"No documents found for {profile_type} '{name}'"}

        profile = build_style_profile(
            matching, profile_type, name, set(),
        )

        store = StyleProfileStore()
        store.save(profile)

        return profile.to_dict()

    def get_style_profile(
        self, profile_type: str, name: str,
    ) -> dict | None:
        """Load a saved style profile."""
        from anchor_ml_engine.style_profiles import StyleProfileStore
        store = StyleProfileStore()
        profile = store.load(profile_type, name)
        return profile.to_dict() if profile else None

    def list_style_profiles(self) -> list[dict]:
        """List all saved style profiles."""
        from anchor_ml_engine.style_profiles import StyleProfileStore
        store = StyleProfileStore()
        return [p.to_dict() for p in store.list_all()]

    def delete_style_profile(self, profile_type: str, name: str) -> bool:
        from anchor_ml_engine.style_profiles import StyleProfileStore
        store = StyleProfileStore()
        return store.delete(profile_type, name)

    # ------------------------------------------------------------------
    # Resolve format: apply the full hierarchy
    # ------------------------------------------------------------------

    def resolve_format(
        self,
        rules: dict,
        category: str | None = None,
        subcategory: str = "default",
        document_type: str = "document",
        author: str | None = None,
        organization: str | None = None,
    ) -> dict:
        """Resolve final formatting using the complete hierarchy:

        Rules > ML Learned > Style Profile > Defaults

        Args:
            rules: Mandatory rules dict (formatting decisions that cannot be overridden)

        Returns a dict with every formatting decision and its provenance.
        """
        from anchor_ml_engine.rule_hierarchy import resolve_format
        from anchor_ml_engine.style_profiles import StyleProfileStore

        # ML learned patterns (optional)
        learned = self.learn(category, subcategory, document_type)

        # Style profile (optional, prefer author over organization)
        style = None
        store = StyleProfileStore()
        if author:
            profile = store.load("author", author)
            if profile:
                style = profile
        if style is None and organization:
            profile = store.load("organization", organization)
            if profile:
                style = profile

        # Resolve through hierarchy
        resolved = resolve_format(rules, learned, style)
        return resolved.to_dict()

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

    def _load_all_records(self) -> list[tuple[NormalizedDocument, dict]]:
        """Load all stored documents with their full storage records."""
        results = []
        for f in self._store_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                doc_data = data.get("document", data)
                doc = NormalizedDocument.model_validate(doc_data)
                results.append((doc, data))
            except Exception:
                continue
        return results

    def _load_matching(
        self,
        category: str | None = None,
        subcategory: str | None = None,
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
                if category and doc.category != category:
                    continue
                if subcategory and doc.subcategory != subcategory:
                    continue
                if document_type and doc.document_type != document_type:
                    continue
                if tags and not any(t in stored_tags for t in tags):
                    continue

                all_docs.append(doc)
            except Exception:
                continue

        return all_docs
