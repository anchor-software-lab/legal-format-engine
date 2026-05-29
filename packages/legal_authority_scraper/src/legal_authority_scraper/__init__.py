"""Backend scraper for WI and federal legal authority.

v2 surface (planned):
- `wicourts.WICourtsScraper` — WI Supreme Court + Court of Appeals
  opinions from wicourts.gov.
- `courtlistener.bulk_ingest` — bulk pull federal authority.
- `cornell_lii.statutes_ingest` — USC chapters.
- `scheduler.run_crawl_cycle()` — RQ job entry point.
"""
