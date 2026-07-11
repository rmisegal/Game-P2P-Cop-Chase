"""Shared fixtures: temp config files and a ConfigManager wired to them."""

import json
from pathlib import Path

import pytest

GAME_TOML = """
version = "1.10"
[game]
group_name = "TestGroup"
sub_game_number = 1
group_id = "test-group"
members = ["id-1", "id-2"]
repos = { cop = "u/cop", thief = "u/thief" }
mcp_servers = { cop = "c.example", thief = "t.example" }
[board]
size = 10
[smell]
grid_size = 5
decay_per_step = 0.10
min_center_intensity = 0.5
emit_intensity = 0.9
[rules]
max_steps = 50
barriers_max = 20
[positions]
thief_start = [5, 5]
cop_start = [7, 5]
[play]
step_speed_seconds = 0.0
setting = "New York"
seed = 1234
[belief]
smell_trust_weight = 4.0
[paths]
logs_dir = "logs"
log_filename = "{role}_match.json"
[network]
host = "127.0.0.1"
my_port = 8801
opponent_url = "http://127.0.0.1:8802/mcp"
turn_timeout_seconds = 2
poll_interval_seconds = 0.01
connect_timeout_seconds = 5
retry_interval_seconds = 0.1
audit_send_timeout_seconds = 2
[llm]
provider = "claude"
executable = "claude"
model = "claude-opus-4-8[1m]"
args = ["-p", "--output-format", "json"]
timeout_seconds = 10
response_field = "result"
step_deadline_seconds = 5
short_prompt_threshold_seconds = 2
[email]
recipient = "someone@example.com"
mode = "draft"
enabled = false
timeout_seconds = 60
draft_script = "C:/fake/draft.py"
skill_lib = "C:/fake/_lib"
"""

RATE_LIMITS = {
    "version": "1.10",
    "services": {
        "claude": {
            "requests_per_minute": 600,
            "concurrent_max": 2,
            "retry_after_seconds": 0,
            "max_retries": 3,
        }
    },
    "default": {
        "requests_per_minute": 600,
        "concurrent_max": 2,
        "retry_after_seconds": 0,
        "max_retries": 1,
    },
    "queue": {"max_depth": 10, "drain_interval_seconds": 0.01, "timeout_seconds": 2},
}


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Write valid game.toml + rate_limits.json into a temp config dir."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "game.toml").write_text(GAME_TOML, encoding="utf-8")
    (cfg / "rate_limits.json").write_text(json.dumps(RATE_LIMITS), encoding="utf-8")
    return cfg


@pytest.fixture
def config(config_dir: Path):
    """A ConfigManager loaded from the temp config dir."""
    from police_thief.shared.config import ConfigManager

    return ConfigManager(config_dir)
