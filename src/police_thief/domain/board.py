# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Pure board geometry: king moves, bounds and barrier checks.

Stateless with respect to the game: each peer owns its state elsewhere; the
Board only answers geometric questions for a configurable NxN grid.
"""

from police_thief.constants import DELTAS, Direction

Cell = tuple[int, int]


class Board:
    """NxN grid. Allowed directions are configurable: the book default is the four
    orthogonal moves (+ STAY handled by the caller); the legacy 8-direction king
    movement is used when no move set is supplied."""

    def __init__(self, size: int, moves: tuple[Direction, ...] | None = None):
        self.size = size
        self._moves: tuple[Direction, ...] = tuple(moves) if moves else tuple(Direction)

    @property
    def moves(self) -> tuple[Direction, ...]:
        return self._moves

    @property
    def diagonal(self) -> bool:
        """True if any allowed direction is diagonal (king-style)."""
        return any(DELTAS[d][0] != 0 and DELTAS[d][1] != 0 for d in self._moves)

    def distance(self, a: Cell, b: Cell) -> int:
        """Move-distance under the allowed set: Chebyshev for king, Manhattan otherwise."""
        if self.diagonal:
            return max(abs(a[0] - b[0]), abs(a[1] - b[1]))
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def in_bounds(self, cell: Cell) -> bool:
        row, col = cell
        return 0 <= row < self.size and 0 <= col < self.size

    def step(
        self, origin: Cell, direction: Direction, barriers: set[Cell] | None = None
    ) -> Cell | None:
        """Cell reached from origin in a direction, or None if the direction is not in
        the allowed move set, off-board, or blocked by a barrier."""
        if direction not in self._moves:
            return None
        d_row, d_col = DELTAS[direction]
        target = (origin[0] + d_row, origin[1] + d_col)
        if not self.in_bounds(target):
            return None
        if barriers and target in barriers:
            return None
        return target

    def neighbors(self, cell: Cell, barriers: set[Cell] | None = None) -> list[Cell]:
        """All reachable adjacent cells under the allowed move set."""
        return [t for d in self._moves if (t := self.step(cell, d, barriers)) is not None]

    def legal_moves(
        self, origin: Cell, barriers: set[Cell] | None = None
    ) -> list[tuple[Direction, Cell]]:
        """(direction, target) pairs for every legal single step from origin."""
        return [
            (d, t) for d in self._moves if (t := self.step(origin, d, barriers)) is not None
        ]
