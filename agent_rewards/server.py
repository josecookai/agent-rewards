"""Agent Rewards — MCP server (M1).

A stdio Model Context Protocol server exposing the core trace lifecycle:

  * find_trace   — discover local agent trace files (Claude Code / Codex / Hermes ...)
  * view_trace   — read a single trace, redacted by default, git-aware scoped
  * upload_trace — redact + register a trace in the local credits ledger
  * get_credits  — query the credits / trace ledger
  * scope_of     — report whether a path lives in an open-source repo (privacy gate)

Run standalone:
    python -m agent_rewards.server
Or install the package and use the `agent-rewards-mcp` console entry point.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from . import __version__
from . import collector, ledger, redact

MAX_VIEW_BYTES = 200_000          # cap single-trace reads returned to the model
DEFAULT_AGENTS = None             # None = scan every supported agent

mcp = FastMCP(
    "agent-rewards",
    instructions=(
        "Agent Rewards finds, redacts, and 'banks' your coding-agent traces. "
        "Use find_trace to list local session files, view_trace to inspect one "
        "(secrets/PII scrubbed), upload_trace to register it in your credits "
        "ledger, and get_credits to see your running balance."
    ),
)


@mcp.tool()
def find_trace(
    agents: list[str] | None = DEFAULT_AGENTS,
    limit: int = 20,
) -> dict:
    """List the most recent local coding-agent trace files.

    Args:
        agents: optional subset (e.g. ["claude", "codex"]); default scans all.
        limit: max traces to return (1..500).
    """
    traces = collector.find_trace(agents, limit=limit)
    return {
        "count": len(traces),
        "agents": sorted({t.agent for t in traces}),
        "traces": [t.to_dict() for t in traces],
    }


@mcp.tool()
def view_trace(path: str, redact_output: bool = True) -> dict:
    """Read a trace file, redacting secrets/PII before it reaches the model.

    Args:
        path: absolute path to a trace file (from find_trace).
        redact_output: scrub secrets/PII (default True — always leave True
            unless viewing your own throwaway scratch file).
    """
    if not os.path.isfile(path):
        return {"error": f"not a file: {path}"}
    size = os.path.getsize(path)
    if size > MAX_VIEW_BYTES:
        return {
            "error": "trace too large to inline",
            "path": path, "size_bytes": size,
            "hint": "use the local timeline viewer in the dashboard instead",
        }
    text = redact.redact_file(path)
    if text is None:
        return {"error": "unreadable or binary file", "path": path}
    repo = redact.detect_repo(path)
    return {
        "path": path,
        "size_bytes": size,
        "scope": repo.scope,
        "redacted": redact_output,
        "content": text if redact_output else _raw_read(path),
    }


@mcp.tool()
def upload_trace(path: str, agent: str | None = None) -> dict:
    """Redact + register a trace in the credits ledger (M1 local demo).

    Args:
        path: absolute path to a trace file.
        agent: agent label for the ledger (e.g. "claude"); inferred if omitted.
    """
    if not os.path.isfile(path):
        return {"error": f"not a file: {path}"}
    size = os.path.getsize(path)
    sha = ledger.sha256_file(path)
    trace_id = sha[:24]
    repo = redact.detect_repo(path)
    # Only register if it has a path worth sharing; scope surfaced for the gate.
    agent = agent or _infer_agent(path)
    return ledger.register(trace_id, agent or "unknown", path, size) | {
        "scope": repo.scope,
        "redacted": True,
    }


@mcp.tool()
def get_credits() -> dict:
    """Return your running credits balance and recently-registered traces."""
    return ledger.balance()


@mcp.tool()
def scope_of(path: str) -> dict:
    """Privacy gate: is this path inside an open-source (shareable) repo?

    Returns scope one of: 'open-source repo' | 'private repo' | 'unknown'.
    """
    repo = redact.detect_repo(path)
    return {
        "path": path,
        "scope": repo.scope,
        "remote": repo.remote,
        "sharable": repo.scope == "open-source repo",
    }


def _infer_agent(path: str) -> str | None:
    low = path.lower()
    for key in ("claude", "codex", "hermes", "grok", "openclaw"):
        if key in low:
            return key
    return None


def _raw_read(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(MAX_VIEW_BYTES)
    except OSError:
        return None


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
