"""Tests for the CLI: argument parsing and delegation to the SDK."""

from unittest.mock import patch

import pytest

from police_thief.cli import main


class TestCli:
    def test_peer_delegates_to_sdk(self, config_dir):
        with patch("police_thief.cli.SimulationSdk") as sdk_cls:
            sdk = sdk_cls.return_value
            sdk.run_peer.return_value = {
                "summary": {"result": "capture", "winner": "police", "steps": 5},
                "email": {"sent": False, "reason": "disabled"},
                "log_path": "logs/police_match.json",
            }
            code = main(["peer", "--role", "police", "--config", str(config_dir),
                         "--stub-llm", "--no-gui"])
        assert code == 0
        sdk.run_peer.assert_called_once()
        assert sdk.run_peer.call_args.kwargs["stub_llm"] is True

    def test_replay_delegates_to_gui(self, config_dir, tmp_path):
        log = tmp_path / "x.json"
        log.write_text("{}", encoding="utf-8")
        with patch("police_thief.cli.SimulationSdk") as sdk_cls, \
             patch("police_thief.cli._launch_replay") as replay:
            sdk_cls.return_value.load_log.return_value = {"summary": {}}
            code = main(["replay", "--log", str(log), "--config", str(config_dir)])
        assert code == 0
        replay.assert_called_once()

    def test_bad_role_rejected(self, config_dir):
        with pytest.raises(SystemExit):
            main(["peer", "--role", "wizard", "--config", str(config_dir)])

    def test_no_command_shows_help(self):
        assert main([]) == 2
