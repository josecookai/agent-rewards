#!/usr/bin/env bash
# ============================================================================
# Agent Rewards — one-click installer (Beta gate B0, item #1)
#
#   Auto-detects which coding agents are present on this machine, creates a
#   dedicated Python venv, installs the `agent_rewards` package, writes the
#   MCP client config for each detected agent, and verifies the stdio MCP
#   server actually boots (a quick JSON-RPC handshake).
#
#   No Python/venv knowledge required. Idempotent: safe to re-run.
#
#   Usage:
#     scripts/install.sh [--agents claude,hermes] [--db DIR] [--skip-config]
#     scripts/install.sh --help
#
#   Options:
#     --agents LIST   Comma-separated subset of: claude,codex,hermes,grok,openclaw
#                     Default: auto-detect whatever is installed on this machine.
#     --db DIR        Directory for the credits ledger (AGENT_REWARDS_DB_DIR).
#                     Default: ~/.agent-rewards
#     --skip-config   Install + verify the server but DO NOT write any MCP config.
#     --help, -h      Show this help and exit.
# ============================================================================
set -euo pipefail

# ---- resolvable paths -------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"          # repo root (parent of scripts/)
VENV_DIR="${REPO_DIR}/.venv"                      # dedicated virtualenv
VENV_PY="$VENV_DIR/bin/python"
DB_DIR="${AGENT_REWARDS_DB_DIR:-$HOME/.agent-rewards}"

# ---- supported agents (mirrors agent_rewards/collector.py AGENT_DIRS) -------
# name -> base dir under $HOME whose presence indicates the agent is installed
declare -A AGENT_BASE_DIRS=(
  [claude]=".claude"
  [codex]=".codex"
  [hermes]=".hermes"
  [grok]=".grok"
  [openclaw]=".openclaw"
)

echo "==> Agent Rewards installer"
echo "    repo : $REPO_DIR"
echo "    venv : $VENV_DIR"
echo "    db   : $DB_DIR"

# ---- --help -----------------------------------------------------------------
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  sed -n '2,27p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
fi

# ---- platform gate: macOS/Linux fine, Windows => point at WSL ----------------
case "$(uname -s)" in
  Linux|Darwin) : ;;
  MINGW*|MSYS*|CYGWIN*|Windows*)
    echo "ERROR: Agent Rewards targets macOS/Linux (the trace paths are $HOME-based)." >&2
    echo "       Please run this inside WSL (Windows Subsystem for Linux) and re-run." >&2
    exit 1
    ;;
  *)
    echo "WARN: unknown OS '$(uname -s)'; continuing, but paths may not resolve." >&2
    ;;
esac

# ---- arg parsing (simple, ordered) ------------------------------------------
SELECTED=()
SKIP_CONFIG=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --agents)
      # comma-separated; validate against the known set
      IFS=',' read -r -a raw <<< "$2"; shift 2
      for a in "${raw[@]}"; do
        [[ -n "${AGENT_BASE_DIRS[$a]:-}" ]] && SELECTED+=("$a") \
          || echo "WARN: ignoring unknown agent '$a' (known: ${!AGENT_BASE_DIRS[*]})" >&2
      done
      ;;
    --db)
      DB_DIR="$2"; shift 2
      ;;
    --skip-config)
      SKIP_CONFIG=1; shift
      ;;
    --help|-h)
      sed -n '2,27p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0
      ;;
    *)
      echo "ERROR: unknown option '$1' (try --help)" >&2; exit 1
      ;;
  esac
done

