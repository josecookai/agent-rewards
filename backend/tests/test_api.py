"""Tests for the hosted backend (docs/API.md contract).

Run::

    cd backend && pytest tests/ -v

Uses an isolated sqlite DB + temp object-store dir per test instance, so tests
never touch a real database or the shared dashboard.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

# Ensure the repo root is importable regardless of cwd, and keep the module-level
# `app = create_app()` in backend.app from writing default ./agent_rewards.db.
# backend/tests/test_api.py -> parents[2] is the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/module_side_effect.db")
os.environ.setdefault("AGENT_REWARDS_STORE_DIR", tempfile.mkdtemp())
os.environ.setdefault("AGENT_REWARDS_ADMIN_KEY", "test-admin-module")

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

ADMIN_KEY = "test-admin-key"


def _sha(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        db_url=f"sqlite:///{tmp_path / 'test.db'}",
        store_dir=str(tmp_path / "store"),
        admin_key=ADMIN_KEY,
        dashboard_dir=str(tmp_path / "no-dashboard"),  # absent -> no static mount
    )
    with TestClient(app) as c:
        yield c


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _mint(client, admin_key: str = ADMIN_KEY) -> str:
    resp = client.post("/v1/auth/keys", headers={"X-Admin-Key": admin_key})
    assert resp.status_code == 200, resp.text
    return resp.json()["api_key"]


def _upload(client, token: str, content: str, agent: str = "claude"):
    body = {
        "agent": agent,
        "content": content,
        "sha256": _sha(content),
        "size_bytes": len(content.encode("utf-8")),
        "license": "research",
        "scope": "open-source repo",
    }
    return client.post("/v1/traces", json=body, headers=_auth(token))


# --------------------------------------------------------------------------- #
# health
# --------------------------------------------------------------------------- #
def test_health_unauthenticated(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "schema_version": 1}


# --------------------------------------------------------------------------- #
# admin mint
# --------------------------------------------------------------------------- #
def test_mint_key(client):
    resp = client.post("/v1/auth/keys", headers={"X-Admin-Key": ADMIN_KEY})
    assert resp.status_code == 200
    api_key = resp.json()["api_key"]
    assert api_key.startswith("ar_")
    assert len(api_key) == 3 + 42  # 'ar_' + 42 hex chars


def test_wrong_admin_key_forbidden(client):
    resp = client.post("/v1/auth/keys", headers={"X-Admin-Key": "not-the-admin"})
    assert resp.status_code == 403
    assert "error" in resp.json()


def test_mint_without_admin_key_forbidden(client):
    resp = client.post("/v1/auth/keys")
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# upload + dedup
# --------------------------------------------------------------------------- #
def test_upload_ok(client):
    token = _mint(client)
    content = "trace line 1\n"
    resp = _upload(client, token, content)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "registered"
    assert body["credits"] > 0
    assert body["trace_id"]


def test_upload_dedup_409(client):
    token = _mint(client)
    content = "dedup me\n"
    assert _upload(client, token, content).status_code == 201
    # same content -> same sha256 -> 409 even by the same key
    resp = _upload(client, token, content)
    assert resp.status_code == 409
    assert "error" in resp.json()


def test_upload_sha256_mismatch_422(client):
    token = _mint(client)
    content = "content here\n"
    body = {
        "agent": "claude",
        "content": content,
        "sha256": "f" * 64,  # wrong
        "size_bytes": len(content.encode("utf-8")),
        "license": "research",
        "scope": "s",
    }
    resp = client.post("/v1/traces", json=body, headers=_auth(token))
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# listing / fetching own
# --------------------------------------------------------------------------- #
def test_list_own_traces(client):
    token = _mint(client)
    contents = ["alpha\n", "beta\n", "gamma\n"]
    for c in contents:
        assert _upload(client, token, c).status_code == 201
    resp = client.get("/v1/traces", headers=_auth(token))
    assert resp.status_code == 200
    traces = resp.json()["traces"]
    assert len(traces) == 3
    for t in traces:
        for field in ("trace_id", "agent", "credits", "size_bytes", "created_at", "sha256"):
            assert field in t


def test_fetch_own_trace(client):
    token = _mint(client)
    content = "unique content\n"
    uploaded = _upload(client, token, content).json()
    tid = uploaded["trace_id"]
    resp = client.get(f"/v1/traces/{tid}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["trace_id"] == tid
    assert body["content"] == content
    assert body["agent"] == "claude"
    assert body["license"] == "research"


def test_fetch_unknown_trace_404(client):
    token = _mint(client)
    resp = client.get(f"/v1/traces/{'0' * 32}", headers=_auth(token))
    assert resp.status_code == 404


def test_download_raw_ndjson(client):
    token = _mint(client)
    content = "line1: {}\nline2: {}\n"
    tid = _upload(client, token, content).json()["trace_id"]
    resp = client.get(f"/v1/traces/{tid}/download", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    assert resp.content.decode("utf-8") == content


# --------------------------------------------------------------------------- #
# per-user isolation
# --------------------------------------------------------------------------- #
def test_per_user_isolation(client):
    token_a = _mint(client)
    token_b = _mint(client)
    tid = _upload(client, token_a, "a's secret trace\n").json()["trace_id"]
    # B cannot see or fetch A's trace
    b_list = client.get("/v1/traces", headers=_auth(token_b)).json()["traces"]
    assert all(t["trace_id"] != tid for t in b_list)
    assert client.get(f"/v1/traces/{tid}", headers=_auth(token_b)).status_code == 404
    assert (
        client.get(f"/v1/traces/{tid}/download", headers=_auth(token_b)).status_code
        == 404
    )


# --------------------------------------------------------------------------- #
# credits
# --------------------------------------------------------------------------- #
def test_credits_summary(client):
    token = _mint(client)
    assert _upload(client, token, "first\n").status_code == 201
    assert _upload(client, token, "second " * 100 + "\n").status_code == 201
    resp = client.get("/v1/credits", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance"] > 0
    assert body["traces_registered"] == 2
    assert len(body["recent"]) == 2
    assert body["balance"] == round(
        sum(t["credits"] for t in body["recent"]), 4
    )


# --------------------------------------------------------------------------- #
# auth failures
# --------------------------------------------------------------------------- #
def test_401_no_key(client):
    assert client.get("/v1/traces").status_code == 401
    assert client.get("/v1/credits").status_code == 401


def test_401_wrong_key(client):
    resp = client.get("/v1/traces", headers=_auth("ar_" + "a" * 42))
    assert resp.status_code == 401
    assert "error" in resp.json()
