"""End-to-end tests for the MCP server via a real stdio client session.

Spawns `agent_rewards.server` the same way Hermes/Claude would (stdio transport,
in-process streams) and exercises the public tool surface.

Each test runs fully inside ONE asyncio event loop — never nest asyncio.run()
inside an already-running loop.
"""
import asyncio
import json
import os
import sys
import tempfile

import pytest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_rewards import collector, ledger  # noqa: E402


def _new_env_db():
    env = {**os.environ, "AGENT_REWARDS_DB_DIR": tempfile.mkdtemp()}
    return env


async def _call_tool(session, name, args=None):
    res = await session.call_tool(name, args or {})
    return json.loads(res.content[0].text)


def _run_tools_scenario(fn):
    """Run an async scenario against a fresh stdio client, single loop."""
    async def _scenario():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "agent_rewards.server"],
            env=_new_env_db(),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await fn(session)
    return asyncio.run(_scenario())


class TestMCPLifecycle:
    def test_tools_registered(self):
        async def scenario(session):
            tools = await session.list_tools()
            return {t.name for t in tools.tools}
        names = _run_tools_scenario(scenario)
        for expected in ("find_trace", "view_trace", "upload_trace",
                         "get_credits", "scope_of"):
            assert expected in names, f"missing tool {expected}"

    def test_find_trace_call(self):
        async def scenario(session):
            return await _call_tool(session, "find_trace", {"limit": 5})
        out = _run_tools_scenario(scenario)
        assert "count" in out and "traces" in out

    def test_upload_view_credits_roundtrip(self, tmp_path):
        trace_file = tmp_path / "session.jsonl"
        trace_file.write_text(
            '{"role":"user","content":"api_key=sk-live-secret99999"}\n'
        )
        async def scenario(session):
            up = await _call_tool(session, "upload_trace",
                                  {"path": str(trace_file), "agent": "claude"})
            assert up["status"] in ("registered", "duplicate")

            cred = await _call_tool(session, "get_credits", {})
            assert "balance" in cred and cred["traces_registered"] >= 1

            view = await _call_tool(session, "view_trace",
                                    {"path": str(trace_file),
                                     "redact_output": True})
            assert view["redacted"] is True
            assert "sk-live-secret99999" not in view["content"]
            assert "<SK>" in view["content"]
            return up, cred, view
        _run_tools_scenario(scenario)

    def test_scope_of_unknown(self, tmp_path):
        p = tmp_path / "outside.jsonl"
        p.write_text("x")
        async def scenario(session):
            return await _call_tool(session, "scope_of", {"path": str(p)})
        out = _run_tools_scenario(scenario)
        assert out["scope"] == "unknown"