# ---- agent auto-detection ----------------------------------------------------
if [[ ${#SELECTED[@]} -eq 0 ]]; then
  for name in claude codex hermes grok openclaw; do
    if [[ -d "$HOME/${AGENT_BASE_DIRS[$name]}" ]]; then
      SELECTED+=("$name")
      echo "    detect: $name  ($HOME/${AGENT_BASE_DIRS[$name]})"
    fi
  done
  if [[ ${#SELECTED[@]} -eq 0 ]]; then
    echo "    detect: no supported coding agents found (claude/codex/hermes/grok/openclaw)."
    echo "            Proceeding with install + server verification only."
    echo "            Tip: pass --agents claude,codex to force configure specific agents."
  fi
else
  echo "    agents (explicit): ${SELECTED[*]}"
fi

# ---- create the virtualenv (idempotent) -------------------------------------
if [[ ! -x "$VENV_PY" ]]; then
  echo "==> Creating Python venv at $VENV_DIR …"
  python3 -m venv "$VENV_DIR"
else
  echo "==> Reusing existing venv at $VENV_DIR (idempotent)."
fi

# -----------------------------------------------------------------------------
# Install the package. Prefer the venv's pip; if it's missing/broken, fall back
# to `uv` (which manages its own env and is a single binary).
# -----------------------------------------------------------------------------
install_with_pip() {
  "$VENV_PY" -m pip install --disable-pip-version-check --quiet --upgrade pip
  # Pin mcp<2: the current project code uses the v1 FastMCP API
  # (mcp.server.fastmcp), which was renamed/removed in mcp 2.x. This keeps the
  # server importable until the package migrates to the mcp 2.x API.
  "$VENV_PY" -m pip install --disable-pip-version-check --quiet "mcp>=1.0.0,<2"
  "$VENV_PY" -m pip install --disable-pip-version-check --editable "$REPO_DIR"
}

install_with_uv() {
  if command -v uv >/dev/null 2>&1; then
    echo "    (falling back to uv)"
    # --python points uv at our venv so the entry point lands in VENV_DIR
    uv pip install --python "$VENV_PY" "mcp>=1.0.0,<2"
    uv pip install --python "$VENV_PY" --editable "$REPO_DIR"
  else
    echo "ERROR: no working pip in the venv and no 'uv' on PATH." >&2
    echo "       Install uv (https://docs.astral.sh/uv/) or ensure python3-pip/venv." >&2
    exit 1
  fi
}

echo "==> Installing agent-rewards into $VENV_DIR …"
if install_with_pip; then
  :
elif install_with_uv; then
  :
else
  echo "ERROR: package install failed (tried pip, then uv)." >&2
  exit 1
fi

# -----------------------------------------------------------------------------
# Write MCP client config for each detected agent (unless --skip-config).
# -----------------------------------------------------------------------------
if [[ $SKIP_CONFIG -eq 1 || ${#SELECTED[@]} -eq 0 ]]; then
  if [[ $SKIP_CONFIG -eq 1 ]]; then
    echo "==> --skip-config: skipping MCP config writes."
  fi
else
  echo "==> Writing MCP configs …"
  for agent in "${SELECTED[@]}"; do
    case "$agent" in
      claude)
        # ~/.claude/.mcp.json  (JSON — merged safely with python)
        if [[ -d "$HOME/.claude" ]]; then
          echo "    claude -> ~/.claude/.mcp.json"
          AGENT_REWARDS_DB_DIR="$DB_DIR" VENV_PY="$VENV_PY" \
            python3 - "$VENV_PY" "$DB_DIR" <<'PY'
import json, os, sys
venv_py, db = sys.argv[1], sys.argv[2]
path = os.path.expanduser("~/.claude/.mcp.json")
cfg = {}
if os.path.exists(path):
    try:
        cfg = json.load(open(path))
    except Exception:
        cfg = {}
servers = cfg.setdefault("mcpServers", {})
servers["agent_rewards"] = {
    "command": venv_py,
    "args": ["-m", "agent_rewards.server"],
    "env": {"AGENT_REWARDS_DB_DIR": db},
}
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PY
        else
          echo "    claude selected but ~/.claude missing — skipping config."
        fi
        ;;

      hermes)
        # ~/.hermes/config.yaml  (YAML — insert the mcp_servers entry via python)
        if [[ -f "$HOME/.hermes/config.yaml" ]]; then
          # Always print the snippet (readable + verified); then try to merge it in.
          echo "    hermes -> MCP snippet (~/.hermes/config.yaml):"
          cat <<EOF
  agent_rewards:
    command: "$VENV_PY"
    args: ["-m", "agent_rewards.server"]
    env:
      AGENT_REWARDS_DB_DIR: "$DB_DIR"
EOF
          AGENT_REWARDS_DB_DIR="$DB_DIR" VENV_PY="$VENV_PY" \
            python3 - "$VENV_PY" "$DB_DIR" <<'PY'
import os, re, sys
venv_py, db = sys.argv[1], sys.argv[2]
path = os.path.expanduser("~/.hermes/config.yaml")
with open(path) as f:
    lines = f.read().splitlines(keepends=True)
out = []
inserted = False
# Only insert if the `mcp_servers:` block exists and does NOT already contain agent_rewards.
block_start = None
for i, ln in enumerate(lines):
    if re.match(r"^mcp_servers:\s*(#.*)?$", ln):
        block_start = i
        break
already = any(re.match(r"^\s+agent_rewards:", ln) for ln in lines[block_start+1:] if block_start is not None and (ln.startswith(" ") or ln.strip()==""))
if block_start is not None and not already:
    block = (
        f"  agent_rewards:\n"
        f'    command: "{venv_py}"\n'
        f'    args: ["-m", "agent_rewards.server"]\n'
        f"    env:\n"
        f"      AGENT_REWARDS_DB_DIR: \"{db}\"\n"
    )
    # insert immediately after the mcp_servers: line, preserving indentation context
    out = lines[:block_start+1] + [block] + lines[block_start+1:]
    inserted = True
else:
    out = lines
    if block_start is None:
        print("WARN: no 'mcp_servers:' block found in config.yaml — snippet printed above, add it manually.", file=sys.stderr)
with open(path, "w") as f:
    f.writelines(out)
print(("    (inserted into config.yaml)" if inserted else "    (agent_rewards already present or no mcp_servers block)"))
PY
        else
          echo "    hermes selected but ~/.hermes/config.yaml missing — skipping."
        fi
        ;;

      codex)
        # ~/.codex/config.toml  (TOML — append an mcp_servers.agent_rewards table)
        if [[ -d "$HOME/.codex" ]]; then
          echo "    codex -> ~/.codex/config.toml"
          python3 - "$VENV_PY" "$DB_DIR" <<PY
import os, sys
venv_py, db = sys.argv[1], sys.argv[2]
path = os.path.expanduser("~/.codex/config.toml")
block = (
    "\n[mcp_servers.agent_rewards]\n"
    f'command = "{venv_py}"\n'
    'args = ["-m", "agent_rewards.server"]\n'
    f'env = {{"AGENT_REWARDS_DB_DIR" = "{db}"}}\n'
)
body = ""
if os.path.exists(path):
    with open(path) as f:
        body = f.read()
    if "[mcp_servers.agent_rewards]" in body:
        print("    (agent_rewards mcp_servers already present in config.toml)")
        raise SystemExit
with open(path, "a") as f:
    f.write(block)
print("    (appended mcp_servers.agent_rewards)")
PY
        else
          echo "    codex selected but ~/.codex missing — skipping config."
        fi
        ;;

      grok|openclaw)
        echo "    $agent -> no standard MCP config file yet (skill install pending in M2); install + verify still done."
        ;;

      *)
        echo "    WARN: no config writer for '$agent' yet." >&2
        ;;
    esac
  done
fi

# -----------------------------------------------------------------------------
# Verify the stdio MCP server actually boots.
#   We push a JSON-RPC initialize request on stdin and check stdout carries the
#   server's name response ("agent-rewards"). The timeout guards a hang.
# -----------------------------------------------------------------------------
echo "==> Verifying Agent Rewards MCP server starts …"
INIT_PAYLOAD='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"ar-install","version":"0.0.0"}}}'
HEALTH_LOG="$(mktemp)"
set +e
AGENT_REWARDS_DB_DIR="$DB_DIR" timeout 20 "$VENV_PY" -m agent_rewards.server \
    < <(printf '%s\n' "$INIT_PAYLOAD") >"$HEALTH_LOG" 2>&1
rc=$?
set -e
# A healthy server replies to `initialize` with serverInfo.name "agent-rewards".
# Detect crash output (import errors / tracebacks) and treat those as failure,
# even if a stray path happened to contain the token "agent-rewards".
if [[ $rc -eq 0 ]] \
  && grep -q '"name":"agent-rewards"' "$HEALTH_LOG" \
  && ! grep -Eq 'Traceback|ModuleNotFoundError|ImportError' "$HEALTH_LOG"; then
  echo "    OK: server answered the stdio initialize handshake."
else
  echo "ERROR: server did not respond to the MCP handshake." >&2
  echo "       (exit=$rc) Output was:" >&2
  sed 's/^/    /' "$HEALTH_LOG" >&2 || true
  echo "    Note: if you see 'ModuleNotFoundError: mcp.server.fastmcp', the venv has mcp 2.x;" >&2
  echo "    re-run this installer (it pins mcp<2) or run: $VENV_PY -m pip install 'mcp<2'" >&2
  rm -f "$HEALTH_LOG"
  exit 1
fi
rm -f "$HEALTH_LOG"

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo
echo "✅ Agent Rewards MCP ready"
echo "    venv      : $VENV_DIR"
echo "    run       : $VENV_PY -m agent_rewards.server   (or scripts/run.sh)"
echo "    db dir    : $DB_DIR"
if [[ $SKIP_CONFIG -eq 0 ]]; then
  echo "    configs   : ${SELECTED[*]:-none detected (use --agents to force)}"
fi
echo "    Restart your MCP client (or reload config) to pick up the new server."
echo "    Uninstall : scripts/uninstall.sh"
