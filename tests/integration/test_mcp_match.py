"""End-to-end distributed match over REAL MCP HTTP servers on two ports.

Mimics two students on the internet: each peer has only its own server and
the other's URL. No central server exists.
"""

import json
import threading

import pytest

from police_thief.constants import Role
from police_thief.infra.mcp_client import McpTransport
from police_thief.infra.mcp_server import start_peer_server

THIEF_PORT = 18801
POLICE_PORT = 18802
HOST = "127.0.0.1"


class GarbageLlm:
    def send(self, prompt: str) -> str:
        return "not json -> deterministic fallback policy"


@pytest.fixture(scope="module")
def peer_pair():
    thief_in = start_peer_server("thief", HOST, THIEF_PORT)
    police_in = start_peer_server("police", HOST, POLICE_PORT)
    thief_transport = McpTransport(
        f"http://{HOST}:{POLICE_PORT}/mcp", thief_in, connect_timeout=30)
    police_transport = McpTransport(
        f"http://{HOST}:{THIEF_PORT}/mcp", police_in, connect_timeout=30)
    return thief_transport, police_transport


@pytest.mark.slow
def test_full_match_over_real_mcp(config, peer_pair):
    from police_thief.peer.runtime import PeerRuntime

    thief_transport, police_transport = peer_pair
    thief = PeerRuntime(Role.THIEF, config, GarbageLlm(), thief_transport)
    police = PeerRuntime(Role.POLICE, config, GarbageLlm(), police_transport)

    results: dict = {}
    threads = [
        threading.Thread(target=lambda: results.update(police=police.run()), daemon=True),
        threading.Thread(target=lambda: results.update(thief=thief.run()), daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
        assert not t.is_alive(), "distributed match did not finish"

    assert results["thief"]["result"] == results["police"]["result"]
    assert results["thief"]["winner"] == results["police"]["winner"]
    assert results["thief"]["audit"]["passed"] is True
    assert results["police"]["audit"]["passed"] is True


# ---- Series wiring over real MCP (SimulationSdk, num_games=1) ----------------

_SERIES_TOML = """
version = "1.10"
[game]
group_name = "{name}"
group_id = "{gid}"
members = ["m-1", "m-2"]
repos = {{ cop = "u/cop", thief = "u/thief" }}
mcp_servers = {{ cop = "c.example", thief = "t.example" }}
[board]
size = 7
[smell]
grid_size = 5
decay_per_step = 0.10
min_center_intensity = 0.5
emit_intensity = 0.9
[rules]
max_steps = 12
barriers_max = 14
[positions]
thief_start = [3, 3]
cop_start = [0, 0]
[play]
step_speed_seconds = 0.0
setting = "New York"
seed = 7
[belief]
smell_trust_weight = 4.0
[paths]
logs_dir = "logs"
log_filename = "{{role}}_match.json"
[network]
host = "127.0.0.1"
my_port = {port}
opponent_url = "http://127.0.0.1:{opp}/mcp"
turn_timeout_seconds = 30
poll_interval_seconds = 0.05
connect_timeout_seconds = 20
retry_interval_seconds = 0.2
audit_send_timeout_seconds = 5
[llm]
provider = "claude"
executable = "claude"
model = "claude-opus-4-8[1m]"
args = ["-p"]
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

_RATE = {
    "version": "1.10",
    "services": {"claude": {"requests_per_minute": 600, "concurrent_max": 2,
                            "retry_after_seconds": 0, "max_retries": 3}},
    "default": {"requests_per_minute": 600, "concurrent_max": 2,
                "retry_after_seconds": 0, "max_retries": 1},
    "queue": {"max_depth": 10, "drain_interval_seconds": 0.01, "timeout_seconds": 2},
}

_SHARED = {
    "schema_version": "1.1", "agreed_between": ["team-police", "team-thief"],
    "board_and_agents": {"grid_size": 7, "thief_start": [3, 3], "cop_start": [0, 0]},
    "movement_and_barriers": {"move_set": ["N", "S", "E", "W", "STAY"],
                              "max_barriers": 14, "max_moves": 12, "survival_threshold": 12},
    "scoring": {"capture_cop": 20, "capture_thief": 5, "survival_cop": 5,
                "survival_thief": 10, "tie_score": 2},
    "pheromones": {"pheromone_center_intensity": 0.9, "pheromone_decay": 0.10,
                   "pheromone_grid_size": 5},
    "network_and_league": {"num_games": 1, "token_budget_per_series": 150000},
}


def _series_config(root, name, gid, port, opp):
    root.mkdir(parents=True, exist_ok=True)
    (root / "game.toml").write_text(
        _SERIES_TOML.format(name=name, gid=gid, port=port, opp=opp), encoding="utf-8")
    (root / "rate_limits.json").write_text(json.dumps(_RATE), encoding="utf-8")
    (root / "game.json").write_text(json.dumps(_SHARED), encoding="utf-8")
    return root


@pytest.mark.slow
def test_series_emits_four_files_over_real_mcp(peer_pair, tmp_path):
    """One-game series over real MCP writes the four artifacts sharing one uid."""
    from police_thief.sdk.sdk import SimulationSdk

    thief_transport, police_transport = peer_pair
    police_cfg = _series_config(tmp_path / "pc", "Police", "team-police", POLICE_PORT, THIEF_PORT)
    thief_cfg = _series_config(tmp_path / "tc", "Thief", "team-thief", THIEF_PORT, POLICE_PORT)
    police_sdk = SimulationSdk(police_cfg, workdir=tmp_path / "police")
    thief_sdk = SimulationSdk(thief_cfg, workdir=tmp_path / "thief")

    results: dict = {}
    threads = [
        threading.Thread(
            target=lambda: results.update(
                police=police_sdk.run_peer("police", stub_llm=True, transport=police_transport)),
            daemon=True),
        threading.Thread(
            target=lambda: results.update(
                thief=thief_sdk.run_peer("thief", stub_llm=True, transport=thief_transport)),
            daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
        assert not t.is_alive(), "series over real MCP did not finish"

    gid = "team-police-vs-team-thief"
    logs = tmp_path / "police" / "logs"
    files = [logs / f"declaration_{gid}.json", logs / f"config_{gid}_g01.json",
             logs / f"log_{gid}_g01.json", logs / f"result_{gid}.json"]
    uids = set()
    for f in files:
        assert f.exists(), f
        uids.add(json.loads(f.read_text(encoding="utf-8"))["game_uid"])
    assert len(uids) == 1  # one shared game_uid across all four files
    assert results["police"]["result"]["mutual_agreement"]["sha256"] == \
        results["thief"]["result"]["mutual_agreement"]["sha256"]
