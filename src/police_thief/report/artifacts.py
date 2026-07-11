# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Pure builders for the four standardized game JSON artifacts (book Appendix F):
declaration, config, log, result. No I/O — each returns a dict matching the
Json-examples/ templates. Wiring into the runtime/sdk happens in a later phase.

Filename helpers (`declaration_filename`, `config_filename`, ...) are re-exported
here for convenience alongside the builders.
"""

from police_thief.report.artifact_helpers import (
    canonical_sha256,
    config_filename,
    declaration_filename,
    ended_at,
    group_block,
    links,
    log_filename,
    result_filename,
    tokens_series,
)
from police_thief.report.artifact_schemas import (
    DEFAULT_TIMEZONE,
    SCHEMA_CONFIG,
    SCHEMA_DECLARATION,
    SCHEMA_LOG,
    SCHEMA_RESULT,
    SCHEMA_VERSION,
)
from police_thief.report.report_writer import consensus_signature

__all__ = [
    "build_config_artifact", "build_declaration", "build_log", "build_result",
    "config_filename", "declaration_filename", "log_filename", "result_filename",
]


def build_declaration(game_id, game_uid, timezone, game_started_at, game_ended_at,
                      num_sub_games, max_tokens_per_game, own, opponent) -> dict:
    """Template 1: static pre-game declaration for the whole series (both teams)."""
    return {
        "_schema": SCHEMA_DECLARATION,
        "schema_version": SCHEMA_VERSION,
        "declaration_type": "pre_game_declaration",
        "game_id": game_id,
        "game_uid": game_uid,
        "links": links(game_id),
        "timezone": timezone,
        "game_started_at": game_started_at,
        "game_ended_at": game_ended_at,
        "num_sub_games": num_sub_games,
        "max_tokens_per_game": max_tokens_per_game,
        "groups": {"group_1": group_block(own), "group_2": group_block(opponent)},
    }


def build_config_artifact(shared_terms: dict, game_id, game_uid, sub_game_number) -> dict:
    """Template 2: the agreed, byte-identical config + its canonical sha256 lock."""
    artifact = {"_schema": SCHEMA_CONFIG, **shared_terms}
    artifact.update({
        "schema_version": SCHEMA_VERSION,
        "game_id": game_id,
        "game_uid": game_uid,
        "sub_game_number": sub_game_number,
        "links": links(game_id),
        "config_name": config_filename(game_id, sub_game_number),
        "config_sha256": canonical_sha256(shared_terms),
    })
    return artifact


def build_log(summary: dict, game_id, game_uid, group_id, opponent_group_id) -> dict:
    """Template 3: one peer's per-sub-game commit-reveal log, from its runtime summary."""
    records = summary["records"]
    log_summary = {
        "sub_game_number": summary["sub_game_number"],
        "group_id": group_id,
        "role": summary["role"],
        "opponent_group_id": opponent_group_id,
        "result": summary["result"],
        "winner_role": summary["winner"],
        "steps": summary["steps"],
        "timezone": summary.get("timezone", DEFAULT_TIMEZONE),
        "started_at": summary["started_at"],
        "ended_at": ended_at(summary["started_at"], summary["duration_seconds"]),
        "duration_seconds": summary["duration_seconds"],
        "tokens_total": summary["tokens_total"],
        "audit": summary["audit"],
    }
    return {
        "_schema": SCHEMA_LOG,
        "schema_version": SCHEMA_VERSION,
        "game_id": game_id,
        "game_uid": game_uid,
        "links": links(game_id),
        "summary": log_summary,
        "records": records,
        "mutual_agreement": {
            "opponent_group_id": opponent_group_id,
            "sha256": consensus_signature(records),
            "confirmed": summary["audit"]["passed"],
        },
    }


def build_result(game_id, game_uid, group_ids, sub_games: list, aggregate_out: dict,
                 mutual_sha256: str) -> dict:
    """Template 4: the aggregated final result over all sub-games (both teams agree)."""
    final_result = {**aggregate_out, "tokens_total_series": tokens_series(sub_games, group_ids)}
    return {
        "_schema": SCHEMA_RESULT,
        "schema_version": SCHEMA_VERSION,
        "report_type": "final_game_result",
        "game_id": game_id,
        "game_uid": game_uid,
        "links": links(game_id),
        "timezone": DEFAULT_TIMEZONE,
        "groups": list(group_ids),
        "num_sub_games": len(sub_games),
        "sub_games": sub_games,
        "final_result": final_result,
        "mutual_agreement": {
            "sha256": mutual_sha256,
            "confirmed": all(sg.get("audit", {}).get("log_verified", False) for sg in sub_games),
        },
    }
