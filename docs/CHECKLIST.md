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
- [ ] README updated with actual install + config snippet
- [ ] `scripts/install.sh` auto-detects agents + writes MCP config
- [ ] CHANGELOG entry

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
