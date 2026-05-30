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

##@ Housekeeping

.PHONY: clean
clean: ## Remove __pycache__, .pytest_cache, build artifacts, and demo files
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
