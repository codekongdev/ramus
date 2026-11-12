"""Unit tests for the shared evaluation-script helpers (env-file parsing and key resolution)."""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import eval_support  # noqa: E402


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("OTHER=x\n# c\nexport OPENAI_API_KEY='dummy-k'  # note\nOPENAI_API_KEY_X=no\n", "dummy-k"),
        ('OPENAI_API_KEY="dq-key"\n', "dq-key"),
        ("OPENAI_API_KEY=plain # comment\n", "plain"),
        ("OPENAI_API_KEY_X=no\nOTHER=1\n", None),
        ("OTHER=1\n", None),
        ("OPENAI_API_KEY=\n", None),
    ],
)
def test_read_env_key(tmp_path, content, expected):
    env_path = tmp_path / "sample.env"
    env_path.write_text(content, encoding="utf-8")
    assert eval_support.read_env_key(env_path) == expected


def test_resolve_api_key_exits_without_key(tmp_path, monkeypatch):
    env_path = tmp_path / "empty.env"
    env_path.write_text("OTHER=1\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    for env_file in (str(env_path), None):
        with pytest.raises(SystemExit) as excinfo:
            eval_support.resolve_api_key(env_file)
        assert "needs OPENAI_API_KEY" in str(excinfo.value)


def test_resolve_api_key_reads_the_env_file(tmp_path):
    env_path = tmp_path / "ok.env"
    env_path.write_text("OPENAI_API_KEY=sk-test-from-file\n", encoding="utf-8")
    assert eval_support.resolve_api_key(str(env_path)) == "sk-test-from-file"


def test_resolve_api_key_exits_cleanly_when_env_file_is_missing(tmp_path):
    missing = tmp_path / "secret-dir-name" / "missing.env"
    with pytest.raises(SystemExit) as excinfo:
        eval_support.resolve_api_key(str(missing))
    message = str(excinfo.value)
    assert "could not read the --env-file" in message
    assert "secret-dir-name" not in message


def test_resolve_api_key_exits_cleanly_when_env_file_is_not_text(tmp_path):
    env_path = tmp_path / "binary.env"
    env_path.write_bytes(b"OPENAI_API_KEY=\xff\xfe\x00sk-leak")
    with pytest.raises(SystemExit) as excinfo:
        eval_support.resolve_api_key(str(env_path))
    assert "could not read the --env-file" in str(excinfo.value)
    assert "sk-leak" not in str(excinfo.value)


def test_static_credentials_returns_its_key():
    import uuid

    assert eval_support.StaticCredentials("sk-test").get_api_key(uuid.uuid4()) == "sk-test"
