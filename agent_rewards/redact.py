"""Agent Rewards — redaction layer.

Local, git-aware, secret/PII scrubber that runs BEFORE anything leaves the machine.
Kept deliberately dependency-free (stdlib regex) so it runs anywhere.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

# Order matters: longer / more specific patterns first so prefixes don't shadow.
_PATTERNS: list[tuple[str, str]] = [
    (r"(sk-[A-Za-z0-9_-]{12,})", "<SK>"),
    (r"(sk-[A-Za-z0-9_-]{20,})", "<SK>"),          # OpenAI-style
    (r"(gh[pousr]_[A-Za-z0-9]{20,})", "<GH_TOKEN>"),
    (r"(AKIA[0-9A-Z]{16})", "<AWS_KEY>"),
    (r"((?s:-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----))", "<PRIVKEY>",),
    (r"((?i:bearer)\s+[A-Za-z0-9._~+/=-]+)", "<BEARER>"),
    (r"((?i:api[_-]?key)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9._-]{8,})", "<API_KEY>"),
    (r"((?i:password)[\"']?\s*[:=]\s*[\"']?[^\s\"']{4,})", "<PASSWORD>"),
    (r"((?i:secret)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9._-]{6,})", "<SECRET>"),
    (r"(xox[baprs]-[A-Za-z0-9-]{8,})", "<SLACK_TOKEN>"),  # slack tokens
]
_SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".zip", ".gz", ".sqlite", ".db"}


def is_binary(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    if ext in _SKIP_EXT:
        return True
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(8000)
    except OSError:
        return True


def redact_text(text: str) -> str:
    out = text
    for pat, mask in _PATTERNS:
        out = re.sub(pat, mask, out)
    return out


@dataclass
class RepoInfo:
    is_repo: bool = False
    remote: str | None = None

    @property
    def scope(self) -> str:
        """open-source-only default: public remote ⇒ safe to share."""
        if not self.is_repo:
            return "unknown"
        if self.remote:
            return "open-source repo"  # public remote; refined in M2
        return "private repo"          # no remote ⇒ treat as private (opt-in only)


def detect_repo(path: str) -> RepoInfo:
    """Walk up from path to find a git root + remote origin URL (public ⇒ open)."""
    cur = os.path.abspath(path)
    if os.path.isfile(cur):
        cur = os.path.dirname(cur)
    while True:
        git = os.path.join(cur, ".git")
        if os.path.isdir(git) or os.path.isfile(git):
            remote = _git_remote(cur)
            return RepoInfo(is_repo=True, remote=remote)
        parent = os.path.dirname(cur)
        if parent == cur:
            return RepoInfo(is_repo=False)
        cur = parent


def _git_remote(repo_root: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", repo_root, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        out = r.stdout.strip()
        return out or None
    except Exception:
        return None


def redact_file(path: str) -> str | None:
    """Return redacted utf-8 text of a trace file, or None if binary/unreadable."""
    if not os.path.isfile(path) or is_binary(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return redact_text(f.read())
    except OSError:
        return None
