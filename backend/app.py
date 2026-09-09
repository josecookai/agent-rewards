"""Agent Rewards — hosted FastAPI backend.

A stateful HTTP service implementing the API contract in ``docs/API.md``:

* ``GET  /v1/health``                    unauthenticated liveness probe
* ``POST /v1/auth/keys``                 mint an API key (admin only)
* ``POST /v1/traces``                    upload a redacted trace  -> 201 / 409 dedup
* ``GET  /v1/traces``                    list caller's own traces
* ``GET  /v1/traces/{id}``               fetch one of the caller's traces
* ``GET  /v1/traces/{id}/download``      raw JSONL (application/x-ndjson)
* ``GET  /v1/credits``                   credits ledger summary

Auth is bearer API keys. Keys are minted by the server admin (X-Admin-Key) and
stored as sha256 hashes; the plaintext is returned once and never persisted.
Per-user isolation is keyed by ``key_id``.

Storage uses SQLAlchemy against ``DATABASE_URL`` (default sqlite for dev, any
Postgres URL in prod) and a plain directory (``AGENT_REWARDS_STORE_DIR``) for
trace blobs. The static dashboard is served from ``../dashboard`` at ``/``.

Run::

    python3 -m backend.app        # uvicorn on 0.0.0.0:8000

Environment:
    DATABASE_URL              default sqlite:///./agent_rewards.db
    AGENT_REWARDS_STORE_DIR   default ./store
    AGENT_REWARDS_ADMIN_KEY   default: generated at boot + printed to log
"""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

CREDITS_PER_KB = 0.05  # server-side mint rate (traces), matches ledger demo
SCHEMA_VERSION = 1
API_KEY_PREFIX = "ar_"

# The dashboard lives in the repo root next to this package (../dashboard).
_BACKEND_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = _BACKEND_DIR.parent / "dashboard"

Base = declarative_base()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sha256_hex(data: bytes) -> str:
    """Lowercase hex sha256 of raw bytes (used for content dedup)."""
    return hashlib.sha256(data).hexdigest()


def sha256_str(s: str) -> str:
    return sha256_hex(s.encode("utf-8"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def mint_api_key() -> str:
    return f"{API_KEY_PREFIX}{secrets.token_hex(21)}"  # ar_<42 hex>


# --------------------------------------------------------------------------- #
# ORM models (portable between sqlite and Postgres)
# --------------------------------------------------------------------------- #
class ApiKeyRow(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True)
    key_id = Column(String, nullable=False, unique=True)
    key_hash = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False)


class TraceRow(Base):
    __tablename__ = "traces"
    id = Column(Integer, primary_key=True)
    trace_id = Column(String, nullable=False, unique=True)
    key_id = Column(String, nullable=False, index=True)
    agent = Column(String, nullable=False)
    license = Column(String, nullable=False)
    scope = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String, nullable=False, index=True)
    credits = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False)


class HashRegistryRow(Base):
    __tablename__ = "hash_registry"
    sha256 = Column(String, primary_key=True)  # global, immutable dedup key
    trace_id = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)


# --------------------------------------------------------------------------- #
# Pydantic request bodies
# --------------------------------------------------------------------------- #
class TraceUpload(BaseModel):
    agent: str
    content: str  # redacted trace text (JSONL)
    sha256: str   # hex sha256 of content, for dedup
    size_bytes: int
    license: str  # research | commercial | exclusive
    scope: str


