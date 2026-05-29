"""Per-firm style guides + user preferences + correction history.

v2 surface (planned):
- `store.StyleGuideStore` — CRUD over Postgres (cloud) or SQLite (local).
- `feedback.record_acceptance(finding, action)` — close the loop on
  user-accepted vs rejected suggestions.
- `models.StyleGuide`, `UserPreferences`, `CorrectionRecord`.
"""
