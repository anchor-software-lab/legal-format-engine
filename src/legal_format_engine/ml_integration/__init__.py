"""ML integration: consumes format-only patterns from anchor-ml-engine.

This module is the ONLY entry point for ML-derived data into the legal
format engine. It imports format specifications (typography, layout,
headings, sections) and NEVER handles raw document content.

Data flow:
    anchor-ml-engine (private)
        -> format_export.export_learned_format()
        -> JSON file with format-only data
        -> this module loads it and applies it below mandatory rules
"""
