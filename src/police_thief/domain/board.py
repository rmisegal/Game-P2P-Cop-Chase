# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Pure board geometry: king moves, bounds and barrier checks.

Stateless with respect to the game: each peer owns its state elsewhere; the
Board only answers geometric questions for a configurable NxN grid.
"""

from police_thief.constants import DELTAS, Direction

Cell = tuple[int, int]


class Board:
    """NxN grid with 8-direction king movement."""

    def __init__(self, size: int):
        self.size = size

    def in_bounds(self, cell: Cell) -> bool:
        row, col = cell
        return 0 <= row < self.size and 0 <= col < self.size

    def step(
        self, origin: Cell, direction: Direction, barriers: set[Cell] | None = None
    ) -> Cell | None:
        """Cell reached from origin in a direction, or None if off-board/blocked."""
        d_row, d_col = DELTAS[direction]
        target = (origin[0] + d_row, origin[1] + d_col)
        if not self.in_bounds(target):
            return None
        if barriers and target in barriers:
            return None
        return target

    def neighbors(self, cell: Cell, barriers: set[Cell] | None = None) -> list[Cell]:
        """All reachable adjacent cells (king moves)."""
        return [t for d in Direction if (t := self.step(cell, d, barriers)) is not None]

    def legal_moves(
        self, origin: Cell, barriers: set[Cell] | None = None
    ) -> list[tuple[Direction, Cell]]:
        """(direction, target) pairs for every legal single step from origin."""
        return [
            (d, t) for d in Direction if (t := self.step(origin, d, barriers)) is not None
        ]
