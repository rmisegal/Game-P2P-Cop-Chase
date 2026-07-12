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

    def _draw_agent(self, pos, role: str, inset: int, outline: str) -> None:
        x0, y0, x1, y1 = self._cell_rect(*pos)
        self.create_oval(x0 + inset, y0 + inset, x1 - inset, y1 - inset,
                         fill=ROLE_COLORS.get(role, "#555"), outline=outline, width=2)
        self.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=role[0].upper(),
                         fill="white", font=("Segoe UI", 14, "bold"))

    def _draw_message(self, message: str) -> None:
        """Highlighted banner across the top of the board (e.g. a frozen track)."""
        width = self.board_size * CELL_PX
        self.create_rectangle(0, 0, width, 22, fill="#ffe082", outline="")
        self.create_text(width // 2, 11, text=message, fill="#5d4037",
                         font=("Segoe UI", 10, "bold"))

    def render(self, my_pos, role: str, barriers, visited, belief_matrix,
               opponent_pos=None, opponent_role: str | None = None,
               message: str | None = None) -> None:
        """Redraw the whole board. In replay both true positions are known, so the
        opponent marker (a black-ringed disc) is drawn alongside mine; live mode
        passes opponent_pos=None and only my truth + the belief heatmap show. When
        one track runs out its agent freezes and `message` names the missing step."""
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
        if opponent_pos is not None and opponent_role:
            self._draw_agent(opponent_pos, opponent_role, 14, "black")
        if my_pos is not None:
            self._draw_agent(my_pos, role, 8, "black")
        if message:
            self._draw_message(message)
