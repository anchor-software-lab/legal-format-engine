.DEFAULT_GOAL := help
SHELL := /bin/bash

PYTHON ?= python
REPO_ROOT := $(shell pwd)

# Use uv when available — it handles the workspace cleanly. Falls back to
# the install-dev.sh script otherwise. Both end with the same installed
# state: editable workspace packages, third-party deps resolved, `lqg`
# on PATH.
UV := $(shell command -v uv 2>/dev/null)

##@ Setup

.PHONY: install
install: ## Install workspace editable (uv if present, else pip fallback)
ifeq ($(UV),)
	@./scripts/install-dev.sh
else
	@$(UV) sync
endif

.PHONY: install-pip
install-pip: ## Force the pip-only path even if uv is installed
	@./scripts/install-dev.sh

##@ Test & lint

.PHONY: test
test: ## Run the full test suite
	@$(PYTHON) -m pytest -q

.PHONY: test-verbose
test-verbose: ## Run tests with -v (per-test names)
	@$(PYTHON) -m pytest -v

.PHONY: test-package
test-package: ## Run one package's tests: make test-package P=legal_docx
	@$(PYTHON) -m pytest packages/$(P)/tests -v

##@ Code generation

.PHONY: schemas
schemas: ## Regenerate schemas/json-schema/*.schema.json from the Pydantic models
	@$(PYTHON) tools/codegen/export_json_schemas.py

##@ Demo

DEMO_DIR := $(REPO_ROOT)/.demo
DEMO_DOCX := $(DEMO_DIR)/brief.docx
DEMO_RULES := $(DEMO_DIR)/rules.yaml

$(DEMO_DIR):
	@mkdir -p $@

$(DEMO_DOCX): | $(DEMO_DIR)
	@$(PYTHON) -c "from legal_docx.testing import make_sample_brief; make_sample_brief('$(DEMO_DOCX)')"
	@echo "Wrote $(DEMO_DOCX)"

$(DEMO_RULES): | $(DEMO_DIR)
	@printf "page_format:\n  font_size_pt: 13.0\n  line_spacing: 2.0\n" > $(DEMO_RULES)
	@echo "Wrote $(DEMO_RULES)"

.PHONY: demo
demo: $(DEMO_DOCX) $(DEMO_RULES) ## Build a sample brief and run lqg check + lqg cites against it
	@echo
	@echo "=== lqg check ==="
	@lqg check $(DEMO_DOCX) --rules $(DEMO_RULES) || true
	@echo
	@echo "=== lqg cites ==="
	@lqg cites $(DEMO_DOCX)

.PHONY: demo-fix
demo-fix: $(DEMO_DOCX) $(DEMO_RULES) ## Demonstrate lqg fix: build, fix, re-check
	@echo "=== lqg fix ==="
	@lqg fix $(DEMO_DOCX) --rules $(DEMO_RULES) --out $(DEMO_DIR)/brief.fixed.docx
	@echo
	@echo "=== lqg check (post-fix) ==="
	@lqg check $(DEMO_DIR)/brief.fixed.docx --rules $(DEMO_RULES)

##@ Eval (LLM harness)

EVAL_DATASET ?= tools/eval/datasets/bluebook.normalize_case/smoke.jsonl
EVAL_PROMPT_ID ?= bluebook.normalize_case@v1
EVAL_MODELS ?= --model fake/canned-A --model fake/canned-B
EVAL_DB ?= tools/eval/results.duckdb
EVAL_CACHE ?= tools/eval/.cache
EVAL_ADVERSARIAL ?= /tmp/anchor-eval-adversarial.jsonl

# `make eval` runs the smoke dataset against the fake client by default.
# Use EVAL_MODE=real and provider env vars to hit real APIs.
EVAL_MODE ?= fake
EVAL_CLIENT_FLAG := $(if $(filter real,$(EVAL_MODE)),--real,--fake)

.PHONY: eval
eval: eval-smoke ## Alias for eval-smoke (15-case offline smoke run)

.PHONY: eval-smoke
eval-smoke: ## Run the smoke dataset; set EVAL_MODE=real to hit live providers
	@$(PYTHON) -m tools.eval.cli run \
		$(EVAL_DATASET) \
		--prompt-id $(EVAL_PROMPT_ID) \
		$(EVAL_MODELS) \
		--cache-dir $(EVAL_CACHE) \
		--db $(EVAL_DB) \
		$(EVAL_CLIENT_FLAG)

.PHONY: eval-calibrate
eval-calibrate: ## Run smoke dataset + print calibration (reliability) diagrams per model
	@$(PYTHON) -m tools.eval.cli calibration \
		$(EVAL_DATASET) \
		--prompt-id $(EVAL_PROMPT_ID) \
		$(EVAL_MODELS) \
		$(EVAL_CLIENT_FLAG)

.PHONY: eval-thresholds
eval-thresholds: ## Check absolute + regression thresholds against the latest run
	@$(PYTHON) -m tools.eval.cli thresholds-check \
		tools/eval/thresholds.yaml \
		--prompt-id $(EVAL_PROMPT_ID) \
		--db $(EVAL_DB)

