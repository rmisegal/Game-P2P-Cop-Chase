# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Sealing helpers: build and SHA-256-seal the records a peer commits to —
the per-step state payloads and the one-time host-spec declaration (book §6).
"""

from datetime import UTC, datetime

from police_thief.domain.crypto import CommitReveal
from police_thief.domain.protocol import TurnMessage
from police_thief.shared.sysinfo import collect_spec
from police_thief.shared.version import CODE_VERSION


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def sealed_spec_record(config, sub_game_number: int = 1) -> dict:
    """Host spec + model + group identity + code version, sealed (step 0).

    `sub_game_number` is the LIVE series index (the series loop rebuilds one
    PeerRuntime per sub-game), not a static config value.
    """
    payload = {
        "step": 0, "type": "system_spec", "spec": collect_spec(),
        "model": config.get("llm.model", "") or "cli-default",
        "code_version": CODE_VERSION,
        "group_name": config.get("game.group_name", "unnamed"),
        "sub_game_number": sub_game_number,
    }
    return {"payload": payload, **CommitReveal.seal(payload)}


def identity_from_config(cfg) -> dict:
    """This peer's static group identity, exchanged in the handshake so both
    peers can build the whole-series declaration. Roles alternate across sub-games,
    so identity is per-GROUP (not per-role). Includes the host `spec` because the
    declaration lists each group's hardware and only its owner knows it."""
    return {
        "group_id": cfg.get("game.group_id", "unknown-group"),
        "group_name": cfg.get("game.group_name", "unnamed"),
        "members": cfg.get("game.members", []),
        "repos": cfg.get("game.repos", {}),
        "mcp_servers": cfg.get("game.mcp_servers", {}),
        "llm_model": cfg.get("llm.model", "") or "cli-default",
        "spec": collect_spec(),
    }


def _state_str(state) -> str:
    """Compact, replayable board-state string for the sealed record."""
    barriers = sorted([list(b) for b in state.barriers])
    return f"grid={state.board.size}x{state.board.size};self={list(state.position)};barriers={barriers}"


def sealed_step_record(state, decision, usage: dict, tokens_total: int) -> dict:
    """One turn's true state + move + intent + hint + prompt-discussion + tokens, sealed.

    `decision` is the brain's Decision (verdict, hint, prompt_text, reasoning, timing).
    The whole payload is hashed, so prompt_discussion is audit-covered too.
    """
    payload = {
        "step": state.step_number,
        "state": _state_str(state),
        "position": list(state.position),
        "move": state.log[-1]["move"] if state.log else "-",
        "intent": decision.verdict,
        "verdict": decision.verdict,  # kept for existing audit/replay/report consumers
        "hint": decision.hint,
        "prompt_discussion": {
            "llm_prompt": decision.prompt_text,
            "llm_reasoning": decision.reasoning,
            "bluff_classification": decision.verdict,
        },
        "model": usage.get("model", "unknown"),
        "tokens_step": usage.get("total", 0),
        "tokens_total": tokens_total,
        "response_seconds": decision.response_seconds,
        "random_move": decision.random_move,
    }
    return {"payload": payload, **CommitReveal.seal(payload)}


def terms_from_config(cfg) -> dict:
    """The signed game agreement: everything both peers MUST match on."""
    return {
        "board_size": cfg.get("board.size"),
        "smell_grid_size": cfg.get("smell.grid_size"),
        "decay_per_step": cfg.get("smell.decay_per_step"),
        "max_steps": cfg.get("rules.max_steps"),
        "barriers_max": cfg.get("rules.barriers_max"),
        "setting": cfg.get("play.setting"),  # the agreed real-world map area (world.map_area)
        "hint_max_words": cfg.get("play.hint_max_words", 15),
        "axis_origin_corner": cfg.get("board.axis_origin_corner", "top-left"),
        "axis_start_index": cfg.get("board.axis_start_index", 0),
        "thief_start": cfg.get("positions.thief_start"),
        "cop_start": cfg.get("positions.cop_start"),
        "num_games": cfg.get("game.num_games", 1),
    }


def build_turn_message(state, role: str, hint: str, smell_grid: dict, commit: str,
                       capture_claim, claim_response, win_claim) -> TurnMessage:
    """The wire message for this turn (turn token travels with it)."""
    barrier = state.last_barrier()
    return TurnMessage(
        step=state.step_number, sender=role, hint=hint, smell_grid=smell_grid,
        commit=commit, timestamp=now_iso(),
        barrier_placed=list(barrier) if barrier else None,
        capture_claim=capture_claim, claim_response=claim_response, win_claim=win_claim,
    )