# --------------------------------------------------------------------------- #
# dependencies
# --------------------------------------------------------------------------- #
def get_db(request: Request):
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def require_key(request: Request, authorization: str | None = Header(default=None)) -> str:
    """Resolve the bearer API key to its owner's key_id, or 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing or invalid API key")
    token = authorization.split(" ", 1)[1].strip()
    if not token.startswith(API_KEY_PREFIX):
        raise HTTPException(status_code=401, detail="missing or invalid API key")
    with request.app.state.session_factory() as db:
        row = db.query(ApiKeyRow).filter(ApiKeyRow.key_hash == sha256_str(token)).first()
    if row is None:
        raise HTTPException(status_code=401, detail="missing or invalid API key")
    return row.key_id


def _blob_path(state, sha: str) -> Path:
    return state.store_path / f"{sha}.jsonl"


# --------------------------------------------------------------------------- #
# app factory
# --------------------------------------------------------------------------- #
def create_app(
    *,
    db_url: str | None = None,
    store_dir: str | None = None,
    admin_key: str | None = None,
    dashboard_dir: str | None = None,
) -> FastAPI:
    """Build and configure a fully wired FastAPI app.

    All knobs fall back to env vars so the same code runs in dev and prod, and
    the explicit keyword args let tests spin up isolated instances.
    """
    db_url = db_url or os.environ.get("DATABASE_URL", "sqlite:///./agent_rewards.db")
    store_dir = store_dir or os.environ.get("AGENT_REWARDS_STORE_DIR", "./store")
    admin_key = admin_key if admin_key is not None else os.environ.get("AGENT_REWARDS_ADMIN_KEY")
    dashboard_dir = dashboard_dir or str(DASHBOARD_DIR)

    if admin_key:
        admin_hash = sha256_str(admin_key)
        _generated_admin = False
    else:
        admin_key = f"ar_admin_{secrets.token_hex(21)}"
        admin_hash = sha256_str(admin_key)
        _generated_admin = True
        print(
            f"[agent-rewards] generated admin key "
            f"(set AGENT_REWARDS_ADMIN_KEY to suppress this): {admin_key}",
            flush=True,
        )

    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    store_path = Path(store_dir)
    store_path.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Agent Rewards Backend", version="0.1.0")
    app.state.engine = engine
    app.state.store_path = store_path
    app.state.session_factory = session_factory
    app.state.admin_hash = admin_hash

    # ---- error envelope: {error: msg} ------------------------------------ #
    @app.exception_handler(HTTPException)
    async def _http_exc_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    # ---- endpoints -------------------------------------------------------- #
    @app.get("/v1/health")
    def health() -> dict:
        return {"status": "ok", "schema_version": SCHEMA_VERSION}

    @app.post("/v1/auth/keys")
    def mint_key(
        request: Request,
        db: Session = Depends(get_db),
        x_admin_key: str | None = Header(default=None),
    ) -> dict:
        if not x_admin_key or sha256_str(x_admin_key) != request.app.state.admin_hash:
            raise HTTPException(status_code=403, detail="invalid admin key")
        api_key = mint_api_key()
        db.add(
            ApiKeyRow(
                key_id=uuid.uuid4().hex,
                key_hash=sha256_str(api_key),
                created_at=utcnow(),
            )
        )
        db.commit()
        return {"api_key": api_key}

    @app.post("/v1/traces", status_code=201)
    def upload_trace(
        payload: TraceUpload,
        request: Request,
        key_id: str = Depends(require_key),
    ) -> dict:
        if sha256_str(payload.content) != payload.sha256:
            raise HTTPException(status_code=422, detail="sha256 does not match content")
        with request.app.state.session_factory() as db:
            if db.query(HashRegistryRow).filter(
                HashRegistryRow.sha256 == payload.sha256
            ).first():
                raise HTTPException(
                    status_code=409, detail="trace already registered (duplicate sha256)"
                )
            trace_id = uuid.uuid4().hex
            credits = round(payload.size_bytes / 1024.0 * CREDITS_PER_KB, 4)
            now = utcnow()
            _blob_path(request.app.state, payload.sha256).write_text(
                payload.content, encoding="utf-8"
            )
            db.add(
                TraceRow(
                    trace_id=trace_id,
                    key_id=key_id,
                    agent=payload.agent,
                    license=payload.license,
                    scope=payload.scope,
                    size_bytes=payload.size_bytes,
                    sha256=payload.sha256,
                    credits=credits,
                    created_at=now,
                )
            )
            db.add(
                HashRegistryRow(sha256=payload.sha256, trace_id=trace_id, created_at=now)
            )
            db.commit()
        return {"trace_id": trace_id, "credits": credits, "status": "registered"}

    @app.get("/v1/traces")
    def list_traces(request: Request, key_id: str = Depends(require_key)) -> dict:
        with request.app.state.session_factory() as db:
            rows = (
                db.query(TraceRow)
                .filter(TraceRow.key_id == key_id)
                .order_by(TraceRow.created_at.desc())
                .all()
            )
        return {
            "traces": [
                {
                    "trace_id": t.trace_id,
                    "agent": t.agent,
                    "credits": t.credits,
                    "size_bytes": t.size_bytes,
                    "created_at": t.created_at.isoformat(),
                    "sha256": t.sha256,
                }
                for t in rows
            ]
        }

    # NOTE: the /download route must be declared before /{trace_id} so that the
    # literal "download" segment wins over the path-param match.
    @app.get("/v1/traces/{trace_id}/download")
    def download_trace(
        trace_id: str, request: Request, key_id: str = Depends(require_key)
    ) -> Response:
        with request.app.state.session_factory() as db:
            row = (
                db.query(TraceRow)
                .filter(TraceRow.trace_id == trace_id, TraceRow.key_id == key_id)
                .first()
            )
        if row is None:
            raise HTTPException(status_code=404, detail="trace not found")
        blob = _blob_path(request.app.state, row.sha256)
        if not blob.is_file():
            raise HTTPException(status_code=404, detail="trace content missing")
        return Response(
            content=blob.read_bytes(),
            media_type="application/x-ndjson",
        )

    @app.get("/v1/traces/{trace_id}")
    def get_trace(
        trace_id: str, request: Request, key_id: str = Depends(require_key)
    ) -> dict:
        with request.app.state.session_factory() as db:
            row = (
                db.query(TraceRow)
                .filter(TraceRow.trace_id == trace_id, TraceRow.key_id == key_id)
                .first()
            )
        if row is None:
            raise HTTPException(status_code=404, detail="trace not found")
        blob = _blob_path(request.app.state, row.sha256)
        return {
            "trace_id": row.trace_id,
            "agent": row.agent,
            "license": row.license,
            "scope": row.scope,
            "created_at": row.created_at.isoformat(),
            "content": blob.read_text(encoding="utf-8") if blob.is_file() else "",
        }

    @app.get("/v1/credits")
    def credits(request: Request, key_id: str = Depends(require_key)) -> dict:
        with request.app.state.session_factory() as db:
            rows = db.query(TraceRow).filter(TraceRow.key_id == key_id).all()
        recent = sorted(rows, key=lambda t: t.created_at, reverse=True)[:10]
        return {
            "balance": round(sum(t.credits for t in rows), 4),
            "traces_registered": len(rows),
            "recent": [
                {
                    "trace_id": t.trace_id,
                    "agent": t.agent,
                    "credits": t.credits,
                    "created_at": t.created_at.isoformat(),
                }
                for t in recent
            ],
        }

    # ---- static dashboard at '/' ----------------------------------------- #
    # Mount only if the dashboard HTML is actually present (the dashboard dir
    # is written by a parallel task and may not exist yet).
    dashboard_index = Path(dashboard_dir) / "index.html"
    if dashboard_index.is_file():
        app.mount(
            "/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard"
        )

    return app


# --------------------------------------------------------------------------- #
# console entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    import uvicorn

    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000)


app = create_app()

if __name__ == "__main__":
    main()
