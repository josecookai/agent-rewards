"""Agent Rewards — credits ledger (M1 local demo).

A tiny sqlite ledger: every upload registers a trace with a hash + byte-size,
and mints credits. Balance is sum of credits. Swap/rpc (USDC settlement) is M4.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import time
import uuid

DB_DIR = os.environ.get("AGENT_REWARDS_DB_DIR", os.path.expanduser("~/.agent-rewards"))
DB_PATH = os.path.join(DB_DIR, "ledger.db")

# demo rate: credits per 1K bytes of trace (M4 replaces with real pricing)
CREDITS_PER_KB = 0.05


def _connect() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS ledger(
            id TEXT PRIMARY KEY,
            trace_id TEXT UNIQUE,
            agent TEXT,
            path TEXT,
            size_bytes INTEGER,
            sha256 TEXT,
            credits REAL,
            registered_at REAL
        )"""
    )
    return con


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def register(trace_id: str, agent: str, path: str, size_bytes: int) -> dict:
    con = _connect()
    try:
        cur = con.execute("SELECT credits FROM ledger WHERE trace_id=?", (trace_id,))
        if cur.fetchone():
            return {"status": "duplicate", "trace_id": trace_id}
        sha = sha256_file(path) if os.path.isfile(path) else ""
        credits = round(size_bytes / 1024.0 * CREDITS_PER_KB, 4)
        con.execute(
            "INSERT INTO ledger(id,trace_id,agent,path,size_bytes,sha256,credits,registered_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, trace_id, agent, path, size_bytes, sha, credits, time.time()),
        )
        con.commit()
        return {"status": "registered", "trace_id": trace_id, "sha256": sha[:16],
                "credits": credits, "size_bytes": size_bytes}
    finally:
        con.close()


def balance() -> dict:
    con = _connect()
    try:
        row = con.execute(
            "SELECT COALESCE(SUM(credits),0), COUNT(*) FROM ledger"
        ).fetchone()
        recent = con.execute(
            "SELECT trace_id, agent, credits, registered_at FROM ledger "
            "ORDER BY registered_at DESC LIMIT 10"
        ).fetchall()
        ledger = [
            {"trace_id": t, "agent": a, "credits": c, "at": r} for t, a, c, r in recent
        ]
        return {"balance": round(row[0] or 0.0, 4), "traces_registered": row[1],
                "recent": ledger}
    finally:
        con.close()
