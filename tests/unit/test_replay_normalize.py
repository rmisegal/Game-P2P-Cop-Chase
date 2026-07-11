"""normalize_log accepts both the legacy match log and the standardized template log."""

from police_thief.gui.replay import normalize_log


def test_legacy_log_shape():
    log = {
        "summary": {
            "role": "police", "result": "capture", "winner": "police",
            "records": [{"payload": {"step": 1, "position": [0, 0]}}],
            "history": [{"smell_grid": {}}],
            "my_log": [{"position": [0, 0], "barrier": None}],
            "audit": {"passed": True}, "group_name": "G", "duration_seconds": 5,
        }
    }
    view = normalize_log(log)
    assert view["records"] and view["history"] and view["my_log"]
    assert view["winner"] == "police"
    assert view["group"] == "G"
    assert view["role"] == "police"


def test_standardized_template_log_shape():
    log = {
        "game_uid": "u",
        "records": [
            {"payload": {"step": 0, "type": "system_spec"}},
            {"payload": {"step": 1, "position": [3, 3]}},
            {"payload": {"step": 2, "position": [2, 3]}},
        ],
        "summary": {
            "role": "cop", "result": "capture", "winner_role": "cop",
            "group_id": "team-07", "sub_game_number": 1,
            "duration_seconds": 9, "audit": {"passed": True},
        },
    }
    view = normalize_log(log)
    assert view["records"]            # top-level records used
    assert view["history"] == []      # no smell history -> flat belief, no crash
    # my_log rebuilt from records; the step-0 system_spec record is skipped
    assert view["my_log"] == [
        {"position": [3, 3], "barrier": None},
        {"position": [2, 3], "barrier": None},
    ]
    assert view["winner"] == "cop"    # falls back to winner_role
    assert view["group"] == "team-07"  # falls back to group_id
