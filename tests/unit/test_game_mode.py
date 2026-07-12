"""Verbal-game mode + model for the GUI (book Table 22): template -> Python/None,
ollama/claude_api/claude_cli -> the real model."""

from police_thief.gui.game_mode import (
    OLLAMA_MODE,
    PYTHON_MODE,
    REMOTE_MODE,
    mode_and_model,
    mode_from_recorded_model,
)


class Cfg:
    def __init__(self, mapping):
        self._m = mapping

    def get(self, key, default=None):
        return self._m.get(key, default)


def test_default_template_is_python_none():
    assert mode_and_model(Cfg({})) == (PYTHON_MODE, "None")


def test_template_explicit_is_python_none():
    assert mode_and_model(Cfg({"trash_talk.provider": "template"})) == (PYTHON_MODE, "None")


def test_ollama_shows_its_model():
    cfg = Cfg({"trash_talk.provider": "ollama", "trash_talk.model": "llama3.1"})
    assert mode_and_model(cfg) == (OLLAMA_MODE, "llama3.1")


def test_ollama_defaults_model_when_unset():
    mode, model = mode_and_model(Cfg({"trash_talk.provider": "ollama"}))
    assert mode == OLLAMA_MODE and model == "llama3.2"


def test_claude_api_is_remote_llm():
    cfg = Cfg({"trash_talk.provider": "claude_api", "trash_talk.model": "claude-haiku-4-5"})
    assert mode_and_model(cfg) == (REMOTE_MODE, "claude-haiku-4-5")


def test_claude_cli_uses_peer_llm_model():
    cfg = Cfg({"trash_talk.provider": "claude_cli", "llm.model": "claude-opus-4-8"})
    assert mode_and_model(cfg) == (REMOTE_MODE, "claude-opus-4-8")


def test_none_config_is_python():
    assert mode_and_model(None) == (PYTHON_MODE, "None")


def test_recorded_stub_is_python_none():
    assert mode_from_recorded_model("stub") == (PYTHON_MODE, "None")
    assert mode_from_recorded_model("") == (PYTHON_MODE, "None")
    assert mode_from_recorded_model("template") == (PYTHON_MODE, "None")


def test_recorded_real_model_is_remote():
    assert mode_from_recorded_model("claude-haiku-4-5") == (REMOTE_MODE, "claude-haiku-4-5")
