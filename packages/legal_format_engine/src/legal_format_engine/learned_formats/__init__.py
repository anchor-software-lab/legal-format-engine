"""Learned formats: storage for ML-exported format specifications.

JSON files in this directory are produced by the anchor-ml-engine's
format_export module and contain ONLY formatting metadata (fonts, margins,
headings, spacing). They never contain document content.

To import a new format spec from the ML engine:

    # In the ML engine repo (private):
    from anchor_ml_engine import MLPipeline, export_learned_format
    pipeline = MLPipeline()
    learned = pipeline.learn(category="appellate", subcategory="wisconsin_court_of_appeals")
    export_learned_format(learned, "appellate_wisconsin_coa.json")

    # Copy the JSON file here (learned_formats/)
    # Then in the legal format engine:
    from legal_format_engine import load_format_spec, merge_with_rules
    spec = load_format_spec("learned_formats/appellate_wisconsin_coa.json")
    resolved = merge_with_rules(mandatory_rules, ml_spec=spec)
"""
