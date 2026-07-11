"""Tests for the four JSON artifact builders — each dict must match the keys of
its Json-examples/ template and carry game_id / game_uid / links (Phase 5)."""

import json
import re
from pathlib import Path

from police_thief.report.artifacts import (
    build_config_artifact,
    build_declaration,
    build_log,
    build_result,
    config_filename,
    declaration_filename,
    log_filename,
    result_filename,
)

TEMPLATES = Path(__file__).parents[3] / "Json-examples"

SPEC = {
    "cpu_type": "Intel(R) Core(TM) i9", "cpu_freq_mhz": 2400, "cpu_cores": 8,
    "ram_gb": 16, "gpu_type": "NVIDIA GeForce RTX 2060", "vram_gb": 6,
    "os": "Windows 11", "gpu_cores_or_cuda": "CUDA",
}


def _template(name: str) -> dict:
    return json.loads((TEMPLATES / name).read_text(encoding="utf-8"))


def _identity(gid: str, name: str) -> dict:
    return {
        "group_id": gid, "group_name": name, "members": ["id-1", "id-2"],
        "repos": {"cop": "u/cop", "thief": "u/thief"},
        "mcp_servers": {"cop": "c.example", "thief": "t.example"},
        "llm_model": "claude-opus-4-8[1m]", "spec": dict(SPEC),
    }


def _summary() -> dict:
    return {
        "result": "capture", "winner": "cop", "steps": 4, "tokens_total": 32843,
        "group_name": "Team-Alpha", "sub_game_number": 1,
        "started_at": "2026-07-11T09:05:23+03:00", "duration_seconds": 99.9,
        "audit": {"passed": True, "verified_steps": 6, "failed_steps": []},
        "records": [{"payload": {"step": 1}, "nonce": "aa", "commit": "bb"}],
        "role": "cop",
    }


def _subgame(n: int, winner: str) -> dict:
    return {
        "sub_game_number": n, "roles": {"team-07": "cop", "team-13": "thief"},
        "started_at": "2026-07-11T09:05:23+03:00", "ended_at": "2026-07-11T09:07:03+03:00",
        "result": "capture", "winner_group": winner, "tie": False,
        "github_commit": {"team-07": "7cf3fc9", "team-13": "a1b2c3d"},
        "tokens": {"team-07": 100, "team-13": 200},
        "score": {"team-07": 20, "team-13": 5},
        "log_files": {"team-07": "a.json", "team-13": "b.json"},
        "audit": {"log_verified": True, "tampered": False},
    }


def _has_core(d: dict) -> None:
    assert d["game_id"] == "GID"
    assert d["game_uid"] == "UID"
    assert "_remark" in d["links"]
    assert d["links"]["declaration"] == "declaration_GID.json"


class TestDeclaration:
    def test_matches_template_keys(self):
        tmpl = _template("1-pre-game-declaration.json")
        d = build_declaration("GID", "UID", "Asia/Jerusalem", "2026-07-11T09:00:00+03:00",
                              "2026-07-11T10:45:00+03:00", 6, 200000,
                              _identity("team-07", "Alpha"), _identity("team-13", "Beta"))
        assert set(tmpl) <= set(d)
        _has_core(d)
        assert set(tmpl["groups"]) <= set(d["groups"])  # group_1, group_2

    def test_hardware_spec_uses_gpu_model(self):
        tmpl = _template("1-pre-game-declaration.json")
        d = build_declaration("GID", "UID", "Asia/Jerusalem", "s", "e", 6, 200000,
                              _identity("team-07", "Alpha"), _identity("team-13", "Beta"))
        hw = d["groups"]["group_1"]["hardware_spec"]
        assert set(hw) == set(tmpl["groups"]["group_1"]["hardware_spec"])
        assert "gpu_model" in hw and "gpu_type" not in hw
        assert hw["gpu_model"] == "NVIDIA GeForce RTX 2060"
        assert d["groups"]["group_1"]["signature"]  # per-group consensus signature


class TestConfig:
    def _shared(self) -> dict:
        tmpl = _template("2-agreed-config.json")
        overlay = {"schema_version", "game_id", "game_uid", "sub_game_number",
                   "links", "config_name", "config_sha256"}
        return {k: v for k, v in tmpl.items() if k not in overlay}

    def test_matches_template_keys(self):
        tmpl = _template("2-agreed-config.json")
        c = build_config_artifact(self._shared(), "GID", "UID", 3)
        assert set(tmpl) <= set(c)
        _has_core(c)
        assert c["sub_game_number"] == 3
        assert c["config_name"] == "config_GID_g03.json"

    def test_config_sha256_hex_and_deterministic(self):
        shared = self._shared()
        c1 = build_config_artifact(shared, "GID", "UID", 3)
        c2 = build_config_artifact(shared, "GID", "UID", 3)
        assert re.fullmatch(r"[0-9a-f]{64}", c1["config_sha256"])
        assert c1["config_sha256"] == c2["config_sha256"]


class TestLog:
    def test_matches_template_keys(self):
        tmpl = _template("3-game-log.json")
        log = build_log(_summary(), "GID", "UID", "team-07", "team-13")
        assert set(tmpl) <= set(log)
        _has_core(log)
        assert set(tmpl["summary"]) <= set(log["summary"])
        assert set(tmpl["mutual_agreement"]) <= set(log["mutual_agreement"])

    def test_summary_mapping(self):
        log = build_log(_summary(), "GID", "UID", "team-07", "team-13")
        s = log["summary"]
        assert s["winner_role"] == "cop"
        assert s["opponent_group_id"] == "team-13"
        assert s["group_id"] == "team-07"
        assert s["ended_at"].startswith("2026-07-11T09:07:")  # started + duration
        assert log["records"] == _summary()["records"]
        assert log["mutual_agreement"]["confirmed"] is True


class TestResult:
    AGG = {
        "total_score": {"team-07": 40, "team-13": 10},
        "sub_games_won": {"team-07": 2, "team-13": 0},
        "ties": 0, "winner_group": "team-07", "series_tie": False,
    }

    def _build(self) -> dict:
        return build_result("GID", "UID", ["team-07", "team-13"],
                            [_subgame(1, "team-07"), _subgame(2, "team-07")],
                            self.AGG, "deadbeef")

    def test_matches_template_keys(self):
        tmpl = _template("4-final-result.json")
        res = self._build()
        assert set(tmpl) <= set(res)
        _has_core(res)
        assert res["num_sub_games"] == 2
        assert res["groups"] == ["team-07", "team-13"]

    def test_final_result_reflects_aggregate(self):
        res = self._build()
        for key, value in self.AGG.items():
            assert res["final_result"][key] == value
        assert res["final_result"]["tokens_total_series"] == {"team-07": 200, "team-13": 400}
        assert res["mutual_agreement"]["sha256"] == "deadbeef"
        assert res["mutual_agreement"]["confirmed"] is True


def test_log_ended_at_falls_back_on_unparsable_start():
    summary = _summary() | {"started_at": "not-a-date"}
    log = build_log(summary, "GID", "UID", "team-07", "team-13")
    assert log["summary"]["ended_at"] == "not-a-date"  # echoed, not crashed


def test_filename_helpers():
    assert declaration_filename("G") == "declaration_G.json"
    assert config_filename("G", 3) == "config_G_g03.json"
    assert log_filename("G", 12) == "log_G_g12.json"
    assert result_filename("G") == "result_G.json"
