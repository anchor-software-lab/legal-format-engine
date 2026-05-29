"""FastAPI SaaS surface.

v1 surface (planned):
- `main.app` — FastAPI application.
- `routes/runs.py` — `POST /v1/runs`, `GET /v1/runs/{id}`, …
- `security/envelope.py` — customer-managed envelope encryption.
- `workers/pipeline_worker.py` — RQ worker that drives the Pipeline.
"""
