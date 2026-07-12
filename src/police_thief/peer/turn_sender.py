# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Outbound turn assembly for a PeerRuntime: seal the step, deposit this peer's
scent and push the wire message. Split from runtime.py to keep it small."""

from police_thief.constants import FINAL_CAUGHT_HINT, NO_HINT_PLACEHOLDER, MoveType, Role
from police_thief.peer import runtime_control
from police_thief.peer.sealing import build_turn_message, sealed_step_record
from police_thief.peer.summary import step_usage


def step_usage_of(rt) -> dict:
    """Tokens consumed since the previous step (delegates to the summary helper)."""
    return step_usage(rt)


def take_turn(rt, claim_response: dict | None) -> None:
    """Compute, seal and send one of rt's turns, pumping the control channel around
    it (status broadcast + honoring pause/stop/quit/restart). Split from runtime.py
    to keep that file within the 150-line rule."""
    runtime_control.pump(rt, runtime_control.THINKING)   # shows PAUSED while paused
    rt.controls.wait_if_paused()
    if rt.controls.stopped:
        rt._result = ("stopped", "-")
        return
    runtime_control.pump(rt, runtime_control.THINKING)
    runtime_control.check(rt)
    if rt._result is not None:
        return
    opponent_hint = (rt.handler.history[-1]["hint"] if rt.handler.history
                     else NO_HINT_PLACEHOLDER)
    deadline = rt.controls.speed
    if deadline is None:
        deadline = rt._config.get("llm.step_deadline_seconds")
    decision = rt.brain.decide(
        rt.state, rt.belief, opponent_hint,
        rt._config.get("play.setting"), rt._config.get("rules.barriers_max"),
        deadline_seconds=deadline,
        short_threshold=rt._config.get("llm.short_prompt_threshold_seconds", 0),
    )
    if not rt.state.apply_move(decision.move_type, decision.direction,
                               rt._config.get("rules.barriers_max")):
        rt.state.apply_move(MoveType.HOLD, None)  # never stall the loop
    usage = step_usage(rt)
    win = rt.rules.thief_result(rt.state) if rt.role is Role.THIEF else None
    capture_claim = (
        list(rt.state.position)
        if rt.role is Role.POLICE and decision.move_type is MoveType.MOVE else None
    )
    send(rt, decision, usage, claim_response, capture_claim,
         {"type": win} if win else None)
    rt._listen({"type": "moved", "decision": decision, "view": rt.view(),
                "commit": rt.records[-1]["commit"],
                "usage": {**usage, "match_total": rt._tokens_total}})
    if win:
        rt._result = (win, Role.THIEF.value)


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
