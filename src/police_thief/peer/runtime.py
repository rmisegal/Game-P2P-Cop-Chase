# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""PeerRuntime: one standalone agent's full lifecycle — no central server.

negotiate (mutual signatures) → turn loop (wait green → think → move → seal →
send) → end-of-game audit (reveal nonces, verify opponent's log). The turn
token travels with the TurnMessage: receiving one makes this peer 'green'.
"""

import random
import time

from police_thief.constants import Role
from police_thief.domain.belief import BeliefGrid
from police_thief.domain.own_state import OwnGameState
from police_thief.domain.protocol import TurnMessage
from police_thief.domain.rules import GameRules
from police_thief.domain.smell import SmellField
from police_thief.peer import runtime_control, turn_sender
from police_thief.peer.control_link import ControlLink
from police_thief.peer.controls import GameControls
from police_thief.peer.sealing import identity_from_config, now_iso, sealed_spec_record
from police_thief.peer.summary import finish, snapshot
from police_thief.strategy import resolve_brain


class PeerRuntime:
    """Runs one agent (thief or police) for ONE sub-game against a remote opponent.

    A series rebuilds a fresh runtime per sub-game (new state/belief/smell/commit
    chain) while the transport/servers stay alive; `sub_game_number` is the live
    series index and roles alternate across the series."""

    def __init__(self, role: Role, config, llm, transport, listener=None, controls=None,
                 own_identity: dict | None = None, sub_game_number: int = 1, link=None):
        from police_thief.peer.turn_handler import TurnHandler

        self.role = role
        self._config = config
        self._own_identity = own_identity or identity_from_config(config)
        self._sub_game_number = sub_game_number
        self.peer_identity: dict = {}
        self.game_id: str | None = None
        self.game_uid: str | None = None
        self._transport = transport
        self._listen = listener or (lambda event: None)
        self.controls = controls or GameControls()
        # Shared across the whole series (enable state persists); a default is made
        # for direct/one-off runtimes. A transport without control methods -> no-op.
        self.link = link or ControlLink(role.value, transport, self.controls, self._listen)
        size = config.get("board.size")
        start = tuple(config.get(f"positions.{'thief' if role is Role.THIEF else 'cop'}_start"))
        self.state = OwnGameState(role=role, start=start, board_size=size,
                                  move_set=config.get("rules.move_set"))
        self.belief = BeliefGrid(board_size=size,
                                 smell_trust=config.get("belief.smell_trust_weight", 4.0),
                                 orthogonal=not self.state.board.diagonal)
        self.smell = SmellField(
            board_size=size, grid_size=config.get("smell.grid_size"),
            decay=config.get("smell.decay_per_step"),
            min_center=config.get("smell.min_center_intensity"),
        )
        # My own scent trail; only its intensity field is sent (never my exact cell).
        self.my_scent = SmellField(
            board_size=size, grid_size=config.get("smell.grid_size"),
            decay=config.get("smell.decay_per_step"),
            min_center=config.get("smell.min_center_intensity"),
        )
        self.rules = GameRules(config.get("rules.max_steps"))
        self.handler = TurnHandler(self.state, self.belief, self.smell, self.rules)
        # Strategy seam: the brain class is INJECTABLE via config (strategy.thief_class /
        # strategy.police_class); unset => the shipped heuristic brain (default behaviour).
        self.brain = resolve_brain(config, role, llm, rng=random.Random(config.get("play.seed")))
        self._llm = llm
        self._tokens_total = 0
        self._started_monotonic = time.monotonic()
        self._started_at = now_iso()
        self.records: list[dict] = []   # my sealed steps: {payload, nonce, commit}
        self.records.append(sealed_spec_record(config, sub_game_number))
        self._result: tuple[str, str] | None = None  # (result, winner)

    def view(self) -> dict:
        return snapshot(self)

    def run(self, skip_negotiation: bool = False) -> dict:
        if not skip_negotiation:
            from police_thief.peer.handshake import negotiate

            negotiate(self)
            self._listen({"type": "negotiated", "view": self.view()})
        runtime_control.pump(self, runtime_control.PLAYING)
        if self.role is Role.THIEF:
            self._take_turn(claim_response=None)
        self._turn_loop()
        runtime_control.pump(self, runtime_control.GAME_OVER)
        return finish(self)

    def _take_turn(self, claim_response: dict | None) -> None:
        turn_sender.take_turn(self, claim_response)

    def _turn_loop(self) -> None:
        timeout = self._config.get("network.turn_timeout_seconds")
        poll = self._config.get("network.poll_interval_seconds", 0.5)
        deadline = time.monotonic() + timeout
        while self._result is None:
            if self.controls.stopped:
                self._result = ("stopped", "-")
                return
            runtime_control.pump(self, runtime_control.WAITING)
            runtime_control.check(self)
            if self._result is not None:
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
                turn_sender.send_final(self, outcome.claim_response)
                self._result = ("capture", Role.POLICE.value)
            else:
                self._take_turn(outcome.claim_response)
