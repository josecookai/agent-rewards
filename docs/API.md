# Agent Rewards — Backend API Contract (v1)

Authoritative interface for the hosted backend (B0 #2/#3) and the dashboard (B0 #4).
The MCP server and dashboard both talk to this. **Do not change paths without
updating both implementations + this file.**

Base URL: `https://api.agent-rewards.ai` (dev: `http://127.0.0.1:8000`)

## Auth

Every request (except `GET /v1/health` and `POST /v1/auth/keys`) requires:

```
Authorization: Bearer <api_key>
```

API keys are minted by an admin holding the server `AGENT_REWARDS_ADMIN_KEY`:

```
POST /v1/auth/keys
  headers: X-Admin-Key: <AGENT_REWARDS_ADMIN_KEY>
  → 200 {"api_key": "ar_<42 hex>"}     # plaintext shown once; store hashed
```

Seed flow: if `AGENT_REWARDS_ADMIN_KEY` is unset the server generates one at
first boot and prints it to the log (dev convenience). Key hashes (sha256) are
stored; the plaintext key is never persisted.

## Endpoints

### `GET /v1/health` — unauthenticated
→ `200 {"status":"ok","schema_version":1}`

### `POST /v1/traces` — upload a redacted trace
Body (JSON):
```json
{
  "agent": "claude",
  "content": "{...jsonl lines...}",   // redacted trace text
  "sha256": "…",                       // of the content, for dedup
  "size_bytes": 12345,
  "license": "research",               // research | commercial | exclusive
  "scope": "open-source repo"          // from MCP scope_of
}
```
Behavior:
- Compute/verify content sha256; **reject 409 if already in hash_registry** (immutable dedup).
- Store blob in object store; insert `traces` + `hash_registry` rows.
- Mint credits from `size_bytes` (server-side rate, not client).
- `201 {"trace_id":"…","credits":3.14,"status":"registered"}`

### `GET /v1/traces` — list caller's traces (own-scope)
→ `200 {"traces":[{"trace_id","agent","credits","size_bytes","created_at","sha256"}]}`

### `GET /v1/traces/{trace_id}` — fetch one trace (caller's own)
→ `200 {"trace_id","agent","license","scope","created_at","content":"…"}`

### `GET /v1/credits` — ledger summary
→ `200 {"balance":3.14,"traces_registered":7,"recent":[{...}]}`

### `GET /v1/traces/{trace_id}/download` — raw JSONL
→ `200` body = raw JSONL bytes, `Content-Type: application/x-ndjson`
   (used by the dashboard timeline viewer / decontamination tooling)

## Conventions
- JSON errors: `{"error":"msg"}` with proper HTTP status (401/403/404/409/422).
- Content is **pre-redacted client-side**; server stores as-is (server may add
  server-side scrub as defense-in-depth in a later milestone).
- Per-user isolation: a key only ever reads/writes its own traces (dashboard is
  read-only per user → own trace registry keyed by key_id).
- Case: `sha256` field is hex lowercase; `trace_id` is opaque string.

## Implementation targets (reference)
- Backend: Python **FastAPI** + SQLAlchemy. `DATABASE_URL` env — default
  `sqlite:///./agent_rewards.db` for dev, Postgres URL for prod (same schema).
  Object store: `AGENT_REWARDS_STORE_DIR` dir on disk (S3/R2 pluggable later).
- Dashboard: static HTML/JS/CSS **served by the backend** at `/` (no build step).
  Uses the bearer token (kept in `localStorage`, paste-in by user).
- MCP `agent_rewards/server.py`: when `AGENT_REWARDS_BACKEND_URL` **and**
  `AGENT_REWARDS_API_KEY` are both set, `upload_trace` POSTs here instead of the
  local sqlite ledger.
