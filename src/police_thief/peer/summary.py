# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""End-of-game: audit exchange + the peer's final match summary."""

import time

from police_thief.domain.crypto import audit_records
from police_thief.domain.protocol import AuditPayload

SKIPPED_AUDIT = {"passed": False, "verified_steps": 0, "failed_steps": [], "skipped": True}
NO_AUDIT_RESULTS = ("timeout", "stopped")  # nobody left (or nothing) to audit with


def snapshot(rt) -> dict:
    """GUI render snapshot: the peer's truth + its belief, nothing more."""
    return {
        "role": rt.role.value,
        "step": rt.state.step_number,
        "position": rt.state.position,
        "barriers": sorted(rt.state.barriers),
        "barriers_used": rt.state.my_barriers,
        "barriers_max": rt._config.get("rules.barriers_max"),
        "visited": sorted(rt.state.visited),
        "belief": rt.belief.as_matrix(),
    }


def step_usage(rt) -> dict:
    """Tokens actually consumed since the previous step (delta accounting).

    A skipped/random step charges 0; a timed-out call's tokens land on the
    step where the abandoned reply finally arrived.
    """
    consumed = getattr(rt._llm, "tokens_consumed", 0)
    step_tokens = consumed - rt._tokens_total
    rt._tokens_total = consumed
    model = (getattr(rt._llm, "last_usage", None) or {}).get("model", "unknown")
    return {"model": model, "total": step_tokens}


def finish(rt) -> dict:
    """Exchange audits (when a real result exists) and build the summary.

    `rt` is the PeerRuntime — this is its final act, split out to keep the
    runtime module within the file-size rule.
    """
    result, winner = rt._result
    audit = SKIPPED_AUDIT
    if result not in NO_AUDIT_RESULTS:
        mine = AuditPayload(sender=rt.role.value, records=rt.records, result_claim=result)
        theirs = rt._transport.exchange_audit(mine.to_dict())
        if theirs is not None:
            audit = audit_records(AuditPayload.from_dict(theirs).records)
            if not audit["passed"]:
                # Iron rule: a forged/tampered opponent log forfeits the game — the
                # honest peer wins by technical decision regardless of the board result.
                result, winner = "tamper_forfeit", rt.role.value
    summary = {
        "result": result, "winner": winner, "steps": rt.state.step_number,
        "tokens_total": rt._tokens_total,
        "group_name": rt._config.get("game.group_name", "unnamed"),
        "sub_game_number": rt._config.get("game.sub_game_number", 1),
        "started_at": rt._started_at,
        "duration_seconds": round(time.monotonic() - rt._started_monotonic, 1),
        "audit": audit, "records": rt.records, "history": rt.handler.history,
        "my_log": rt.state.log, "role": rt.role.value,
    }
    rt._listen({"type": "game_over", "summary": summary, "view": rt.view()})
    return summary
