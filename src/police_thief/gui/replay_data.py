# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Log-loading helpers for the Visual Replay Player: normalization, the sibling
opponent log (so both true positions can be drawn), and sub-game discovery."""

import json
import re
from pathlib import Path


def normalize_log(log_data: dict) -> dict:
    """Accept EITHER the legacy match log (records/history/my_log nested under
    'summary') OR the standardized template log (records at top level, no smell
    'history'). Returns a uniform view; when the smell history is absent the
    belief heatmap simply stays flat while crypto re-verification still runs."""
    summary = log_data.get("summary", {})
    records = log_data.get("records") or summary.get("records", [])
    my_log = summary.get("my_log")
    if my_log is None:  # standardized format: rebuild a minimal move log from records
        my_log = [
            {"position": r["payload"].get("position", [0, 0]), "barrier": None}
            for r in records
            if r.get("payload", {}).get("type") != "system_spec"
        ]
    return {
        "summary": summary,
        "records": records,
        "history": summary.get("history", []),
        "my_log": my_log,
        "role": summary.get("role", "-"),
        "result": summary.get("result", "-"),
        "winner": summary.get("winner") or summary.get("winner_role", "-"),
        "group": summary.get("group_name") or summary.get("group_id", "unnamed"),
        "sub_game_number": summary.get("sub_game_number", 1),
        "duration_seconds": summary.get("duration_seconds", 0),
        "audit": summary.get("audit", {"passed": True}),
    }


def _game_id(log_data: dict) -> str:
    return log_data.get("game_id") or log_data.get("summary", {}).get("group_id", "")


def opponent_positions(log_path, log_data: dict) -> list:
    """Locate the opponent's sibling log (logs/<opponent_group_id>/log_<game_id>_gNN)
    and return its per-step true positions, so playback can draw BOTH agents.
    Returns [] when the path/sibling is unavailable (belief heatmap still shows)."""
    if not log_path:
        return []
    summary = log_data.get("summary", {})
    opponent = summary.get("opponent_group_id")
    game_id = _game_id(log_data)
    sub = summary.get("sub_game_number", 1)
    if not opponent or not game_id:
        return []
    sibling = Path(log_path).resolve().parent.parent / opponent / \
        f"log_{game_id}_g{sub:02d}.json"
    if not sibling.exists():
        return []
    data = json.loads(sibling.read_text(encoding="utf-8"))
    return [entry["position"] for entry in normalize_log(data)["my_log"]]


def discover_subgames(log_path, log_data: dict) -> list:
    """Sub-game numbers available beside this log (log_<game_id>_gNN.json)."""
    if not log_path:
        return []
    game_id = _game_id(log_data)
    folder = Path(log_path).resolve().parent
    found = []
    for path in folder.glob(f"log_{game_id}_g*.json"):
        match = re.search(r"_g(\d+)\.json$", path.name)
        if match:
            found.append(int(match.group(1)))
    return sorted(found)


def subgame_log_path(log_path, log_data: dict, sub: int) -> Path:
    """Path to another sub-game's log in the same folder."""
    game_id = _game_id(log_data)
    return Path(log_path).resolve().parent / f"log_{game_id}_g{sub:02d}.json"


def frozen_message(i: int, my_len: int, my_role: str,
                   opp_len: int, opp_role: str) -> str | None:
    """Name any agent whose track has run out at step i (its marker is frozen so
    the peer that moved more times keeps advancing). None when both still move."""
    frozen = []
    if i >= my_len:
        frozen.append(my_role)
    if opp_len and i >= opp_len:
        frozen.append(opp_role)
    return " | ".join(f"missing {role} step (frozen)" for role in frozen) or None


def move_labels(payload: dict, commit: str, verify_status: str) -> dict:
    """The per-step 'my move' panel labels, derived from a sealed record."""
    return {
        "hint_out": payload.get("hint", "-"),
        "model": payload.get("model", "-"),
        "tokens": f"{payload.get('tokens_step', 0):,} / {payload.get('tokens_total', 0):,}",
        "llm_time": f"{payload.get('response_seconds', 0):.2f}"
                    + (" [RANDOM]" if payload.get("random_move") else ""),
        "verdict": f"{payload.get('verdict', '-')} (revealed)",
        "commit": f"{commit[:24]}... [{verify_status}]",
    }
