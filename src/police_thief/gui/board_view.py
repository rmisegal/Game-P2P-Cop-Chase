# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""BoardView: Tkinter canvas rendering one peer's view of the world —
my TRUE position, known barriers, visited trail, and the opponent-location
belief heatmap. The opponent's true position is never available to draw.
"""

import tkinter as tk

CELL_PX = 52
ROLE_COLORS = {"thief": "#e67e22", "police": "#2980b9"}


class BoardView(tk.Canvas):
    """NxN grid canvas for one peer."""

    def __init__(self, parent, board_size: int):
        self.board_size = board_size
        side = board_size * CELL_PX
        super().__init__(parent, width=side, height=side, bg="white",
                         highlightthickness=1, highlightbackground="#888")

    def _cell_rect(self, row: int, col: int):
        x0, y0 = col * CELL_PX, row * CELL_PX
        return x0, y0, x0 + CELL_PX, y0 + CELL_PX

    @staticmethod
    def _heat_color(probability: float, peak: float) -> str:
        """White -> red scale by probability relative to the current peak."""
        if peak <= 0:
            return "#ffffff"
        level = min(1.0, probability / peak)
        green_blue = int(255 * (1 - 0.8 * level))
        return f"#ff{green_blue:02x}{green_blue:02x}"

    def render(self, my_pos, role: str, barriers, visited, belief_matrix) -> None:
        """Redraw the whole board from the peer's current knowledge."""
        self.delete("all")
        peak = max((p for row in belief_matrix for p in row), default=0.0)
        for row in range(self.board_size):
            for col in range(self.board_size):
                self.create_rectangle(
                    *self._cell_rect(row, col), outline="#ccc",
                    fill=self._heat_color(belief_matrix[row][col], peak),
                )
        for cell in visited:
            x0, y0, x1, y1 = self._cell_rect(*cell)
            self.create_oval(x0 + 21, y0 + 21, x1 - 21, y1 - 21,
                             fill="#b0bec5", outline="")
        for cell in barriers:
            x0, y0, x1, y1 = self._cell_rect(*cell)
            self.create_rectangle(x0 + 4, y0 + 4, x1 - 4, y1 - 4,
                                  fill="#263238", outline="")
        if my_pos is not None:
            x0, y0, x1, y1 = self._cell_rect(*my_pos)
            self.create_oval(x0 + 8, y0 + 8, x1 - 8, y1 - 8,
                             fill=ROLE_COLORS.get(role, "#555"), outline="black", width=2)
            self.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=role[0].upper(),
                             fill="white", font=("Segoe UI", 14, "bold"))
