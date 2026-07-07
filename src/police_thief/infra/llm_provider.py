# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Claude CLI provider: `type prompt.txt | claude -p --output-format json`.

Auth is the CLI's browser LOGIN (subscription), never an API key. The proven
basic-clis pattern: ANTHROPIC_API_KEY and friends are STRIPPED from the
subprocess env — if present, the CLI silently switches to API-key billing.
"""

import contextlib
import os
import platform
import subprocess
import tempfile

from police_thief.exceptions import (
    ProviderAuthError,
    ProviderCliError,
    ProviderParseError,
    ProviderTimeoutError,
)
from police_thief.shared.config import ConfigManager

# Keys that would hijack CLI auth away from the browser-login token.
STRIP_KEYS = [
    "ANTHROPIC_API_KEY",
    "CLAUDECODE",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "API_TIMEOUT_MS",
]


class ClaudeCliProvider:
    """Send a prompt to the claude CLI and return the text result."""

    def __init__(self, config: ConfigManager):
        self._executable = config.get("llm.executable", "claude")
        self._args = list(config.get("llm.args", ["-p", "--output-format", "json"]))
        self._model = config.get("llm.model", "") or "cli-default"
        if self._model != "cli-default":
            self._args += ["--model", f'"{self._model}"']
        self.last_usage: dict = {"model": self._model, "in": 0, "out": 0, "total": 0}
        self.tokens_consumed = 0  # cumulative, bumped ONLY when a reply is parsed
        self._timeout = config.get("llm.timeout_seconds", 120)
        self._response_field = config.get("llm.response_field", "result")
        self._verify_cli()

    def _verify_cli(self) -> str:
        try:
            result = subprocess.run(
                f"{self._executable} --version", capture_output=True, text=True,
                timeout=10, shell=True, encoding="utf-8", errors="replace",
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            pass
        raise ProviderCliError(
            f"CLI '{self._executable}' not found/working; install it and run `claude` once to login."
        )

    def send(self, prompt: str) -> str:
        """Pipe the prompt through the CLI (login auth) and extract the result."""
        temp_path = self._write_temp(prompt)
        try:
            cat = "type" if platform.system() == "Windows" else "cat"
            cmd = f'{cat} "{temp_path}" | {self._executable} {" ".join(self._args)}'
            raw = self._run(cmd)
            return self._extract(raw)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(temp_path)

    @staticmethod
    def _write_temp(prompt: str) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(prompt)
            return f.name

    def _run(self, cmd: str) -> str:
        env = {k: v for k, v in os.environ.items() if k not in STRIP_KEYS}
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self._timeout,
                shell=True, encoding="utf-8", errors="replace", env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderTimeoutError(f"claude CLI timed out after {self._timeout}s") from exc
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or "Unknown CLI error"
            if "auth" in error.lower() or "login" in error.lower():
                raise ProviderAuthError(f"Authentication required: {error}")
            raise ProviderCliError(error)
        return result.stdout

    def _extract(self, raw: str) -> str:
        import json

        try:
            wrapper = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderParseError(f"CLI returned non-JSON: {raw[:200]}") from exc
        self._record_usage(wrapper)
        content = wrapper.get(self._response_field, "")
        return self._strip_fences(content) if isinstance(content, str) else str(content)

    def _record_usage(self, wrapper: dict) -> None:
        """Capture token usage from the CLI's JSON wrapper for the sealed log."""
        usage = wrapper.get("usage") or {}
        tokens_in = sum(usage.get(key, 0) or 0 for key in (
            "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        tokens_out = usage.get("output_tokens", 0) or 0
        self.last_usage = {"model": self._model, "in": tokens_in,
                           "out": tokens_out, "total": tokens_in + tokens_out}
        self.tokens_consumed += tokens_in + tokens_out

    @staticmethod
    def _strip_fences(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            body = [line for line in lines[1:] if not line.strip().startswith("```")]
            return "\n".join(body).strip()
        return stripped
