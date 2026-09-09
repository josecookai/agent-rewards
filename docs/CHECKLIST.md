# Agent Rewards — Release Checklist

A living checklist used to gate each milestone. Check off items as they're done;
a milestone is "shippable" only when its block is fully checked.

## M1.1 — MCP server usable locally ✅
The goal of this release: you can install the package, run the stdio MCP server,
and call every tool from a real MCP client.

### Code
- [x] Package importable as `agent_rewards` (not `mcp` — avoids SDK clash)
- [x] `redact.py` scrubber loads without `re.error`; handles multiline private keys
- [x] `ledger.py` registers traces, dedups by sha256, reports balanced credits
- [x] `collector.py` finds traces across `claude/codex/hermes/grok/openclaw`
- [x] `server.py` exposes all 5 tools via FastMCP
- [x] `pyproject.toml` + `agent-rewards-mcp` entry point

### Correctness (tests)
- [x] `test_redact.py` — secret patterns, binary files, repo scope detection
- [x] `test_collector.py` — agent discovery, sorting, extension filtering
- [x] `test_server.py` — end-to-end via real stdio `ClientSession`
- [x] Full suite green: `20 passed`

### Verification
- [x] Manual stdio session: discovered `find_trace/get_credits/scope_of/upload_trace/view_trace`
- [x] `view_trace` redacts `sk-…` before content reaches the model
- [x] `upload_trace` → `get_credits` round-trip increments balance

### Docs & install
- [x] `docs/ROADMAP.md` written
- [x] `docs/CHECKLIST.md` written
- [x] README updated with actual install + config snippet
- [ ] `scripts/install.sh` auto-detects agents + writes MCP config
- [ ] CHANGELOG entry

## ⚠️ B0 — Beta / Public Preview 🔨 *(backend + dashboard + installer shipped)*
**Gate:** an outsider goes from `git clone` → running MCP + hosted backend in <2 min,
uploads a real trace end-to-end, and verifies it in a dashboard — no code changes.

### 1 · One-click install 🟡
- [x] `scripts/install.sh` — auto-detect agents present, write MCP config, run server
- [x] `scripts/run.sh` / `scripts/uninstall.sh`
- [ ] `uvx agent-rewards` / `pipx install agent-rewards` one-liner
- [x] Fresh-machine walkthrough (venv creation + MCP handshake verified: `✅ Agent Rewards MCP ready`)

### 2 · Hosted backend 🟡 (shipped: `backend/` FastAPI)
- [x] SQLAlchemy schema: `traces`, `agents`-ish, `hash_registry` (sha256, immutable) — Postgres-ready
- [x] Object store for trace blobs (`AGENT_REWARDS_STORE_DIR`)
- [x] Upload endpoint (`POST /v1/traces`) accepting JSONL + verifying sha256
- [x] Hash-registry dedup: `409` on duplicate content-address
- [ ] Deploy to a real host

### 3 · Upload auth 🟡 (shipped)
- [x] API-key mint via admin (`X-Admin-Key`), key stored as sha256 hash
- [x] Per-key read/write isolation (other key → 404) — verified
- [x] `.env`/secret handling
- [ ] Rate-limit / lease-token hardening

### 4 · Dashboard 🟡 (shipped: `dashboard/`, served at `/`)
- [x] Timeline viewer rendering raw JSONL (User/Assistant cards) — verified in browser
- [x] Credits / ledger view wired to backend — verified (balance + recent)
- [x] Read-only per-user scope (own traces only)

### 5 · HTTP MCP mode 🟡
- [ ] `streamable-http` transport with bearer auth (FastMCP host)
- [ ] Remote upload client path (MCP → hosted backend)

### 6 · Privacy hardening 🔴
- [ ] Broader PII patterns (email, phone, wallet addr, IPs)
- [ ] Optional LLM review gate over redacted output before persist
- [ ] Terms-of-service / data-license policy (`research`/`commercial`/`exclusive`)
- [ ] Rate-limit + abuse controls on upload

### 7 · Deployment 🔴 (works locally)
- [x] Runs locally via `uvicorn backend.app:app` (verified on 127.0.0.1)
- [ ] Demo instance on a domain (api.agent-rewards.ai) behind TLS
- [ ] CI/CD: build + deploy on merge (extend `static.yml` for backend)

### 8 · E2E proof 🔨 (verified locally)
- [x] `scripts/integration_smoke.py` — 12 checks pass (health, mint, upload, dedup, list, credits, fetch, isolation, download, dashboard at `/`)
- [x] `scripts/seed_demo.py` + browser walkthrough (gate → credits → traces → timeline viewer)
- [ ] Repeat E2E on a fresh host (live deploy)

### 9 · Per-trace visibility 🟡
- [ ] Real public/private repo detection (not just "has an origin remote")

### 10 · Decontamination 🟢 (nice-to-have)
- [ ] Fingerprint traces against eval sets for train/test leakage

**B0 exit:** 🔴 cleared (privacy hardening + live deploy), all verified by a fresh test
account on a fresh host; `docs/BETA.md` green.

## M1.2 — HTTP + packaging polish ⬜
- [ ] Ship `streamable-http` mode (`fastmcp run`/host:port + auth header)
- [ ] `uvx agent-rewards` / `pipx` one-liner
- [ ] GitHub release with built wheel
- [ ] MCP config snippet verified in Hermes `~/.hermes/config.yaml`
- [ ] Claude Code `.mcp.json` verified

## M2 — Skills + daemon ⬜
- [ ] Claude Code skill installed & auto-uploads
- [ ] Codex skill installed
- [ ] Hermes skill installed (trace dir `~/.hermes/sessions/**`)
- [ ] Per-trace public/private visibility detection
- [ ] Daily daemon (incremental, dedup, offline queue) running as a service
- [ ] Optional LLM review gate wired

## M3 — Backend ⬜
- [ ] Postgres + object store + hash registry schema
- [ ] Timeline viewer (dashboard) rendering a raw JSONL trace
- [ ] Decontamination check
- [ ] Licensing tags on every trace

## M4 — Settlement ⬜
- [ ] USDC/USDT settlement contract on Base L2
- [ ] Exchange SDK/CLI
- [ ] Marketplace listing + seller approval

## M5 — Incentives ⬜
- [ ] Contributor reward mechanics
- [ ] Token layer (if justified)
