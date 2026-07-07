# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Smell mechanics: each peer emits a local MxM grid and absorbs the opponent's.

The field tracks intensities the peer knows about on the full board; every game
step all intensities decay by a configured constant (clamped to 0..1).
"""

from police_thief.domain.board import Cell


class SmellField:
    """Board-wide smell intensities known to one peer + MxM grid emission."""

    def __init__(self, board_size: int, grid_size: int, decay: float, min_center: float):
        self._board_size = board_size
        self._grid_size = grid_size
        self._decay = decay
        self._min_center = min_center
        self._values: dict[Cell, float] = {}

    def emit(self, center: Cell, intensity: float) -> dict:
        """Build the MxM smell grid message centred on a chosen cell.

        Intensity falls off with Chebyshev distance from the center; the center
        cell must meet the configured minimum (game rule: at least one cell >= 0.5).
        """
        if intensity < self._min_center:
            raise ValueError(
                f"Center intensity {intensity} below required minimum {self._min_center}"
            )
        half = self._grid_size // 2
        falloff = intensity / (half + 1)
        values = [
            [
                round(max(0.0, intensity - falloff * max(abs(dr), abs(dc))), 3)
                for dc in range(-half, half + 1)
            ]
            for dr in range(-half, half + 1)
        ]
        return {"center": [center[0], center[1]], "values": values}

    def absorb(self, grid: dict) -> None:
        """Merge a received MxM grid into the known field (max wins per cell)."""
        center_row, center_col = grid["center"]
        half = self._grid_size // 2
        for i, row in enumerate(grid["values"]):
            for j, value in enumerate(row):
                cell = (center_row - half + i, center_col - half + j)
                if 0 <= cell[0] < self._board_size and 0 <= cell[1] < self._board_size:
                    self._values[cell] = max(self._values.get(cell, 0.0), value)

    def decay_all(self) -> None:
        """One game step passed: every intensity drops by the decay constant."""
        for cell in list(self._values):
            self._values[cell] = max(0.0, round(self._values[cell] - self._decay, 3))

    def intensity_at(self, cell: Cell) -> float:
        return self._values.get(cell, 0.0)

    def strongest_cell(self) -> Cell | None:
        """The most fragrant known cell — the naive opponent-location guess."""
        if not self._values:
            return None
        cell, value = max(self._values.items(), key=lambda kv: kv[1])
        return cell if value > 0.0 else None

    def snapshot(self) -> dict[str, float]:
        """Serializable copy: {'r,c': intensity} for logging / GUI."""
        return {f"{r},{c}": v for (r, c), v in self._values.items() if v > 0.0}
