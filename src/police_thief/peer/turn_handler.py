# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""TurnHandler: apply an opponent's TurnMessage to MY local view.

The only knowledge a peer ever gains about its opponent flows through here:
NL hint, smell grid, declared barriers, claims. Nothing else exists — there is
no shared board to consult.
"""

from dataclasses import dataclass

from police_thief.domain.belief import BeliefGrid
from police_thief.domain.own_state import OwnGameState
from police_thief.domain.protocol import TurnMessage
from police_thief.domain.rules import GameRules
from police_thief.domain.smell import SmellField


@dataclass
class IncomingOutcome:
    """Flags raised by an incoming message."""

    i_won: bool = False                 # opponent confirmed my capture claim
    i_am_caught: bool = False           # opponent's capture claim hit my true cell
    opponent_won: bool = False          # opponent raised a win claim
    win_type: str | None = None
    claim_response: dict | None = None  # honest answer I must attach to my next message


class TurnHandler:
    """Folds opponent messages into belief/smell/barrier knowledge."""

    def __init__(self, state: OwnGameState, belief: BeliefGrid,
                 smell_field: SmellField, rules: GameRules):
        self.state = state
        self.belief = belief
        self.smell_field = smell_field
        self.rules = rules
        self.history: list[dict] = []   # every received message, for GUI/replay

    def process(self, message: TurnMessage) -> IncomingOutcome:
        self.history.append(message.to_dict())
        if message.barrier_placed:
            self.state.note_barrier(tuple(message.barrier_placed))
        # Opponent moved: spread belief, then sharpen it with the fresh smell.
        self.belief.diffuse()
        self.belief.observe_smell(message.smell_grid)
        self.smell_field.absorb(message.smell_grid)
        self.smell_field.decay_all()

        outcome = IncomingOutcome()
        if message.claim_response and message.claim_response.get("caught"):
            outcome.i_won = True
        if message.win_claim:
            outcome.opponent_won = True
            outcome.win_type = message.win_claim.get("type")
        if message.capture_claim:
            caught = self.rules.is_captured(self.state, tuple(message.capture_claim))
            outcome.claim_response = {"claim": list(message.capture_claim), "caught": caught}
            outcome.i_am_caught = caught
        return outcome