.PHONY: eval-adversarial
eval-adversarial: ## Generate adversarial mutants from the smoke seed into $(EVAL_ADVERSARIAL)
	@$(PYTHON) -m tools.eval.cli generate-adversarial \
		$(EVAL_DATASET) \
		--out $(EVAL_ADVERSARIAL) \
		--per-case 5
	@echo "Wrote $(EVAL_ADVERSARIAL)"

.PHONY: eval-regression
eval-regression: eval-adversarial ## Run smoke + adversarial back-to-back (nightly-equivalent local run)
	@$(PYTHON) -m tools.eval.cli run \
		$(EVAL_DATASET) \
		--prompt-id $(EVAL_PROMPT_ID) \
		$(EVAL_MODELS) \
		--cache-dir $(EVAL_CACHE) \
		--db $(EVAL_DB) \
		$(EVAL_CLIENT_FLAG)
	@$(PYTHON) -m tools.eval.cli run \
		$(EVAL_ADVERSARIAL) \
		--prompt-id $(EVAL_PROMPT_ID) \
		$(EVAL_MODELS) \
		--cache-dir $(EVAL_CACHE) \
		--db $(EVAL_DB) \
		$(EVAL_CLIENT_FLAG)

.PHONY: eval-clean
eval-clean: ## Drop the eval response cache and the DuckDB results store
	@rm -rf $(EVAL_CACHE) $(EVAL_DB) $(EVAL_ADVERSARIAL)
	@echo "Removed $(EVAL_CACHE), $(EVAL_DB), and $(EVAL_ADVERSARIAL)"

##@ Corpus bootstrap (Wisconsin briefs)

CORPUS_CACHE      ?= tools/corpus/.cache
CORPUS_OUT        ?= tools/eval/datasets/bluebook.normalize_case/wi_corpus.jsonl
CORPUS_SESSION    ?= tools/corpus/.session
CORPUS_CANDIDATES ?= tools/corpus/.cache/candidates.jsonl
CORPUS_DISCOVERY  ?= tools/corpus/.cache/discovered.json
CORPUS_PDF        ?=
CORPUS_TEXT       ?=
CORPUS_COURT      ?= coa
CORPUS_MAX        ?= 25

.PHONY: corpus-discover
corpus-discover: ## Discover up to $(CORPUS_MAX) brief URLs from wicourts.gov
	@$(PYTHON) -m tools.corpus.cli discover \
		--out $(CORPUS_DISCOVERY) \
		--court $(CORPUS_COURT) \
		--max $(CORPUS_MAX) \
		--cache-dir $(CORPUS_CACHE)

.PHONY: corpus-download
corpus-download: ## Download every brief in $(CORPUS_DISCOVERY) into the cache
	@$(PYTHON) -m tools.corpus.cli download $(CORPUS_DISCOVERY) --cache-dir $(CORPUS_CACHE)

.PHONY: corpus-extract
corpus-extract: ## Extract candidate citations from a PDF: PDF=path/to/brief.pdf
	@if [ -z "$(CORPUS_PDF)" ]; then \
		echo "set CORPUS_PDF=path/to/brief.pdf (or use corpus-extract-text CORPUS_TEXT=path)"; exit 2; \
	fi
	@$(PYTHON) -m tools.corpus.cli extract $(CORPUS_PDF) \
		--out $(CORPUS_CANDIDATES) \
		--id-prefix $(notdir $(basename $(CORPUS_PDF)))

.PHONY: corpus-extract-text
corpus-extract-text: ## Extract candidates from a text file: CORPUS_TEXT=path/to/brief.txt
	@if [ -z "$(CORPUS_TEXT)" ]; then \
		echo "set CORPUS_TEXT=path/to/brief.txt"; exit 2; \
	fi
	@$(PYTHON) -m tools.corpus.cli extract $(CORPUS_TEXT) --text \
		--out $(CORPUS_CANDIDATES) \
		--id-prefix $(notdir $(basename $(CORPUS_TEXT)))

.PHONY: corpus-triage
corpus-triage: ## Interactive labeling loop with checkpoints in $(CORPUS_SESSION)
	@$(PYTHON) -m tools.corpus.cli triage $(CORPUS_CANDIDATES) \
		--out $(CORPUS_OUT) \
		--session-dir $(CORPUS_SESSION)

.PHONY: corpus-merge
corpus-merge: ## Merge labeled JSONLs: make corpus-merge INPUTS="a.jsonl b.jsonl" OUT=merged.jsonl
	@if [ -z "$(INPUTS)" ] || [ -z "$(OUT)" ]; then \
		echo "set INPUTS=\"a.jsonl b.jsonl\" OUT=merged.jsonl"; exit 2; \
	fi
	@$(PYTHON) -m tools.corpus.cli merge $(INPUTS) --out $(OUT)

.PHONY: corpus-clean
corpus-clean: ## Drop the corpus cache + session checkpoints
	@rm -rf $(CORPUS_CACHE) $(CORPUS_SESSION)
	@echo "Removed $(CORPUS_CACHE) and $(CORPUS_SESSION)"

##@ Housekeeping

.PHONY: clean
clean: eval-clean corpus-clean ## Remove __pycache__, .pytest_cache, build artifacts, demo + eval + corpus state
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf $(DEMO_DIR)
	@echo "Cleaned __pycache__, .pytest_cache, egg-info, .demo/"

##@ Help

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Anchor Quality Gate dev commands\n\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	     /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 } \
	     /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
