# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""PeerWindow: shared Tkinter chrome for the live and replay views."""

import tkinter as tk

from police_thief.gui.board_view import BoardView

GREEN, IDLE = "#2ecc71", "#95a5a6"


class PeerWindow:
    """Window chrome shared by live and replay modes."""

    def __init__(self, title: str, board_size: int, speed: float):
        self.root = tk.Tk()
        self.root.title(title)
        self.banner = tk.Label(self.root, text="WAITING...", bg=IDLE, fg="white",
                               font=("Segoe UI", 14, "bold"), pady=6)
        self.banner.pack(fill="x")
        body = tk.Frame(self.root)
        body.pack(padx=8, pady=8)
        self.board = BoardView(body, board_size)
        self.board.pack(side="left")
        panel = tk.Frame(body)
        panel.pack(side="left", fill="y", padx=(10, 0))
        self.labels = {}
        for key, caption in [("step", "Step"), ("model", "Model"),
                             ("tokens", "Tokens step / total"),
                             ("llm_time", "LLM response (s)"),
                             ("barriers", "Barriers used"),
                             ("hint_in", "Opponent says"),
                             ("hint_out", "I said"), ("verdict", "My verdict"),
                             ("commit", "My commit (sealed)"), ("status", "Status")]:
            tk.Label(panel, text=caption + ":", font=("Segoe UI", 9, "bold"),
                     anchor="w").pack(fill="x")
            self.labels[key] = tk.Label(panel, text="-", anchor="w", wraplength=300,
                                        justify="left")
            self.labels[key].pack(fill="x", pady=(0, 6))
        tk.Label(panel, text="Step time budget (sec)\n0 = no LLM, random moves:",
                 font=("Segoe UI", 9, "bold"), anchor="w", justify="left").pack(fill="x")
        self.speed = tk.DoubleVar(value=speed)
        tk.Scale(panel, from_=0.0, to=60.0, resolution=0.1, orient="horizontal",
                 variable=self.speed).pack(fill="x")

    def add_about_button(self, about: dict) -> None:
        tk.Button(self.root, text="About / System spec",
                  command=lambda: self._show_about(about)).pack(pady=(0, 6))

    def _show_about(self, about: dict) -> None:
        top = tk.Toplevel(self.root)
        top.title("About")
        text = "\n".join(f"{key}: {value}" for key, value in about.items())
        tk.Label(top, text=text, justify="left", anchor="w",
                 font=("Consolas", 10), padx=12, pady=12).pack()
        tk.Button(top, text="Close", command=top.destroy).pack(pady=(0, 8))

    def set_turn(self, mine: bool, text: str | None = None) -> None:
        self.banner.config(bg=GREEN if mine else IDLE,
                           text=text or ("MY TURN - thinking..." if mine else "WAITING..."))

    def set_label(self, key: str, value: str) -> None:
        self.labels[key].config(text=value)

    def render(self, view: dict) -> None:
        self.board.render(view["position"], view["role"], view["barriers"],
                          view["visited"], view["belief"])
        self.set_label("step", str(view["step"]))
        if "barriers_used" in view:
            self.set_label("barriers",
                           f"{view['barriers_used']} / {view['barriers_max']}")
