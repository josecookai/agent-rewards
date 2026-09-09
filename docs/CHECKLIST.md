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

## ⚠️ B0 — Beta / Public Preview ⬜
**Gate:** an outsider goes from `git clone` → running MCP + hosted backend in <2 min,
uploads a real trace end-to-end, and verifies it in a dashboard — no code changes.

### 1 · One-click install 🔴
- [ ] `scripts/install.sh` — auto-detect agents present, write MCP config, run server
- [ ] `uvx agent-rewards` / `pipx install agent-rewards` one-liner
- [ ] Fresh-machine walkthrough (no Python venv knowledge needed)

### 2 · Hosted backend 🔴 (currently: local-only sqlite)
- [ ] Postgres schema: `traces`, `agents`, `hash_registry` (sha256, immutable)
- [ ] Object store for trace blobs (S3/GCS/R2 or local volume)
- [ ] Upload endpoint (`POST /v1/traces`) accepting redacted JSONL
- [ ] Hash-registry dedup: reject on duplicate content-address

### 3 · Upload auth 🔴
- [ ] API-key issuance + per-key rate-limit / quota
- [ ] Lease token on upload; server validates key + content signature
- [ ] `.env`/secret handling; keys never in the MCP tool args

### 4 · Dashboard 🔴
- [ ] Timeline viewer rendering a raw JSONL trace (HF-style)
- [ ] Credits / ledger view wired to backend (not just local sqlite)
- [ ] Read-only per-user scope (a user only sees their own traces)

### 5 · HTTP MCP mode 🟡
- [ ] `streamable-http` transport with bearer auth (FastMCP host)
- [ ] Remote upload client path (server-side collector uploads via HTTP)

### 6 · Privacy hardening 🔴
- [ ] Broader PII patterns (email, phone, wallet addr, IPs)
- [ ] Optional LLM review gate over redacted output before persist
- [ ] Terms-of-service / data-license policy (`research`/`commercial`/`exclusive`)
- [ ] Rate-limit + abuse controls on upload

### 7 · Deployment 🔴
- [ ] Demo instance on a domain (api.agent-rewards.ai) behind TLS
- [ ] CI/CD: build + deploy on merge (`static.yml` extended for backend)
- [ ] Health-check + rollback

### 8 · E2E proof 🔴
- [ ] One test account pushes a real Claude/Codex trace through
      find→redact→upload→ledger→dashboard
- [ ] `docs/BETA.md` walkthrough proven from a clean machine

### 9 · Per-trace visibility 🟡
- [ ] Real public/private repo detection (not just "has an origin remote")

### 10 · Decontamination 🟢 (nice-to-have)
- [ ] Fingerprint traces against eval sets for train/test leakage

**B0 exit:** all 🔴/🟡 checked and verified by a fresh test account; `docs/BETA.md` green.

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
