# Agent Rewards — Roadmap

**Status: `M1` partially shipped (working local MCP server).** This roadmap
tracks the project from the current M0/M1 scaffold toward a production
agent-trace marketplace with USDC/USDT settlement.

Legend: ✅ shipped · 🔨 in progress · ⬜ planned · ⛔ blocked

---

## M0 — Foundation ✅ *(done)*
- [x] GitHub repo + MIT license
- [x] README (positioning, architecture, features)
- [x] Demo landing page (`landing/`) + GitHub Pages workflow (`.github/workflows/static.yml`)

## M1 — MCP server: usable local MCP ✅ *(core shipped)*
Goal: the MCP **actually works** — you can install it and call it in Hermes/Claude/Codex today.

- [x] `agent_rewards` Python package (renamed from `mcp/` to avoid SDK name clash)
- [x] `redact.py` — local, git-aware secret/PII scrubber *(fixed `(?i)` regex bug)*
- [x] `ledger.py` — sqlite credits ledger (sha256 dedup, credits per KB)
- [x] `collector.py` — cross-agent trace discovery (`find_trace`)
- [x] `server.py` — FastMCP stdio server, 5 tools:
  - `find_trace` · `view_trace` · `upload_trace` · `get_credits` · `scope_of`
- [x] `pyproject.toml` — installable, `agent-rewards-mcp` entry point
- [x] Test suite (20 tests) incl. in-process stdio `ClientSession` e2e
- [x] Verified end-to-end over real stdio transport
- 🔨 Install docs / MCP config snippet for Hermes + Claude (`config.yaml`) — README done; `mcp/` snippet in repo pending
- ⬜ `scripts/install.sh` — auto-detect agents, one-shot installer (from README's `npx agent-rewards install`)
- ⬜ TLS-authd **HTTP** mode (`FastMCP` streamable-http) for remote dashboard use

## ⚠️ Beta Gate (B0) — Public Preview 🔨 *(backend + dashboard + installer shipped)*
**Definition of beta:** an outsider can go from `git clone` to a running MCP + hosted backend
in **under 2 minutes**, upload real traces end-to-end, and verify them in a dashboard — without
touching code. Settlement is **explicitly NOT required** for beta (that's M4/production).

Gap analysis — current status vs. beta:

| # | Area | Status | Needed for beta | Blocking? |
|---|------|--------|-----------------|-----------|
| 1 | **One-click install** | ✅ `scripts/install.sh` + `run.sh`/`uninstall.sh` | `uvx`/`pipx` one-liner polish | 🟡 |
| 2 | **Hosted backend** | ✅ `backend/` FastAPI (Postgres-ready schema, object store, hash dedup) | deploy to real host | 🟡 |
| 3 | **Upload auth** | ✅ API-key (+hash of key stored), admin mint, per-key isolation | rate-limit/lease hardening | 🟡 |
| 4 | **Dashboard** | ✅ `dashboard/` static (gate, credits, traces, timeline viewer) served at `/` | hosted deploy | 🟡 |
| 5 | **HTTP MCP mode** | ⬜ stdio only | `streamable-http` + auth, or remote upload client | 🟡 |
| 6 | **Privacy hardening** | 🔨 rule-based scrub only | LLM review gate + broader PII/wallet patterns + terms/ToS | 🔴 |
| 7 | **Deployment** | 🔨 works locally (`uvicorn backend.app:app`) | demo domain (api.agent-rewards.ai) + CI/CD | 🔴 |
| 8 | **E2E-flows demo** | ✅ verified locally (12 integration checks + browser) | repeat on fresh host | 🟡 |
| 9 | **Per-trace visibility** | 🟡 remote-presence heuristic | real public/private repo detection | 🟡 |
| 10 | **Basic decontamination** | ⬜ | train/test leakage fingerprint | 🟢 (nice-to-have) |

**B0 exit criteria** → 🔴 items cleared (privacy hardening + a live deploy proving the E2E
from a fresh host), and `docs/BETA.md` walkthrough is proven from a clean machine.

## M2 — Per-agent skills + redactor + daily daemon
Goal: zero-touch collection — traces get found, redacted, and banked daily.

- ⬜ Per-agent skill installers: **Claude Code → Codex → Hermes → Grok → Openclaw**
- ⬜ Git-aware scoping v2 — detect public-vs-private repo **per trace** (currently `open-source repo`
  is inferred only from "has an origin remote"; needs visibility detection)
- ⬜ LLM review gate — optional pass over redacted output before upload
- ⬜ Daily sync daemon — incremental upload, sha256 dedup, offline queue (reuse `ledger` + `collector`)
- ⬜ Secret patterns expansion + PII heuristics (emails, phone #s, wallet addrs)

## M3 — Backend + dashboard + hash registry + decontamination
Goal: a real hosted registry buyers can query, with dataset-quality controls.

- ⬜ Backend: Postgres + object store + immutable content-addressed hash registry (sha256/IPFS)
- ⬜ Dashboard: HF-style timeline viewer (streams JSONL into a readable conversation)
- ⬜ Live credits/ledger view (wire `get_credits` to backend, not just local sqlite)
- ⬜ Decontamination — train/test leakage checks (fingerprint traces against eval sets)
- ⬜ Licensing tags per trace: `research` / `commercial` / `exclusive`

## M4 — Ledger + USDC/USDT settlement + marketplace
Goal: the monetary loop closes — sellers get paid, buyers get licensed access.

- ⬜ On-chain settlement — USDC/USDT on Base L2 (pull-based, per-trace licensing)
- ⬜ Contract addresses + SDK/CLI for exchange
- ⬜ Marketplace: list, discover, buy access; seller approval flow
- ⬜ Real pricing model (replaces `CREDITS_PER_KB` demo rate)

## M5 — Contributor rewards / token incentives
Goal: grow supply side.

- ⬜ Open-source contributor reward mechanics
- ⬜ Optional token / points layer (if a token becomes justified)

---

## Guiding principles
1. **Privacy-first is the moat** — redact locally, before anything leaves the machine.
2. **Provenance** — content-addressed, immutable; buyers can verify.
3. **Native MCP** — install as a skill + MCP server, zero manual workflow.
4. **Cross-agent** — Claude Code / Codex / Hermes / Grok / Openclaw share one pipeline.
5. **Licensing control** — the seller always decides who can buy and at what price.
