"""Legal authority lookup + good-law tracking.

v1 surface (planned):
- `courtlistener.CourtListenerClient` — REST client + caching.
- `cap.CAPClient` — Caselaw Access Project client.
- `good_law.compute_status(authority_id)` — citator graph CTE.
- `models.Authority`, `Treatment`, `CitatorEdge`.
"""
