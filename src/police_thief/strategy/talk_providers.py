# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Resolve the trash-talk provider from the [trash_talk] config block, and the
network 'askers' for the opt-in LLM providers.

Providers:
  * ``template``    (default) - pure Python, zero tokens, instant, offline.
  * ``claude_cli``  - reuse the peer's existing ``claude -p`` provider (expensive:
                      still pays the Claude Code system-prompt overhead per call).
  * ``claude_api``  - the Anthropic SDK with a SMALL model (default Haiku) - ~200
                      tokens/call. Needs `anthropic` installed + an API key / login.
  * ``ollama``      - a local model via the Ollama HTTP API - free, no RPM limit.
"""

import json
import logging
import random
import urllib.request

from police_thief.strategy.trash_talk import LlmTrashTalk, TrashTalk

logger = logging.getLogger(__name__)

_OLLAMA_DEFAULT = "http://localhost:11434/api/generate"


def resolve_trash_talk(config, rng: random.Random, llm=None) -> TrashTalk:
    """Build the trash-talk provider. Default (and any unknown value) is the free
    ``template`` provider, so the shipped game runs fast and offline."""
    get = config.get if config is not None else (lambda _k, d=None: d)
    provider = str(get("trash_talk.provider", "template")).lower()
    every = get("trash_talk.every_n_steps", 1)
    model = get("trash_talk.model", "")

    if provider == "template":
        return TrashTalk(rng)
    if provider == "claude_cli":
        if llm is None:
            logger.warning("trash_talk.provider=claude_cli but no llm; using template")
            return TrashTalk(rng)
        return LlmTrashTalk(lambda prompt, _d=None: llm.send(prompt), rng, every, model)
    if provider == "ollama":
        url = get("trash_talk.ollama_url", _OLLAMA_DEFAULT)
        return LlmTrashTalk(_ollama_asker(model or "llama3.2", url), rng, every, model)
    if provider == "claude_api":
        return LlmTrashTalk(_claude_api_asker(model or "claude-haiku-4-5"), rng, every, model)

    logger.warning("unknown trash_talk.provider %r; using template", provider)
    return TrashTalk(rng)


def _ollama_asker(model: str, url: str):
    """A local Ollama call (stdlib only, no extra dependency)."""
    def ask(prompt: str, deadline=None) -> str:
        body = json.dumps(
            {"model": model, "prompt": prompt, "stream": False, "format": "json"}
        ).encode()
        request = urllib.request.Request(  # noqa: S310 - fixed localhost Ollama endpoint
            url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=deadline or 30) as response:  # noqa: S310
            return json.loads(response.read())["response"]
    return ask


def _claude_api_asker(model: str):
    """A short Anthropic Messages API call using a SMALL model (default Haiku).
    `anthropic` is imported lazily so it stays an optional dependency."""
    def ask(prompt: str, deadline=None) -> str:
        import anthropic  # optional dep; only needed for provider=claude_api

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in message.content if block.type == "text")
    return ask
