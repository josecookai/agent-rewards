#!/usr/bin/env bash
# ============================================================================
# Agent Rewards — uninstaller
#
#   Safely removes only the things scripts/install.sh created:
#     * the repo-local venv      ( <repo>/.venv )
#     * the ~/.claude/.mcp.json  entry for agent_rewards
#     * the ~/.hermes/config.yaml agent_rewards mcp_servers entry
#     * the ~/.codex/config.toml mcp_servers.agent_rewards table
#
#   It does NOT delete the credits ledger (~/.agent-rewards) unless you pass
#   --purge-db. It never touches files it didn't create.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${REPO_DIR}/.venv"
PURGE_DB=0

for a in "$@"; do
  case "$a" in
    --purge-db) PURGE_DB=1 ;;
    --help|-h)
      sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      echo "Options:"
      echo "  --purge-db   also delete the credits ledger dir (~/.agent-rewards)"
      exit 0
      ;;
    *) echo "ERROR: unknown option '$a' (try --help)" >&2; exit 1 ;;
  esac
done

echo "==> Agent Rewards uninstaller"

# 1) repo-local venv
if [[ -d "$VENV_DIR" ]]; then
  echo "    removing venv: $VENV_DIR"
  rm -rf "$VENV_DIR"
else
  echo "    no venv at $VENV_DIR — nothing to remove."
fi

# 2) Claude Code ~/.claude/.mcp.json — remove the agent_rewards server entry
if [[ -f "$HOME/.claude/.mcp.json" ]]; then
  echo "    removing agent_rewards from ~/.claude/.mcp.json"
  python3 - <<'PY'
import json, os
path = os.path.expanduser("~/.claude/.mcp.json")
try:
    cfg = json.load(open(path))
except Exception:
    print("    WARN: could not parse ~/.claude/.mcp.json; leaving it untouched.")
    raise SystemExit
servers = cfg.get("mcpServers", {})
if "agent_rewards" in servers:
    del servers["agent_rewards"]
    if not servers:
        cfg.pop("mcpServers", None)
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    print("    removed agent_rewards from ~/.claude/.mcp.json")
else:
    print("    agent_rewards not in ~/.claude/.mcp.json")
PY
fi

# 3) Hermes ~/.hermes/config.yaml — remove the agent_rewards mcp_servers entry
if [[ -f "$HOME/.hermes/config.yaml" ]]; then
  echo "    removing agent_rewards from ~/.hermes/config.yaml"
  python3 - <<'PY'
import os, re
path = os.path.expanduser("~/.hermes/config.yaml")
with open(path) as f:
    lines = f.read().splitlines(keepends=True)
# remove the contiguous block: line `  agent_rewards:` through the next top-level
# key (a line not starting with a space) or end of file.
out, i, removed = [], 0, False
while i < len(lines):
    if re.match(r"^  agent_rewards:\s*(#.*)?$", lines[i]):
        i += 1
        while i < len(lines) and (lines[i].startswith(" ") and lines[i].strip() != ""):
            i += 1
        removed = True
        continue
    out.append(lines[i]); i += 1
with open(path, "w") as f:
    f.writelines(out)
print(("    removed agent_rewards block" if removed else "    agent_rewards not in ~/.hermes/config.yaml"))
PY
fi

# 4) Codex ~/.codex/config.toml — remove the mcp_servers.agent_rewards table
if [[ -f "$HOME/.codex/config.toml" ]]; then
  echo "    removing mcp_servers.agent_rewards from ~/.codex/config.toml"
  python3 - <<'PY'
import os, re
path = os.path.expanduser("~/.codex/config.toml")
with open(path) as f:
    txt = f.read()
# remove the [mcp_servers.agent_rewards] table: drop the header line and every
# following line up to the next top-level "[...]" table header or EOF. Tolerates
# both indented and unindented key=value entries.
lines = txt.splitlines(keepends=True)
out, i, removed = [], 0, False
while i < len(lines):
    ln = lines[i]
    if re.match(r"^\[mcp_servers\.agent_rewards\]\s*$", ln):
        removed = True
        i += 1
        while i < len(lines) and not lines[i].lstrip().startswith("["):
            i += 1
        continue
    out.append(ln); i += 1
with open(path, "w") as f:
    f.writelines(out)
print(("    removed mcp_servers.agent_rewards" if removed else "    agent_rewards not in ~/.codex/config.toml"))
PY
fi

# 5) optional ledger purge
if [[ $PURGE_DB -eq 1 ]]; then
  if [[ -d "$HOME/.agent-rewards" ]]; then
    echo "    removing ledger: $HOME/.agent-rewards"
    rm -rf "$HOME/.agent-rewards"
  else
    echo "    no ledger at ~/.agent-rewards to purge."
  fi
fi

echo "✅ Agent Rewards uninstalled."
