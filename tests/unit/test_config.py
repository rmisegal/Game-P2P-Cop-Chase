"""Tests for ConfigManager: load, dotted get, defaults, version validation."""

import pytest

from police_thief.exceptions import ConfigError, ConfigVersionError
from police_thief.shared.config import ConfigManager


class TestConfigManager:
    def test_loads_game_toml(self, config):
        assert config.get("board.size") == 10

    def test_dotted_get_nested(self, config):
        assert config.get("smell.decay_per_step") == 0.10
        assert config.get("network.my_port") == 8801

    def test_get_default_when_missing(self, config):
        assert config.get("board.moons", 42) == 42
        assert config.get("nosuch.section.key", "x") == "x"

    def test_get_list_value(self, config):
        assert config.get("positions.thief_start") == [5, 5]

    def test_rate_limits_loaded(self, config):
        assert config.rate_limits["queue"]["max_depth"] == 10
        assert config.service_limits("claude")["concurrent_max"] == 2

    def test_service_limits_falls_back_to_default(self, config):
        assert config.service_limits("unknown")["requests_per_minute"] == 600

    def test_bad_version_rejected(self, config_dir):
        toml = (config_dir / "game.toml").read_text(encoding="utf-8")
        (config_dir / "game.toml").write_text(
            toml.replace('version = "1.10"', 'version = "9.99"'), encoding="utf-8"
        )
        with pytest.raises(ConfigVersionError):
            ConfigManager(config_dir)

    def test_missing_config_dir_rejected(self, tmp_path):
        with pytest.raises(ConfigError):
            ConfigManager(tmp_path / "nope")

    def test_missing_rate_limits_rejected(self, config_dir):
        (config_dir / "rate_limits.json").unlink()
        with pytest.raises(ConfigError):
            ConfigManager(config_dir)
