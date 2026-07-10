# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Opponent-location belief heatmap.

Nobody sees the opponent's true position: each peer maintains a probability
grid over the board, updated from received smell grids and diffused each turn
(the opponent moved one king step). Shown in the GUI as the prediction heatmap.
"""

from police_thief.domain.board import Cell

_EPSILON = 1e-9


class BeliefGrid:
    """Probability distribution over an NxN board for the opponent's cell."""

    def __init__(self, board_size: int, smell_trust: float = 4.0):
        self._size = board_size
        self._smell_trust = smell_trust
        uniform = 1.0 / (board_size * board_size)
        self._probs = [[uniform] * board_size for _ in range(board_size)]

    def _normalize(self) -> None:
        total = sum(sum(row) for row in self._probs)
        if total < _EPSILON:  # degenerate: reset to uniform rather than divide by ~0
            uniform = 1.0 / (self._size * self._size)
            self._probs = [[uniform] * self._size for _ in range(self._size)]
            return
        self._probs = [[p / total for p in row] for row in self._probs]

    def observe_smell(self, cells: dict) -> None:
        """Bayesian-ish update from a received scent-cell map {'r,c': intensity}:
        scale each cell's probability by (1 + trust*intensity). No explicit position
        is supplied — the belief is inferred from the decaying scent field alone."""
        for key, value in cells.items():
            r, c = (int(x) for x in key.split(","))
            if 0 <= r < self._size and 0 <= c < self._size:
                self._probs[r][c] *= 1.0 + self._smell_trust * value
        self._normalize()

    def diffuse(self) -> None:
        """Opponent made one king move: spread each cell's mass to its neighbourhood."""
        fresh = [[0.0] * self._size for _ in range(self._size)]
        for r in range(self._size):
            for c in range(self._size):
                mass = self._probs[r][c]
                if mass < _EPSILON:
                    continue
                targets = [
                    (r + dr, c + dc)
                    for dr in (-1, 0, 1)
                    for dc in (-1, 0, 1)
                    if 0 <= r + dr < self._size and 0 <= c + dc < self._size
                ]
                share = mass / len(targets)
                for tr, tc in targets:
                    fresh[tr][tc] += share
        self._probs = fresh
        self._normalize()

    def exclude(self, cell: Cell) -> None:
        """Rule out a cell (e.g. I stand here and no capture happened)."""
        self._probs[cell[0]][cell[1]] = 0.0
        self._normalize()

    def most_likely(self) -> Cell:
        best, best_p = (0, 0), -1.0
        for r in range(self._size):
            for c in range(self._size):
                if self._probs[r][c] > best_p:
                    best, best_p = (r, c), self._probs[r][c]
        return best

    def as_matrix(self) -> list[list[float]]:
        return [row[:] for row in self._probs]
