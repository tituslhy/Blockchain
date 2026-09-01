#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the blockchain course repo.
# uv provisions the pinned Python 3.13 toolchain and installs the locked deps.
set -euo pipefail

# uv may already be on PATH from the base image; otherwise pull it into the
# well-known per-user bin dir and make it visible for the rest of this script.
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# Provision the interpreter pinned by .python-version and install the exact
# locked dependency set. --frozen fails loudly if uv.lock is out of date
# instead of silently rewriting it.
uv python install
uv sync --frozen
