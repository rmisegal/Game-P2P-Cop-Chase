"""Pure helpers behind the Visual Replay Player: sibling-opponent log loading,
sub-game discovery, and the per-step move-label mapping."""

import json

from police_thief.gui.replay_data import (
    discover_subgames,
    frozen_message,
    move_labels,
    opponent_positions,
    subgame_log_path,
)

GAME_ID = "team-a-vs-team-b"


def _write_log(path, role, group, positions, opponent):
    records = [{"payload": {"step": 0, "type": "system_spec"}}]
    records += [{"payload": {"step": i + 1, "position": p}}
                for i, p in enumerate(positions)]
    path.write_text(json.dumps({
        "game_id": GAME_ID,
        "summary": {"role": role, "group_id": group,
                    "opponent_group_id": opponent, "sub_game_number": 1},
        "records": records,
    }), encoding="utf-8")


def test_move_labels_maps_payload_fields():
    payload = {"hint": "hi", "model": "stub", "tokens_step": 10, "tokens_total": 20,
               "response_seconds": 1.5, "random_move": True, "verdict": "bluff"}
    labels = move_labels(payload, "abcdef0123456789abcdef0123456789", "verified OK")
    assert labels["hint_out"] == "hi"
    assert labels["tokens"] == "10 / 20"
    assert "[RANDOM]" in labels["llm_time"]
    assert labels["verdict"] == "bluff (revealed)"
    assert labels["commit"].endswith("[verified OK]")


def test_move_labels_defaults_when_empty():
    labels = move_labels({}, "-", "-")
    assert labels["hint_out"] == "-"
    assert labels["tokens"] == "0 / 0"
    assert "[RANDOM]" not in labels["llm_time"]


def test_frozen_message_none_while_both_move():
    assert frozen_message(3, my_len=34, my_role="police",
                          opp_len=35, opp_role="thief") is None


def test_frozen_message_names_shorter_track():
    # police=34, thief=35: at step index 34 police has run out and freezes.
    msg = frozen_message(34, my_len=34, my_role="police",
                         opp_len=35, opp_role="thief")
    assert msg == "missing police step (frozen)"


def test_frozen_message_no_opponent_log():
    assert frozen_message(3, my_len=2, my_role="police",
                          opp_len=0, opp_role="thief") == "missing police step (frozen)"


def test_discover_subgames_finds_and_sorts(tmp_path):
    group = tmp_path / "team-a"
    group.mkdir()
    for sub in (2, 1):
        _write_log(group / f"log_{GAME_ID}_g{sub:02d}.json", "police", "team-a",
                   [[0, 0]], "team-b")
    log_path = group / f"log_{GAME_ID}_g01.json"
    data = json.loads(log_path.read_text(encoding="utf-8"))
    assert discover_subgames(str(log_path), data) == [1, 2]


def test_discover_subgames_empty_without_path():
    assert discover_subgames(None, {"game_id": GAME_ID}) == []


def test_subgame_log_path_zero_pads(tmp_path):
    log_path = tmp_path / "team-a" / f"log_{GAME_ID}_g01.json"
    result = subgame_log_path(str(log_path), {"game_id": GAME_ID}, 3)
    assert result.name == f"log_{GAME_ID}_g03.json"


def test_opponent_positions_reads_sibling_log(tmp_path):
    (tmp_path / "team-a").mkdir()
    (tmp_path / "team-b").mkdir()
    my_path = tmp_path / "team-a" / f"log_{GAME_ID}_g01.json"
    _write_log(my_path, "police", "team-a", [[0, 0], [1, 0]], "team-b")
    _write_log(tmp_path / "team-b" / f"log_{GAME_ID}_g01.json", "thief", "team-b",
               [[6, 6], [5, 6]], "team-a")
    data = json.loads(my_path.read_text(encoding="utf-8"))
    assert opponent_positions(str(my_path), data) == [[6, 6], [5, 6]]


def test_opponent_positions_missing_sibling_returns_empty(tmp_path):
    (tmp_path / "team-a").mkdir()
    my_path = tmp_path / "team-a" / f"log_{GAME_ID}_g01.json"
    _write_log(my_path, "police", "team-a", [[0, 0]], "team-b")
    data = json.loads(my_path.read_text(encoding="utf-8"))
    assert opponent_positions(str(my_path), data) == []
    assert opponent_positions(None, data) == []
