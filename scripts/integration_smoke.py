#!/usr/bin/env python3
"""Agent Rewards — B0 integration smoke test.

Boots the FastAPI backend in-process (TestClient), exercises the whole API:
health → mint key → upload (with dedup) → list → credits → fetch → download,
AND verifies the dashboard static files are served correctly at '/'.

Requires: the `backend` package importable (run from repo root), and the
dashboard/ dir present. Installs no deps; assumes backend deps already present.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import json
import hashlib

# isolate backend storage (backend honors DATABASE_URL + AGENT_REWARDS_STORE_DIR)
_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/ar.db")
os.environ.setdefault("AGENT_REWARDS_STORE_DIR", os.path.join(_tmp, "store"))
os.environ.setdefault("AGENT_REWARDS_ADMIN_KEY", "test-admin-key")

from backend.app import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

PASS = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global PASS
    mark = "✅" if cond else "❌"
    print(f"{mark} {name}" + (f" — {extra}" if extra else ""))
    if not cond:
        raise SystemExit(f"FAILED: {name}")


client = TestClient(app)


def main() -> None:
    # 1. health (unauthenticated)
    r = client.get("/v1/health")
    check("health", r.status_code == 200 and r.json().get("status") == "ok",
          str(r.json()))

    # 2. dashboard static at '/'
    r = client.get("/")
    check("dashboard index at /", r.status_code == 200,
          f"status={r.status_code}, len={len(r.text)}")

    # 3. mint key (admin)
    r = client.post("/v1/auth/keys", headers={"X-Admin-Key": "test-admin-key"})
    check("mint key w/ admin", r.status_code == 200, str(r.text))
    api_key = r.json()["api_key"]
    auth = {"Authorization": f"Bearer {api_key}"}

    # 4. mint with WRONG admin -> 403
    r = client.post("/v1/auth/keys", headers={"X-Admin-Key": "nope"})
    check("wrong admin -> 403", r.status_code == 403, str(r.status_code))

    # 5. no auth -> 401
    r = client.get("/v1/credits")
    check("no auth -> 401", r.status_code == 401, str(r.status_code))

    # 6. upload
    content = '{"role":"user","content":"hi"}\n{"role":"assistant","content":"hello"}\n'
    body = {
        "agent": "claude",
        "content": content,
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "size_bytes": len(content),
        "license": "research",
        "scope": "open-source repo",
    }
    r = client.post("/v1/traces", json=body, headers=auth)
    check("upload -> registered", r.status_code == 201, str(r.text))
    payload = r.json()
    check("upload credits > 0", payload.get("credits", 0) > 0, str(payload))
    trace_id = payload["trace_id"]

    # 7. upload duplicate -> 409
    r = client.post("/v1/traces", json=body, headers=auth)
    check("duplicate -> 409", r.status_code == 409, str(r.status_code))

    # 8. list own traces
    r = client.get("/v1/traces", headers=auth)
    traces = r.json().get("traces", [])
    check("list has >=1", len(traces) >= 1 and traces[0]["trace_id"] == trace_id)

    # 9. credits
    r = client.get("/v1/credits", headers=auth)
    cd = r.json()
    check("credits balance", cd.get("traces_registered", 0) >= 1, str(cd))

    # 10. fetch own trace
    r = client.get(f"/v1/traces/{trace_id}", headers=auth)
    check("fetch own trace", r.status_code == 200
          and r.json().get("content") == content)

    # 11. fetch OTHER's trace -> isolation (new key must not see it)
    r2 = client.post("/v1/auth/keys", headers={"X-Admin-Key": "test-admin-key"})
    other_auth = {"Authorization": f"Bearer {r2.json()['api_key']}"}
    r = client.get(f"/v1/traces/{trace_id}", headers=other_auth)
    check("isolation: other key 404", r.status_code in (403, 404),
          str(r.status_code))

    # 12. download raw
    r = client.get(f"/v1/traces/{trace_id}/download", headers=auth)
    check("download raw jsonl", r.status_code == 200
          and r.headers.get("content-type", "").startswith("application/x-ndjson"),
          r.headers.get("content-type", ""))

    print(f"\n🧪 ALL INTEGRATION CHECKS PASSED ({len([None])})")


if __name__ == "__main__":
    main()
