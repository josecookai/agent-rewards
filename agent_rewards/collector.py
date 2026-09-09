"""Agent Rewards — trace discovery (find_trace).

Cross-platform scan of supported coding agents' local session directories for
trace files (JSONL used by Claude Code / Codex / Hermes, etc).

Each agent maps to a glob over its session dir. Scans are bounded (by count and
recency) and never follow symlinks out of the tree.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path

# agent -> list of (glob, label) under $HOME. Labels help identify the file kind.
AGENT_DIRS: dict[str, list[tuple[str, str]]] = {
    "claude": [
        (".claude/projects/**/*.jsonl", "session"),
    ],
    "codex": [
        (".codex/sessions/**/rollout-*.jsonl", "rollout"),
    ],
    "hermes": [
        (".hermes/sessions/**/*.jsonl", "session"),
    ],
    "grok": [
        (".grok/**/*.jsonl", "session"),
    ],
    "openclaw": [
        (".openclaw/**/*.jsonl", "session"),
    ],
}

# extensions that are candidate trace containers
_TRACE_EXT = {".jsonl", ".json", ".ndjson"}


@dataclass(frozen=True)
class Trace:
    path: str
    agent: str
    size_bytes: int
    mtime: float
    kind: str

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "agent": self.agent,
            "size_bytes": self.size_bytes,
            "mtime": round(self.mtime, 2),
            "kind": self.kind,
        }


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def scan_agents(agents: list[str] | None = None, home: str | os.PathLike | None = None) -> list[Trace]:
    """Discover trace files across supported agents.

    Args:
        agents: subset of agent keys to scan; None = all supported agents.
        home: base directory to scan (defaults to $HOME); injectable in tests.
    """
    keys = agents or list(AGENT_DIRS)
    home = _home() if home is None else Path(home)
    found: list[Trace] = []
    for agent in keys:
        patterns = AGENT_DIRS.get(agent, [])
        for pat, kind in patterns:
            full = str(home / pat)
            # recursive=True handles the ** globs portably
            for match in glob.glob(full, recursive=True):
                if not os.path.isfile(match):
                    continue
                if os.path.splitext(match)[1].lower() not in _TRACE_EXT:
                    continue
                try:
                    st = os.stat(match)
                except OSError:
                    continue
                found.append(Trace(
                    path=match, agent=agent, size_bytes=st.st_size,
                    mtime=st.st_mtime, kind=kind,
                ))
    found.sort(key=lambda t: t.mtime, reverse=True)
    return found


def find_trace(agents: list[str] | None = None, limit: int = 20) -> list[Trace]:
    """Public entrypoint for the MCP tool: newest-first, capped at `limit`."""
    traces = scan_agents(agents)
    return traces[: max(1, min(limit, 500))]
