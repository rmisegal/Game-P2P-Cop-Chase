# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Outbound turn assembly for a PeerRuntime: seal the step, deposit this peer's
scent and push the wire message. Split from runtime.py to keep it small."""

from police_thief.constants import FINAL_CAUGHT_HINT, MoveType
from police_thief.peer.sealing import build_turn_message, sealed_step_record
from police_thief.peer.summary import step_usage


def step_usage_of(rt) -> dict:
    """Tokens consumed since the previous step (delegates to the summary helper)."""
    return step_usage(rt)


def send(rt, decision, usage, claim_response, capture_claim, win_claim) -> None:
    """Seal this step, refresh my scent trail, and send the turn to the opponent."""
    record = sealed_step_record(rt.state, decision, usage, rt._tokens_total)
    rt.records.append(record)
    rt.my_scent.deposit(rt.state.position, rt._config.get("smell.emit_intensity"))
    rt.my_scent.decay_all()
    message = build_turn_message(
        rt.state, rt.role.value, decision.hint, rt.my_scent.snapshot(),
        record["commit"], capture_claim, claim_response, win_claim,
    )
    rt._transport.send_turn(message.to_dict())


def send_final(rt, claim_response: dict | None) -> None:
    """Send the mandatory 'You got me' final message when this peer is caught."""
    from police_thief.domain.brains import Decision

    final = Decision(MoveType.HOLD, None, FINAL_CAUGHT_HINT, "truth")
    send(rt, final, step_usage(rt), claim_response, None, None)
