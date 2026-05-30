#!/usr/bin/env bash
# Install the Anchor Quality Gate workspace in editable mode without uv.
#
# Usage:
#   scripts/install-dev.sh           # install everything + runtime deps
#   scripts/install-dev.sh --no-deps # workspace packages only (CI: deps cached)
#
# Prefer `uv sync` from the repo root if you have uv — that's the canonical
# path and handles the workspace cleanly. This script exists for environments
# where uv isn't available (vendor laptops, CI shells, quick demos).

set -euo pipefail

PYTHON="${PYTHON:-python}"
PIP_FLAGS=()

# Resolve the repo root from this script's location so the command works
# from any cwd.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Workspace packages in dependency order. `legal_quality_gate` first
# because everything else depends on its types; CLI last because it
# pulls in every other package.
PACKAGES=(
    legal_quality_gate
    legal_format_engine
    legal_docx
    legal_citations
    legal_llm_gateway
    legal_authority
    legal_style_memory
    legal_authority_scraper
    legal_skill_kit
    legal_api
    legal_cli
)

# Runtime + dev third-party deps used across the workspace. uv would
# discover these from each package's pyproject; we just install the
# union here so editable installs work with --no-deps.
THIRD_PARTY=(
    "pydantic>=2.0,<3"
    "pyyaml>=6.0,<7"
    "python-docx>=1.1.0"
    "lxml>=5.0"
    "eyecite>=2.6"
    "typer>=0.12"
    "rich>=13.7"
    "pytest"
)

echo "==> Installing third-party runtime deps"
"$PYTHON" -m pip install -q "${THIRD_PARTY[@]}"

echo "==> Installing workspace packages editable (--no-deps; resolved above)"
for pkg in "${PACKAGES[@]}"; do
    echo "    - $pkg"
    "$PYTHON" -m pip install -q -e "./packages/$pkg" --no-deps
done

echo "==> Sanity check: which lqg"
which lqg || {
    echo "    ! lqg not on PATH (entry point not installed?)" >&2
    exit 1
}

echo "==> Done. Try:"
echo "      lqg --help"
echo "      pytest"
