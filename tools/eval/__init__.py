"""LLM eval harness for the Anchor Quality Gate.

Production tier per the design discussion:

- Programmatic scoring (exact match, field match, schema validity) for
  the cheap and deterministic signal.
- Bluebook-aware fuzzy scoring (T.6 reporter equivalence, whitespace,
  italic markup) for the domain-specific gates.
- LLM-as-judge with a calibrated rubric for nuanced cases that
  programmatic match flags as different but might be equivalent.
- Calibration measurement (reliability diagrams) so we know whether
  the LLM's reported confidence actually predicts correctness.
- Adversarial dataset generation from clean cites by structured
  perturbation, so the corpus expands faster than human labeling can.
- Response cache keyed by (prompt_id, model, input_hash) — dev loops
  cost nothing once cached; PR CI re-runs cost only the diff.
- DuckDB-backed historical store with per-prompt thresholds so CI can
  catch regressions (>2pp accuracy drop / >10% cost rise / >X p95
  latency rise) before merge.
- Three tiers — smoke (~30 cases, runs on every PR), regression
  (200-500, nightly), full (1k+, weekly + on-demand).

Layout:

    tools/eval/
    ├── types.py            domain types (EvalCase, CaseResult, RunReport)
    ├── dataset.py          JSONL load + iterate
    ├── cache.py            (prompt_id, model, input_hash) → response
    ├── runner.py           async fan-out across models + scorers
    ├── store.py            DuckDB schema + read/write
    ├── reporter.py         Rich tables + calibration plots
    ├── calibration.py      reliability buckets
    ├── adversarial.py      programmatic perturbation generator
    ├── thresholds.py       per-prompt threshold loader + check
    ├── cli.py              `python -m tools.eval.cli ...`
    ├── scorers/
    │   ├── base.py         Scorer Protocol
    │   ├── programmatic.py exact_match, field_match, schema_valid
    │   ├── bluebook.py     BluebookFuzzy
    │   └── judge.py        LLMJudge wrapping our LLMClient
    ├── prompts/
    │   └── judge.bluebook_normalize.md
    ├── datasets/
    │   └── bluebook.normalize_case/
    │       ├── smoke.jsonl
    │       ├── regression.jsonl
    │       └── adversarial.jsonl
    └── thresholds.yaml
"""
