"""Series orchestration + emitter wiring, driven in-process over a fake transport.

Two full peers (distinct group ids) play a series with the stub LLM; we assert the
four JSON files are written, share one game_uid, alternate roles across sub-games,
and that a single aggregated result carries per-group scores. Deterministic and
fast (no real MCP servers) — this is the reliable Phase-6 gate; the real-MCP
localhost variant lives in tests/integration/test_mcp_match.py.
"""

import json
import queue
import threading

import pytest

from police_thief.constants import Role
from police_thief.sdk.sdk import SimulationSdk
from police_thief.sdk.series import role_for

GAME_TOML = """
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
my_port = 8801
opponent_url = "http://127.0.0.1:8802/mcp"
turn_timeout_seconds = 3
poll_interval_seconds = 0.01
connect_timeout_seconds = 5
retry_interval_seconds = 0.1
audit_send_timeout_seconds = 2
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

RATE_LIMITS = {
    "version": "1.10",
    "services": {"claude": {"requests_per_minute": 600, "concurrent_max": 2,
                            "retry_after_seconds": 0, "max_retries": 3}},
    "default": {"requests_per_minute": 600, "concurrent_max": 2,
                "retry_after_seconds": 0, "max_retries": 1},
    "queue": {"max_depth": 10, "drain_interval_seconds": 0.01, "timeout_seconds": 2},
}


def _shared(num_games: int) -> dict:
    return {
        "schema_version": "1.1",
        "agreed_between": ["team-police", "team-thief"],
        "board_and_agents": {"grid_size": 7, "thief_start": [3, 3], "cop_start": [0, 0]},
        "movement_and_barriers": {"move_set": ["N", "S", "E", "W", "STAY"],
                                  "max_barriers": 14, "max_moves": 12, "survival_threshold": 12},
        "scoring": {"capture_cop": 20, "capture_thief": 5, "survival_cop": 5,
                    "survival_thief": 10, "tie_score": 2},
        "pheromones": {"pheromone_center_intensity": 0.9, "pheromone_decay": 0.10,
                       "pheromone_grid_size": 5},
        "network_and_league": {"num_games": num_games, "token_budget_per_series": 150000},
    }


def _write_config(root, name, gid, num_games):
    cfg = root
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "game.toml").write_text(GAME_TOML.format(name=name, gid=gid), encoding="utf-8")
    (cfg / "rate_limits.json").write_text(json.dumps(RATE_LIMITS), encoding="utf-8")
    (cfg / "game.json").write_text(json.dumps(_shared(num_games)), encoding="utf-8")
    return cfg


class FakeTransport:
    """One side of a queue-pair 'network', reused across all sub-games."""

    def __init__(self, inbox, outbox):
        self._inbox, self._outbox = inbox, outbox

    def exchange_agreement(self, signed):
        self._outbox.put(("agreement", signed))
        return self._inbox.get(timeout=10)[1]

    def send_turn(self, message):
        self._outbox.put(("turn", message))

    def poll_turn(self, timeout):
        try:
            kind, payload = self._inbox.get(timeout=timeout)
            return payload if kind == "turn" else None
        except queue.Empty:
            return None

    def exchange_audit(self, payload):
        self._outbox.put(("audit", payload))
        try:
            return self._inbox.get(timeout=10)[1]
        except queue.Empty:
            return None


def _play(tmp_path, num_games):
    a_to_b, b_to_a = queue.Queue(), queue.Queue()
    police_dir = _write_config(tmp_path / "police_cfg", "Police", "team-police", num_games)
    thief_dir = _write_config(tmp_path / "thief_cfg", "Thief", "team-thief", num_games)
    police_sdk = SimulationSdk(police_dir, workdir=tmp_path / "police")
    thief_sdk = SimulationSdk(thief_dir, workdir=tmp_path / "thief")
    results: dict = {}

    def run(name, sdk, role, tr):
        results[name] = sdk.run_peer(role, stub_llm=True, transport=tr)

    threads = [
        threading.Thread(target=run,
                         args=("police", police_sdk, "police", FakeTransport(a_to_b, b_to_a)),
                         daemon=True),
        threading.Thread(target=run,
                         args=("thief", thief_sdk, "thief", FakeTransport(b_to_a, a_to_b)),
                         daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
        assert not t.is_alive(), "series did not finish"
    return results


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_role_for_alternates():
    assert role_for(Role.POLICE, 1) is Role.POLICE
    assert role_for(Role.POLICE, 2) is Role.THIEF
    assert role_for(Role.THIEF, 1) is Role.THIEF
    assert role_for(Role.THIEF, 2) is Role.POLICE


class TestSingleGameSeries:
    def test_four_files_share_one_game_uid(self, tmp_path):
        _play(tmp_path, num_games=1)
        logs = tmp_path / "police" / "logs" / "team-police"
        gid = "team-police-vs-team-thief"
        files = [logs / f"declaration_{gid}.json", logs / f"config_{gid}_g01.json",
                 logs / f"log_{gid}_g01.json", logs / f"result_{gid}.json"]
        for f in files:
            assert f.exists(), f
        uids = {_load(f)["game_uid"] for f in files}
        assert len(uids) == 1  # one shared game_uid across all four files

    def test_both_peers_agree_on_ids_and_audit(self, tmp_path):
        results = _play(tmp_path, num_games=1)
        p_uid = results["police"]["result"]["game_uid"]
        t_uid = results["thief"]["result"]["game_uid"]
        assert p_uid == t_uid  # deterministic, no exchange needed
        gid = "team-police-vs-team-thief"
        p_log = _load(tmp_path / "police" / "logs" / "team-police" / f"log_{gid}_g01.json")
        assert p_log["summary"]["audit"]["passed"] is True


class TestTwoGameSeries:
    def test_role_alternation_and_aggregate(self, tmp_path):
        _play(tmp_path, num_games=2)
        gid = "team-police-vs-team-thief"
        logs = tmp_path / "police" / "logs" / "team-police"
        g01 = _load(logs / f"log_{gid}_g01.json")
        g02 = _load(logs / f"log_{gid}_g02.json")
        assert g01["summary"]["role"] == "police"     # natural role on odd
        assert g02["summary"]["role"] == "thief"       # opposite on even
        assert g01["summary"]["sub_game_number"] == 1
        assert g02["summary"]["sub_game_number"] == 2

    def test_single_aggregated_result_with_group_scores(self, tmp_path):
        _play(tmp_path, num_games=2)
        gid = "team-police-vs-team-thief"
        result = _load(tmp_path / "police" / "logs" / "team-police" / f"result_{gid}.json")
        assert result["num_sub_games"] == 2
        assert len(result["sub_games"]) == 2
        total = result["final_result"]["total_score"]
        assert set(total) == {"team-police", "team-thief"}  # both groups scored
        # roles swap between the two sub-games from each group's perspective
        assert result["sub_games"][0]["roles"]["team-police"] == "police"
        assert result["sub_games"][1]["roles"]["team-police"] == "thief"


@pytest.mark.parametrize("num_games", [1, 2])
def test_series_matches_across_peers(tmp_path, num_games):
    """Both peers write an identical aggregated final_result (mutual agreement)."""
    results = _play(tmp_path, num_games)
    assert results["police"]["result"]["final_result"]["total_score"] == \
        results["thief"]["result"]["final_result"]["total_score"]
    assert results["police"]["result"]["mutual_agreement"]["sha256"] == \
        results["thief"]["result"]["mutual_agreement"]["sha256"]
