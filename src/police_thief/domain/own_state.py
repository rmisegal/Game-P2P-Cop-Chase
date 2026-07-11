# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""OwnGameState: everything one peer truthfully knows about ITSELF.

There is no shared board. Each peer is authoritative only for its own position,
its visited-cells set and (for police) its barrier quota; opponent-declared
barriers are noted as they arrive over the wire.
"""

from police_thief.constants import Direction, MoveType, Role, directions_from_move_set
from police_thief.domain.board import Board, Cell


class OwnGameState:
    """One peer's private game state and per-step move log."""

    def __init__(self, role: Role, start: Cell, board_size: int, move_set=None):
        self.role = role
        self.board = Board(board_size, moves=directions_from_move_set(move_set))
        self.position: Cell = start
        self.visited: set[Cell] = {start}
        self.barriers: set[Cell] = set()  # all known barriers (mine + declared by opponent)
        self.my_barriers = 0
        self.step_number = 0
        self.log: list[dict] = []

    @property
    def unique_cells(self) -> int:
        return len(self.visited)

    def note_barrier(self, cell: Cell) -> None:
        """Record a barrier the opponent declared (impassable for both)."""
        self.barriers.add(cell)

    def apply_move(
        self, move_type: MoveType, direction: Direction | None, barriers_max: int = 0
    ) -> bool:
        """Apply my own action. Returns False (unchanged state) if illegal."""
        placed: Cell | None = None
        if move_type is MoveType.BARRIER:
            placed = self._place_barrier(direction, barriers_max)
            if placed is None:
                return False
        elif move_type is MoveType.MOVE:
            target = self.board.step(self.position, direction, self.barriers)
            if target is None:
                return False
            self.position = target
            self.visited.add(target)
        # HOLD: position unchanged, not counted as a unique visit
        self.step_number += 1
        self.log.append(
            {
                "step": self.step_number,
                "position": [self.position[0], self.position[1]],
                "move": f"{move_type.value}:{direction.value if direction else '-'}",
                "unique_cells": self.unique_cells,
                "barrier": [placed[0], placed[1]] if placed else None,
            }
        )
        return True

    def _place_barrier(self, direction: Direction | None, barriers_max: int) -> Cell | None:
        if self.role is not Role.POLICE or direction is None:
            return None
        if self.my_barriers >= barriers_max:
            return None
        target = self.board.step(self.position, direction, self.barriers)
        if target is None:
            return None
        self.barriers.add(target)
        self.my_barriers += 1
        return target

    def last_barrier(self) -> Cell | None:
        """The barrier cell just placed, if my last logged move was a barrier."""
        if self.log and self.log[-1]["barrier"]:
            row, col = self.log[-1]["barrier"]
            return (row, col)
        return None
