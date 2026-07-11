# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Wire the four JSON artifact builders to disk for a whole series.

`emit_series` writes ONE declaration + result and a per-sub-game config + log,
all named from the shared game_id, and returns the result dict (for emailing).
Per-group scores come from `domain.scoring`; the two peers derive identical
sub-game entries (same roles/result/scores), so their result files agree.
"""

import json
from pathlib import Path

from police_thief.domain import scoring
from police_thief.report.artifact_helpers import ended_at
from police_thief.report.artifact_schemas import DEFAULT_TIMEZONE
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
from police_thief.report.report_writer import consensus_signature

_DEFAULT_SCORING = {"capture_cop": 20, "capture_thief": 5, "survival_cop": 5,
                    "survival_thief": 10, "tie_score": 2}
_DEFAULT_TOKEN_BUDGET = 200000


def _write(logs_dir, filename: str, data: dict) -> Path:
    out = Path(logs_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _scoring(config) -> dict:
    return config.get("scoring") or dict(_DEFAULT_SCORING)


def _max_tokens(config) -> int:
    league = config.shared.get("network_and_league", {}) if config.shared else {}
    return league.get("token_budget_per_series", _DEFAULT_TOKEN_BUDGET)


def _roles(own_gid: str, opp_gid: str, own_role: str) -> dict:
    opp_role = "thief" if own_role == "police" else "police"
    return {own_gid: own_role, opp_gid: opp_role}


def _subgame_entry(summary, game_id, own_gid, opp_gid, scoring_cfg) -> dict:
    """One sub-game's row in the result: roles, outcome, per-group score, audit."""
    roles = _roles(own_gid, opp_gid, summary["role"])
    n = summary["sub_game_number"]
    score = scoring.score_subgame(summary["result"], roles, scoring_cfg)
    winner = next((g for g, r in roles.items() if r == summary["winner"]), None)
    passed = summary["audit"]["passed"]
    return {
        "sub_game_number": n, "roles": roles,
        "started_at": summary["started_at"],
        "ended_at": ended_at(summary["started_at"], summary["duration_seconds"]),
        "result": summary["result"], "winner_group": winner, "tie": winner is None,
        "github_commit": {own_gid: "unknown", opp_gid: "unknown"},
        "tokens": {own_gid: summary["tokens_total"], opp_gid: 0},
        "score": score,
        "log_files": {own_gid: log_filename(game_id, n), opp_gid: log_filename(game_id, n)},
        "audit": {"log_verified": passed, "tampered": not passed},
    }


def emit_series(config, logs_dir, series) -> dict:
    """Write all four artifacts for `series` and return the result dict."""
    own = series.own_identity
    opp = series.peer_identity or own
    own_gid = own.get("group_id", "unknown-group")
    opp_gid = opp.get("group_id", "unknown-opponent")
    game_id = series.game_id or f"{own_gid}-vs-{opp_gid}"
    game_uid = series.game_uid or "0"
    scoring_cfg = _scoring(config)
    summaries = series.summaries
    first, last = summaries[0], summaries[-1]

    _write(logs_dir, declaration_filename(game_id), build_declaration(
        game_id, game_uid, DEFAULT_TIMEZONE, first["started_at"],
        ended_at(last["started_at"], last["duration_seconds"]),
        len(summaries), _max_tokens(config), own, opp))

    sub_games = []
    for summary in summaries:
        n = summary["sub_game_number"]
        _write(logs_dir, config_filename(game_id, n),
               build_config_artifact(config.shared, game_id, game_uid, n))
        _write(logs_dir, log_filename(game_id, n),
               build_log(summary, game_id, game_uid, own_gid, opp_gid))
        sub_games.append(_subgame_entry(summary, game_id, own_gid, opp_gid, scoring_cfg))

    agg = scoring.aggregate([sg["score"] for sg in sub_games],
                            scoring_cfg.get("tie_score", 2))
    # The mutual signature must be BYTE-IDENTICAL for both peers, so hash only the
    # symmetric outcome (roles/result/score/aggregate) — never per-peer tokens or
    # wall-clock timestamps, which legitimately differ between the two peers.
    symmetric = {
        "game_id": game_id, "aggregate": agg,
        "sub_games": [{"sub_game_number": sg["sub_game_number"], "roles": sg["roles"],
                       "result": sg["result"], "winner_group": sg["winner_group"],
                       "score": sg["score"]} for sg in sub_games],
    }
    mutual = consensus_signature(symmetric)
    result = build_result(game_id, game_uid, sorted([own_gid, opp_gid]),
                          sub_games, agg, mutual)
    _write(logs_dir, result_filename(game_id), result)
    return result
