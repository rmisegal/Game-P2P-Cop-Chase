"""Tests for ConfigManager: load, dotted get, defaults, version validation."""

import json

import pytest

from police_thief.exceptions import ConfigError, ConfigVersionError
from police_thief.shared.config import ConfigManager

SHARED_GAME = {
    "schema_version": "1.1",
    "board_and_agents": {"grid_size": 7, "thief_start": [3, 3], "cop_start": [0, 0]},
    "movement_and_barriers": {
        "move_set": ["N", "S", "E", "W", "STAY"],
        "max_barriers": 14,
        "max_moves": 35,
        "survival_threshold": 35,
    },
    "scoring": {
        "capture_cop": 20,
        "capture_thief": 5,
        "survival_cop": 5,
        "survival_thief": 10,
        "tie_score": 2,
    },
    "pheromones": {
        "pheromone_center_intensity": 0.9,
        "pheromone_decay": 0.10,
        "pheromone_grid_size": 5,
    },
    "network_and_league": {"num_games": 1},
}


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


class TestSharedJsonOverlay:
    """A shared game.json overlays the local TOML game-terms (Appendix-F schema)."""

    @staticmethod
    def _with_shared(config_dir, shared=None):
        (config_dir / "game.json").write_text(
            json.dumps(shared or SHARED_GAME), encoding="utf-8"
        )
        return ConfigManager(config_dir)

    def test_no_shared_is_backward_compatible(self, config):
        # No game.json present -> pure TOML behaviour (board.size stays 10).
        assert config.get("board.size") == 10
        assert config.shared == {}

    def test_shared_overrides_game_terms(self, config_dir):
        cfg = self._with_shared(config_dir)
        assert cfg.get("board.size") == 7  # 10 (toml) -> 7 (shared)
        assert cfg.get("positions.thief_start") == [3, 3]
        assert cfg.get("positions.cop_start") == [0, 0]
        assert cfg.get("rules.barriers_max") == 14
        assert cfg.get("rules.max_moves") == 35
        assert cfg.get("rules.max_steps") == 35
        assert cfg.get("rules.move_set") == ["N", "S", "E", "W", "STAY"]
        assert cfg.get("smell.emit_intensity") == 0.9
        assert cfg.get("smell.decay_per_step") == 0.10
        assert cfg.get("smell.grid_size") == 5
        assert cfg.get("game.num_games") == 1

    def test_shared_adds_scoring_section(self, config_dir):
        cfg = self._with_shared(config_dir)
        assert cfg.get("scoring.capture_cop") == 20
        assert cfg.get("scoring.survival_thief") == 10
        assert cfg.get("scoring.tie_score") == 2

    def test_local_only_keys_untouched_by_shared(self, config_dir):
        cfg = self._with_shared(config_dir)
        assert cfg.get("network.my_port") == 8801  # local-only, not overlaid
        assert cfg.get("game.group_name") == "TestGroup"
        assert cfg.get("belief.smell_trust_weight") == 4.0

    def test_shared_raw_exposed(self, config_dir):
        cfg = self._with_shared(config_dir)
        assert cfg.shared["board_and_agents"]["grid_size"] == 7

    def test_partial_shared_overlay(self, config_dir):
        # Only board section present -> other terms keep TOML values.
        cfg = self._with_shared(config_dir, {"board_and_agents": {"grid_size": 9}})
        assert cfg.get("board.size") == 9
        assert cfg.get("rules.max_steps") == 50  # untouched TOML value
