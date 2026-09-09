#!/usr/bin/env python3
"""Seed demo traces into a running Agent Rewards backend."""
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("AR_BASE", "http://127.0.0.1:8765")


def req(method, path, data=None, headers=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(BASE + path, data=body, method=method)
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    if body:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    _, k = req("POST", "/v1/auth/keys", headers={"X-Admin-Key": "dev-admin"})
    api_key = k["api_key"]
    auth = {"Authorization": f"Bearer {api_key}"}
    print("minted key:", api_key)

    samples = [
        ("claude", '{"role":"user","content":"fix the OOM in the worker"}\n{"role":"assistant","content":"added a backpressure queue to limiter.py","tool_calls":[{"name":"edit_file"}]}\n'),
        ("codex", '{"role":"user","content":"write a retry decorator"}\n{"role":"assistant","content":"implemented retry with exponential backoff"}\n'),
        ("hermes", '{"role":"user","content":"summarize this PR diff"}\n{"role":"assistant","content":"here is the summary","reasoning":"grouped by subsystem"}\n'),
        ("claude", '{"role":"user","content":"set up pgbouncer"}\n{"role":"assistant","content":"connected, 20 max connections","tool_calls":[{"name":"run_terminal"}]}\n'),
    ]
    for agent, content in samples:
        body = {
            "agent": agent, "content": content,
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
            "size_bytes": len(content), "license": "research", "scope": "open-source repo",
        }
        st, r = req("POST", "/v1/traces", data=body, headers=auth)
        print("upload", agent, st, r)

    _, cd = req("GET", "/v1/credits", headers=auth)
    print("credits:", json.dumps(cd, indent=2))
    with open(os.path.expanduser("~/.agent-rewards-demo-key"), "w") as f:
        f.write(api_key)
    print("DEMO_KEY_SAVED")


if __name__ == "__main__":
    main()
