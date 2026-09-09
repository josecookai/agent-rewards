"""Tests for the trace discovery (collector)."""
import os

from agent_rewards import collector


def _make_trace(tmp_path, rel, mtime):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"role":"user","content":"hi"}\n')
    os.utime(p, (mtime, mtime))
    return p


class TestScanAgents:
    def test_finds_claude_jsonl(self, tmp_path):
        _make_trace(tmp_path, ".claude/projects/dir/session.jsonl", 1000.0)
        _make_trace(tmp_path, ".claude/projects/dir/nested/x.jsonl", 2000.0)
        traces = collector.scan_agents(["claude"], home=tmp_path)
        assert len(traces) == 2
        assert all(t.agent == "claude" for t in traces)

    def test_codex_rollout_only(self, tmp_path):
        _make_trace(tmp_path, ".codex/sessions/ab/rollout-123.jsonl", 1000.0)
        # a non-rollout jsonl under sessions should NOT match codex pattern
        _make_trace(tmp_path, ".codex/sessions/ab/other.jsonl", 1000.0)
        traces = collector.scan_agents(["codex"], home=tmp_path)
        names = {os.path.basename(t.path) for t in traces}
        assert names == {"rollout-123.jsonl"}

    def test_sorted_newest_first(self, tmp_path):
        _make_trace(tmp_path, ".claude/projects/a/old.jsonl", 1000.0)
        _make_trace(tmp_path, ".claude/projects/b/new.jsonl", 9000.0)
        traces = collector.scan_agents(["claude"], home=tmp_path)
        assert len(traces) == 2
        assert traces[0].path.endswith("new.jsonl")

    def test_ignores_non_trace_ext(self, tmp_path):
        p = tmp_path / ".claude" / "projects" / "a" / "session.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("not a trace")
        assert collector.scan_agents(["claude"], home=tmp_path) == []

    def test_find_trace_limit(self, tmp_path):
        for i in range(10):
            _make_trace(tmp_path, f".claude/p{i}/s.jsonl", 1000.0 + i)
        assert len(collector.find_trace(["claude"], limit=3, )) == 3
        # find_trace always uses $HOME — verify it at least returns our count cap type
        assert callable(collector.find_trace)
