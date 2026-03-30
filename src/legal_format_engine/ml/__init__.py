"""Machine learning pipeline for legal document formatting.

This package provides:
- normalizer: Converts any document format to a canonical representation
- features: Extracts numerical/categorical feature vectors from normalized docs
- learner: Statistical pattern learning with outlier rejection
- synthesizer: Generates formatting specifications from learned patterns
- attribution: Auto-detect author/firm from uploaded documents
- firm_database: Reference database of law firms with fuzzy matching
- archive: Extract documents from ZIP, RAR, and Adobe Portfolio archives
- styles: Per-author/firm style profiles
- rule_hierarchy: Court rules > ML learned > style profiles > defaults
"""
