#!/usr/bin/env bash
# ============================================================================
# Agent Rewards — launcher
#
#   Simplest way to start the stdio MCP server once scripts/install.sh has
#   created the venv. Uses `exec` so the server inherits this process's stdout/
#   stderr and logs stream straight to the terminal (or the MCP client that
#   spawned it).
#
#   Usage:
#     scripts/run.sh                 # start the server (stdio)
#     PATH="..."; scripts/run.sh     # with additional env, e.g. db dir
#
#   Honour AGENT_REWARDS_DB_DIR if set, else default to ~/.agent-rewards.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PY="${REPO_DIR}/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "ERROR: no venv found at $REPO_DIR/.venv" >&2
  echo "       Run scripts/install.sh first to create it, then re-run this." >&2
  exit 1
fi

export AGENT_REWARDS_DB_DIR="${AGENT_REWARDS_DB_DIR:-$HOME/.agent-rewards}"

echo "Agent Rewards MCP (stdio) — db: $AGENT_REWARDS_DB_DIR" >&2
exec "$VENV_PY" -m agent_rewards.server
