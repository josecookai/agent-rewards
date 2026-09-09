"""Tests for the redaction layer."""
import os
import tempfile

import pytest

from agent_rewards import redact


class TestRedactText:
    def test_sk_key(self):
        assert redact.redact_text("key=sk-abc123def456ghi789jkl012") == \
            "key=<SK>"

    def test_gh_token(self):
        assert redact.redact_text("token=ghp_" + "a" * 40) == "token=<GH_TOKEN>"

    def test_private_key(self):
        blob = (
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n"
            "-----END RSA PRIVATE KEY-----"
        )
        out = redact.redact_text(blob)
        assert "<PRIVKEY>" in out
        assert "MIIEow" not in out

    def test_bearer(self):
        assert redact.redact_text("Authorization: Bearer abc.def.ghi") == \
            "Authorization: <BEARER>"

    def test_password(self):
        out = redact.redact_text('"password": "hunter2"')
        assert "hunter2" not in out
        assert "<PASSWORD>" in out

    def test_plain_text_unchanged(self):
        assert redact.redact_text("just normal words here 12345") == \
            "just normal words here 12345"


class TestRedactFile:
    def test_binary_return_none(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n")
            p = f.name
        try:
            assert redact.redact_file(p) is None
        finally:
            os.unlink(p)

    def test_text_redacted(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write('{"role":"user","content":"api_key=sk-live-abc123"}')
            p = f.name
        try:
            out = redact.redact_file(p)
            assert out is not None
            assert "sk-live-secret99999" not in out
            assert ("<API_KEY>" in out or "<SK>" in out)
        finally:
            os.unlink(p)


class TestDetectRepo:
    def test_no_repo(self, tmp_path):
        info = redact.detect_repo(tmp_path / "x.jsonl")
        assert info.scope == "unknown"

    def test_repo_no_remote_is_private(self, tmp_path):
        os.makedirs(tmp_path / ".git")
        info = redact.detect_repo(tmp_path)
        assert info.is_repo is True
        assert info.scope == "private repo"

    def test_repo_with_remote_is_open(self, tmp_path):
        os.makedirs(tmp_path / ".git")
        # monkeypatch the git call by writing a fake remote via git if available
        pytest.importorskip("subprocess")
        if not _git_available():
            pytest.skip("git not available")
        os.system(
            f"cd {tmp_path} && git init -q && "
            f"git remote add origin https://github.com/foo/bar.git"
        )
        info = redact.detect_repo(tmp_path)
        assert info.scope == "open-source repo"


def _git_available() -> bool:
    import shutil
    return shutil.which("git") is not None
