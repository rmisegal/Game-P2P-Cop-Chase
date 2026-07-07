# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Win/end conditions evaluated on a peer's OWN state (no referee exists).

The thief evaluates its own victory claims; the police issues capture claims.
Everything is later proven or disproven by the cryptographic audit.
"""

from police_thief.domain.board import Cell
from police_thief.domain.own_state import OwnGameState


class GameRules:
    """Configured end-of-game conditions."""

    def __init__(self, max_steps: int, unique_cells_to_win: int):
        self.max_steps = max_steps
        self.unique_cells_to_win = unique_cells_to_win

    def thief_result(self, state: OwnGameState) -> str | None:
        """The thief's win claim, if any: 'unique_cells', 'survival' or None."""
        if state.unique_cells >= self.unique_cells_to_win:
            return "unique_cells"
        if state.step_number >= self.max_steps:
            return "survival"
        return None

    @staticmethod
    def is_captured(state: OwnGameState, claim: Cell) -> bool:
        """Honest answer to a capture claim: is my true position the claimed cell?

        Lying here is pointless — the audit reveals the sealed true position and
        a false answer forfeits the game.
        """
        return state.position == tuple(claim)
