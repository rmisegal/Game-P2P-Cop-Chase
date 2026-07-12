# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Verbal-game (trash-talk) mode + model for the GUI, per book Table 22.

The MOVE is always pure Python; only the banter may use an LLM. This maps the
private `trash_talk.provider` to the human game mode and the model to display:
`template` -> Python / "None"; `ollama` -> Ollama / model; `claude_api` and
`claude_cli` -> Remote LLM / model. Pure and headless-testable (no Tk)."""

PYTHON_MODE = "Python (template)"
OLLAMA_MODE = "Ollama"
REMOTE_MODE = "Remote LLM"

_OLLAMA_DEFAULT_MODEL = "llama3.2"
_CLAUDE_API_DEFAULT_MODEL = "claude-haiku-4-5"


def mode_and_model(config) -> tuple[str, str]:
    """Return (game_mode, model_label) for the Table-22 verbal-game mode.

    model_label is the literal string "None" for the template (Python) mode, so
    the GUI never claims an LLM the game is not using."""
    get = config.get if config is not None else (lambda _k, d=None: d)
    provider = str(get("trash_talk.provider", "template") or "template").lower()
    model = str(get("trash_talk.model", "") or "")
    if provider == "ollama":
        return OLLAMA_MODE, model or _OLLAMA_DEFAULT_MODEL
    if provider == "claude_api":
        return REMOTE_MODE, model or _CLAUDE_API_DEFAULT_MODEL
    if provider == "claude_cli":
        # claude_cli reuses this peer's own claude -p provider (llm.model).
        return REMOTE_MODE, model or str(get("llm.model", "") or "claude-cli")
    return PYTHON_MODE, "None"


_NO_LLM_MODELS = {"", "-", "none", "stub", "template"}


def mode_from_recorded_model(model: str) -> tuple[str, str]:
    """Replay side: classify a recorded per-step model string into (mode, label).
    A template/stub run is reported as Python / "None"; anything else names its
    model under the Remote-LLM mode."""
    text = str(model or "").strip()
    if text.lower() in _NO_LLM_MODELS:
        return PYTHON_MODE, "None"
    return REMOTE_MODE, text
