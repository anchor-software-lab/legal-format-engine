"""Bluebook citation parsing, normalization, validation.

v0 surface (planned):
- `parser.extract_citations(text) -> list[Citation]` (eyecite-backed)
- `bluebook.normalizer.normalize(citation) -> Citation`
- `bluebook.signal.classify(signal: str) -> SignalKind`
- `bluebook.short_form.resolve(citations) -> list[Citation]`
"""
