"""Tests for ClaudeCliProvider: login-auth subprocess flow, env stripping."""

import json
from unittest.mock import MagicMock, patch

import pytest

from police_thief.exceptions import (
    ProviderAuthError,
    ProviderCliError,
    ProviderParseError,
    ProviderTimeoutError,
)
from police_thief.infra.llm_provider import STRIP_KEYS, ClaudeCliProvider


@pytest.fixture
def provider(config):
    with patch.object(ClaudeCliProvider, "_verify_cli", return_value="9.9.9"):
        return ClaudeCliProvider(config)


def cli_result(returncode=0, stdout="", stderr=""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


class TestClaudeCliProvider:
    def test_send_extracts_result_field(self, provider):
        wrapper = json.dumps({"result": "hello world"})
        with patch("subprocess.run", return_value=cli_result(stdout=wrapper)) as run:
            assert provider.send("hi") == "hello world"
        assert "claude -p --output-format json" in run.call_args[0][0]

    def test_configured_model_passed_to_cli(self, provider, config):
        wrapper = json.dumps({"result": "ok"})
        with patch("subprocess.run", return_value=cli_result(stdout=wrapper)) as run:
            provider.send("hi")
        model = config.get("llm.model")  # whatever the config file says, no literal here
        assert f'--model "{model}"' in run.call_args[0][0]

    def test_env_strips_api_key(self, provider):
        wrapper = json.dumps({"result": "ok"})
        fake_env = {"ANTHROPIC_API_KEY": "sk-x", "PATH": "/bin", "CLAUDECODE": "1"}
        with patch("subprocess.run", return_value=cli_result(stdout=wrapper)) as run, \
             patch("os.environ", fake_env):
            provider.send("hi")
        env = run.call_args[1]["env"]
        for key in STRIP_KEYS:
            assert key not in env
        assert env["PATH"] == "/bin"

    def test_auth_error_detected(self, provider):
        with patch("subprocess.run", return_value=cli_result(1, stderr="please login")),              pytest.raises(ProviderAuthError):
            provider.send("hi")

    def test_cli_error_on_nonzero_exit(self, provider):
        with patch("subprocess.run", return_value=cli_result(1, stderr="boom")),              pytest.raises(ProviderCliError):
            provider.send("hi")

    def test_timeout_raises(self, provider):
        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.TimeoutExpired("claude", 10)),              pytest.raises(ProviderTimeoutError):
            provider.send("hi")

    def test_bad_json_raises_parse_error(self, provider):
        with patch("subprocess.run", return_value=cli_result(stdout="not json")),              pytest.raises(ProviderParseError):
            provider.send("hi")

    def test_code_fences_stripped(self, provider):
        inner = "```json\n{\"move\": \"N\"}\n```"
        wrapper = json.dumps({"result": inner})
        with patch("subprocess.run", return_value=cli_result(stdout=wrapper)):
            assert provider.send("hi") == '{"move": "N"}'

    def test_missing_cli_raises(self, config):
        with patch("subprocess.run", side_effect=OSError("no such file")),              pytest.raises(ProviderCliError):
            ClaudeCliProvider(config)
