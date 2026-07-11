# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Shared, pure helpers for the artifact builders: game_id-derived filenames, the
`links` block, canonical hashing, and the declaration's hardware/group blocks."""

import hashlib
import json
from datetime import datetime, timedelta

from police_thief.report.artifact_schemas import LINKS_REMARK
from police_thief.report.report_writer import consensus_signature


def declaration_filename(game_id: str) -> str:
    return f"declaration_{game_id}.json"


def config_filename(game_id: str, sub_game_number: int) -> str:
    return f"config_{game_id}_g{sub_game_number:02d}.json"


def log_filename(game_id: str, sub_game_number: int) -> str:
    return f"log_{game_id}_g{sub_game_number:02d}.json"


def result_filename(game_id: str) -> str:
    return f"result_{game_id}.json"


def links(game_id: str) -> dict:
    """Shared links block: logical role -> filename. Per-sub-game files keep the
    literal g<NN> placeholder because <NN> (sub_game_number) varies per file."""
    return {
        "_remark": LINKS_REMARK,
        "declaration": declaration_filename(game_id),
        "config": f"config_{game_id}_g<NN>.json",
        "log": f"log_{game_id}_g<NN>.json",
        "result": result_filename(game_id),
    }


def canonical_sha256(data) -> str:
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def ended_at(started_at: str, duration_seconds: float) -> str:
    """started_at (ISO, tz-aware) + duration -> ISO ended_at; echo input if unparsable."""
    try:
        start = datetime.fromisoformat(started_at)
    except (TypeError, ValueError):
        return started_at
    return (start + timedelta(seconds=duration_seconds)).isoformat()


def hardware_spec(spec: dict) -> dict:
    """Exactly the 6 book hardware fields, renaming gpu_type -> gpu_model."""
    return {
        "cpu_type": spec.get("cpu_type"),
        "cpu_freq_mhz": spec.get("cpu_freq_mhz"),
        "cpu_cores": spec.get("cpu_cores"),
        "ram_gb": spec.get("ram_gb"),
        "gpu_model": spec.get("gpu_type"),
        "vram_gb": spec.get("vram_gb"),
    }


def group_block(identity: dict) -> dict:
    """One team's static block; signature = consensus over the block sans signature."""
    block = {
        "group_id": identity["group_id"],
        "group_name": identity["group_name"],
        "members": identity["members"],
        "repos": identity["repos"],
        "mcp_servers": identity["mcp_servers"],
        "llm_model": identity["llm_model"],
        "hardware_spec": hardware_spec(identity["spec"]),
    }
    block["signature"] = consensus_signature(block)
    return block


def tokens_series(sub_games: list, group_ids) -> dict:
    return {g: sum(sg.get("tokens", {}).get(g, 0) for sg in sub_games) for g in group_ids}
