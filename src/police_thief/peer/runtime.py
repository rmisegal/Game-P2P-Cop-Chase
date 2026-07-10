# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""PeerRuntime: one standalone agent's full lifecycle — no central server.

negotiate (mutual signatures) → turn loop (wait green → think → move → seal →
send) → end-of-game audit (reveal nonces, verify opponent's log). The turn
token travels with the TurnMessage: receiving one makes this peer 'green'.
"""

import random
import time

from police_thief.constants import FINAL_CAUGHT_HINT, NO_HINT_PLACEHOLDER, MoveType, Role
from police_thief.domain.belief import BeliefGrid
from police_thief.domain.brains import PoliceBrain, ThiefBrain
from police_thief.domain.negotiation import Negotiation
from police_thief.domain.own_state import OwnGameState
from police_thief.domain.protocol import TurnMessage
from police_thief.domain.rules import GameRules
from police_thief.domain.smell import SmellField
from police_thief.peer.controls import GameControls
from police_thief.peer.sealing import (
    build_turn_message,
    now_iso,
    sealed_spec_record,
    sealed_step_record,
    terms_from_config,
)
from police_thief.peer.summary import finish, snapshot, step_usage


class PeerRuntime:
    """Runs one agent (thief or police) against a remote opponent."""

    def __init__(self, role: Role, config, llm, transport, listener=None, controls=None):
        from police_thief.peer.turn_handler import TurnHandler

        self.role = role
        self._config = config
        self._transport = transport
        self._listen = listener or (lambda event: None)
        self.controls = controls or GameControls()
        size = config.get("board.size")
        start = tuple(config.get(f"positions.{'thief' if role is Role.THIEF else 'cop'}_start"))
        self.state = OwnGameState(role=role, start=start, board_size=size)
        self.belief = BeliefGrid(board_size=size,
                                 smell_trust=config.get("belief.smell_trust_weight", 4.0))
        self.smell = SmellField(
            board_size=size, grid_size=config.get("smell.grid_size"),
            decay=config.get("smell.decay_per_step"),
            min_center=config.get("smell.min_center_intensity"),
        )
        self.rules = GameRules(config.get("rules.max_steps"))
        self.handler = TurnHandler(self.state, self.belief, self.smell, self.rules)
        brain_cls = ThiefBrain if role is Role.THIEF else PoliceBrain
        self.brain = brain_cls(llm, rng=random.Random(config.get("play.seed")))
        self._llm = llm
        self._tokens_total = 0
        self._started_monotonic = time.monotonic()
        self._started_at = now_iso()
        self.records: list[dict] = []   # my sealed steps: {payload, nonce, commit}
        self.records.append(sealed_spec_record(config))
        self._result: tuple[str, str] | None = None  # (result, winner)

    def view(self) -> dict:
        return snapshot(self)

    def run(self, skip_negotiation: bool = False) -> dict:
        if not skip_negotiation:
            negotiation = Negotiation(terms_from_config(self._config))
            peer_message = self._transport.exchange_agreement(negotiation.signed())
            negotiation.verify_peer(peer_message)
            self._started_monotonic = time.monotonic()  # game clock starts at agreement
            self._listen({"type": "negotiated", "view": self.view()})
        if self.role is Role.THIEF:
            self._take_turn(claim_response=None)
        self._turn_loop()
        return self._finish()

    def _turn_loop(self) -> None:
        timeout = self._config.get("network.turn_timeout_seconds")
        poll = self._config.get("network.poll_interval_seconds", 0.5)
        deadline = time.monotonic() + timeout
        while self._result is None:
            if self.controls.stopped:
                self._result = ("stopped", "-")
                return
            incoming = self._transport.poll_turn(poll)
            if incoming is None:
                if time.monotonic() > deadline:
                    self._result = ("timeout", self.role.value)  # opponent silent
                continue
            deadline = time.monotonic() + timeout
            outcome = self.handler.process(TurnMessage.from_dict(incoming))
            self._listen({"type": "incoming", "message": incoming, "view": self.view()})
            if outcome.i_won:
                self._result = ("capture", Role.POLICE.value)
            elif outcome.opponent_won:
                self._result = (outcome.win_type or "survival", Role.THIEF.value)
            elif outcome.i_am_caught:
                self._send_final(outcome.claim_response)
                self._result = ("capture", Role.POLICE.value)
            else:
                self._take_turn(outcome.claim_response)

    def _take_turn(self, claim_response: dict | None) -> None:
        self.controls.wait_if_paused()
        if self.controls.stopped:
            self._result = ("stopped", "-")
            return
        opponent_hint = (self.handler.history[-1]["hint"] if self.handler.history
                         else NO_HINT_PLACEHOLDER)
        deadline = self.controls.speed  # live GUI slider wins over the config default
        if deadline is None:
            deadline = self._config.get("llm.step_deadline_seconds")
        decision = self.brain.decide(
            self.state, self.belief, opponent_hint,
            self._config.get("play.setting"), self._config.get("rules.barriers_max"),
            deadline_seconds=deadline,
            short_threshold=self._config.get("llm.short_prompt_threshold_seconds", 0),
        )
        if not self.state.apply_move(decision.move_type, decision.direction,
                                     self._config.get("rules.barriers_max")):
            self.state.apply_move(MoveType.HOLD, None)  # never stall the loop
        usage = self._step_usage()
        win = self.rules.thief_result(self.state) if self.role is Role.THIEF else None
        capture_claim = (
            list(self.state.position)
            if self.role is Role.POLICE and decision.move_type is MoveType.MOVE else None
        )
        self._send(decision, usage, claim_response, capture_claim,
                   {"type": win} if win else None)
        self._listen({"type": "moved", "decision": decision, "view": self.view(),
                      "commit": self.records[-1]["commit"],
                      "usage": {**usage, "match_total": self._tokens_total}})
        if win:
            self._result = (win, Role.THIEF.value)

    def _step_usage(self) -> dict:
        return step_usage(self)

    def _send_final(self, claim_response: dict | None) -> None:
        from police_thief.domain.brains import Decision

        final = Decision(MoveType.HOLD, None, FINAL_CAUGHT_HINT, "truth")
        self._send(final, self._step_usage(), claim_response, None, None)

    def _send(self, decision, usage, claim_response, capture_claim, win_claim) -> None:
        record = sealed_step_record(self.state, decision.verdict, decision.hint, usage,
                                    self._tokens_total, decision.response_seconds,
                                    decision.random_move)
        self.records.append(record)
        message = build_turn_message(
            self.state, self.role.value, decision.hint,
            self.smell.emit(self.state.position, self._config.get("smell.emit_intensity")),
            record["commit"], capture_claim, claim_response, win_claim,
        )
        self._transport.send_turn(message.to_dict())

    def _finish(self) -> dict:
        return finish(self)
