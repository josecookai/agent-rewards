# 🤖 Agent Rewards

**Turn your coding-agent traces into a stablecoin reward.**

Agent Rewards is an open-source skill/MCP that installs into your coding agents — **Claude Code,
Codex, Grok Bot, Hermes Agent, Openclaw** — automatically finds, redacts, and uploads your agent
sessions, and lets you **sell access to those traces to researchers and model trainers for
USDC/USDT**.

Your agents already generate high-value training data every day (tool calls, multi-turn reasoning,
error recovery). You generate that data anyway. Agent Rewards makes it worth something.

![GitHub release](https://img.shields.io/badge/release-v0.1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platforms](https://img.shields.io/badge/claude-code-codex-grok-hermes-openclaw-lightgrey)

---

## Why

Real conversation/trajectory data is the scarcest, most valuable post-training signal for open
models. Yet today:

- **HF Agent Traces** gives you the upload pipeline — but it's *manual* (`hf upload`, no incentive).
- **KTH reproducible-trajectories** proves "install + share to a DB" — but CLI-only, no reward.
- **WildChat / LMSYS / ShareChat** proved wild conversation data trains better models.

None of them is **native, automated, privacy-first, and paid**. That's the gap Agent Rewards fills.

---

## ✨ Features

1. **🔍 Find your trace** — scans all supported agents' local session dirs, cross-platform.
2. **⬆️ Upload / auto-upload daily** — incremental sync daemon, sha256 dedup, offline queue.
3. **🖥️ View your trace** — HF-style timeline viewer: prompts, tool calls, tool outputs, reasoning.
4. **🪙 View your credits** — live ledger + token balance.
5. **🔁 Exchange your traces for USDC/USDT** — sell access on-chain (Base L2, low fees); pull-based,
   per-trace licensing (research / commercial / exclusive).

---

## 🚀 One-click install

Agent Rewards ships as (a) a shared **MCP server** and (b) thin **per-agent skills** so it mounts
natively into each runtime.

| Agent          | Install target                       | Trace location                     |
|----------------|--------------------------------------|------------------------------------|
| Claude Code    | `~/.claude/plugins/` skill           | `~/.claude/projects/**/*.jsonl`    |
| Codex          | `~/.codex/` skill                    | `~/.codex/sessions/**/rollout-*.jsonl` |
| Grok Bot       | Grok skill                           | `~/.grok/**`                       |
| Hermes Agent   | `~/.hermes/skills/` + MCP server     | `~/.hermes/sessions/**`            |
| Openclaw       | Openclaw skill                       | `~/.openclaw/**`                   |

```bash
# one-shot installer (auto-detects agents present on the machine)
npx agent-rewards install
# or via MCP config
#   mcp_servers:
#     agent-rewards:
#       url: "https://api.agent-rewards.ai/mcp"
```

---

## 🔒 Privacy by default (the moat)

- **Git-aware scoping** — default uploads only traces touching **open-source repositories**. Private
  code is opt-in only.
- **Local redaction** — secret/PII/token scrub + LLM review gate *before* anything leaves the machine.
- **Provenance** — content-addressed (sha256 / IPFS), immutable hash registry.
- **Clear licensing** — every trace is tagged `research` / `commercial` / `exclusive`; you set the price.

You stay in control of *what* leaves your machine and *who* can buy it.

---

## Architecture

```
[installer]
   └─ per-agent skills / MCP  (claude · codex · grok · hermes · openclaw)
         └─ [collector] scan trace jsonl
              └─ [redactor] git-aware + secret/PII scrub (local-first)
                   └─ [sync daemon] upload daily · dedup · offline queue
                        └─ [backend] Postgres + object store + hash registry
                             ├─ [api] REST / MCP read API
                             ├─ [dashboard] view traces · credits · listings
                             └─ [ledger] USDC/USDT settlement (Base L2)
                                  └─ [marketplace] buy / sell access
```

---

## Roadmap

- **M0** — repo + README + demo landing page *(this release)*
- **M1** — HTTP MCP server: `find_trace` / `upload_trace` / `view_trace` / `get_credits`
- **M2** — per-agent skills (Claude Code, Codex, Hermes first) + redactor + daily daemon
- **M3** — backend + dashboard + hash registry + decontamination
- **M4** — ledger + USDC/USDT settlement + marketplace
- **M5** — open-sourcing contributor rewards / token incentives

---

## Getting started (contributors)

```bash
git clone https://github.com/josecookai/agent-rewards.git
cd agent-rewards
# landing page (demo)
python3 -m http.server --directory landing 8000   # → http://localhost:8000
```

---

## Related work

- [HF Agent Traces](https://huggingface.co/docs/hub/main/en/agent-traces) — trace upload + viewer infra
- [KTH reproducible-trajectories](https://github.com/ASSERT-KTH/reproducible-trajectories) — share-to-DB
- [ShareChat](https://arxiv.org/html/2512.17843v3) — multi-platform wild conversation dataset (incl. Grok)
- [WildChat](https://wildchat.allen.ai/) — 1M real user–ChatGPT conversations

---

## License

MIT. Traces contributed by users remain under **their** chosen license and are only accessible to
buyers you approve.
