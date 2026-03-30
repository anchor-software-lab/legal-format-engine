"""Tests for the style_profiles module."""

import pytest
from anchor_ml_engine.style_profiles import (
    DISCRETIONARY_FIELDS,
    StyleProfileStore,
    build_style_profile,
    _collect,
)
from anchor_ml_engine.models import (
    NormalizedDocument,
    NormalizedParagraphStyle,
    NormalizedSection,
    StylePreference,
    StyleProfile,
)


class TestDiscretionaryFields:
    def test_key_fields_present(self):
        assert "body_first_line_indent" in DISCRETIONARY_FIELDS
        assert "block_quote_left_indent" in DISCRETIONARY_FIELDS
        assert "footnote_font_size_pt" in DISCRETIONARY_FIELDS
        assert "heading_space_before_pt" in DISCRETIONARY_FIELDS

    def test_non_discretionary_fields_absent(self):
        # Font name and size are rule-governed, not discretionary
        assert "font_name" not in DISCRETIONARY_FIELDS
        assert "font_size_pt" not in DISCRETIONARY_FIELDS


class TestCollect:
    def test_collect_discretionary(self):
        values: dict[str, list] = {}
        _collect(values, "body_first_line_indent", 0.5, set())
        assert "body_first_line_indent" in values
        assert values["body_first_line_indent"] == [0.5]

    def test_collect_rule_governed_skipped(self):
        values: dict[str, list] = {}
        _collect(values, "body_first_line_indent", 0.5, {"body_first_line_indent"})
        assert "body_first_line_indent" not in values

    def test_collect_non_discretionary_skipped(self):
        values: dict[str, list] = {}
        _collect(values, "font_name", "Arial", set())
        assert "font_name" not in values

    def test_collect_none_skipped(self):
        values: dict[str, list] = {}
        _collect(values, "body_first_line_indent", None, set())
        assert "body_first_line_indent" not in values


class TestBuildStyleProfile:
    def test_build_from_documents(self):
        docs = []
        for i in range(4):
            doc = NormalizedDocument(
                id=f"doc_{i}",
                source_filename=f"doc_{i}.docx",
                source_format="docx",
                category="test_cat",
                paragraph_styles=[
                    NormalizedParagraphStyle(
                        context="body",
                        font_family="Times New Roman",
                        font_size_pt=12.0,
                        line_spacing=2.0,
                        first_line_indent=0.5,
                        alignment="justify",
                    ),
                ],
                sections=[
                    NormalizedSection(id="introduction", original_name="Introduction", order=0),
                ],
            )
            docs.append((doc, {}))

        profile = build_style_profile(docs, "author", "Test Author")
        assert profile.name == "Test Author"
        assert profile.profile_type == "author"
        assert profile.document_count == 4
        assert "test_cat" in profile.categories

        # Should have learned body_first_line_indent
        indent_pref = profile.get("body_first_line_indent")
        assert indent_pref is not None
        assert indent_pref.value == 0.5
        assert indent_pref.consistency == 1.0

    def test_inconsistent_values_excluded(self):
        """If consistency < 50%, preference should not be included."""
        docs = []
        for i in range(4):
            indent = 0.5 if i == 0 else float(i) * 0.3
            doc = NormalizedDocument(
                id=f"doc_{i}",
                source_filename=f"doc_{i}.docx",
                source_format="docx",
                paragraph_styles=[
                    NormalizedParagraphStyle(
                        context="body",
                        font_family="Times New Roman",
                        font_size_pt=12.0,
                        line_spacing=2.0,
                        first_line_indent=indent,
                    ),
                ],
            )
            docs.append((doc, {}))

        profile = build_style_profile(docs, "author", "Inconsistent")
        # With 4 different values, none should have > 50% consistency
        # (first value 0.5 appears once out of 4 = 25%)
        indent_pref = profile.get("body_first_line_indent")
        assert indent_pref is None


class TestStyleProfileStore:
    def test_save_and_load(self, tmp_path):
        store = StyleProfileStore(store_dir=tmp_path)
        profile = StyleProfile(
            profile_type="author",
            name="Jane Doe",
            document_count=3,
            preferences=[
                StylePreference(field="body_first_line_indent", value=0.5,
                                sample_count=3, consistency=0.9),
            ],
        )
        store.save(profile)

        loaded = store.load("author", "Jane Doe")
        assert loaded is not None
        assert loaded.name == "Jane Doe"
        assert len(loaded.preferences) == 1

    def test_list_all(self, tmp_path):
        store = StyleProfileStore(store_dir=tmp_path)
        for name in ["Alice", "Bob"]:
            store.save(StyleProfile(
                profile_type="author", name=name, document_count=1,
            ))
        all_profiles = store.list_all()
        assert len(all_profiles) == 2

    def test_delete(self, tmp_path):
        store = StyleProfileStore(store_dir=tmp_path)
        store.save(StyleProfile(
            profile_type="author", name="To Delete", document_count=1,
        ))
        assert store.delete("author", "To Delete") is True
        assert store.load("author", "To Delete") is None

    def test_load_nonexistent(self, tmp_path):
        store = StyleProfileStore(store_dir=tmp_path)
        assert store.load("author", "Nobody") is None


class TestStyleProfileModel:
    def test_to_dict_and_from_dict(self):
        profile = StyleProfile(
            profile_type="organization",
            name="Test Org",
            document_count=10,
            categories=["cat_a", "cat_b"],
            preferences=[
                StylePreference(field="body_first_line_indent", value=0.5,
                                sample_count=10, consistency=0.95),
            ],
        )
        d = profile.to_dict()
        restored = StyleProfile.from_dict(d)
        assert restored.name == "Test Org"
        assert restored.document_count == 10
        assert len(restored.preferences) == 1
        assert restored.preferences[0].value == 0.5

    def test_get_preference(self):
        profile = StyleProfile(
            profile_type="author", name="Test",
            preferences=[
                StylePreference(field="a", value=1),
                StylePreference(field="b", value=2),
            ],
        )
        assert profile.get("a").value == 1
        assert profile.get("b").value == 2
        assert profile.get("c") is None
