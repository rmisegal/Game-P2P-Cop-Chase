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


def sealed_spec_record(config) -> dict:
    """Host spec + model + group identity + code version, sealed (step 0)."""
    payload = {
        "step": 0, "type": "system_spec", "spec": collect_spec(),
        "model": config.get("llm.model", "") or "cli-default",
        "code_version": CODE_VERSION,
        "group_name": config.get("game.group_name", "unnamed"),
        "sub_game_number": config.get("game.sub_game_number", 1),
    }
    return {"payload": payload, **CommitReveal.seal(payload)}


def sealed_step_record(state, verdict: str, hint: str, usage: dict,
                       tokens_total: int, response_seconds: float = 0.0,
                       random_move: bool = False) -> dict:
    """One turn's true state + move + verdict + tokens + timing, sealed."""
    payload = {
        "step": state.step_number,
        "position": list(state.position),
        "move": state.log[-1]["move"] if state.log else "-",
        "verdict": verdict,
        "hint": hint,
        "model": usage.get("model", "unknown"),
        "tokens_step": usage.get("total", 0),
        "tokens_total": tokens_total,
        "response_seconds": response_seconds,
        "random_move": random_move,
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
        "setting": cfg.get("play.setting"),
        "thief_start": cfg.get("positions.thief_start"),
        "cop_start": cfg.get("positions.cop_start"),
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
