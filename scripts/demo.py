#!/usr/bin/env python3
"""Agent Rewards — local demo / smoke test.

Runs the MCP server in-process, exercises every tool through a real stdio
client session, and prints the results. Uses a throwaway ledger dir so it never
touches ~/.agent-rewards.

Usage:
    python3 scripts/demo.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

DB = tempfile.mkdtemp()
DEMO_TRACE = os.path.join(tempfile.mkdtemp(), "demo_trace.jsonl")

TOOLS = [
    ("find_trace", {"limit": 3}),
    ("scope_of", {"path": DEMO_TRACE}),
    ("upload_trace", {"path": DEMO_TRACE, "agent": "claude"}),
    ("get_credits", {}),
    ("view_trace", {"path": DEMO_TRACE, "redact_output": True}),
]


async def _main() -> int:
    with open(DEMO_TRACE, "w") as f:
        f.write('{"role":"user","content":"token sk-demo-abcdefghijklmno"}\n')

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "agent_rewards.server"],
        env={**os.environ, "AGENT_REWARDS_DB_DIR": DB},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", ", ".join(sorted(t.name for t in tools.tools)))
            for name, args in TOOLS:
                res = await session.call_tool(name, args)
                data = json.loads(res.content[0].text)
                print(f"\n== {name} ==\n{json.dumps(data, ensure_ascii=False, indent=2)[:800]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
