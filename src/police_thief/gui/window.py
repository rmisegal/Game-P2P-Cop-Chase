# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""PeerWindow: shared Tkinter chrome for the live and replay views."""

import os
import subprocess
import sys
import tkinter as tk
import webbrowser

from police_thief.gui.board_view import BoardView
from police_thief.shared.version import (
    BOOK_VERSION,
    CODE_VERSION,
    COPYRIGHT_TITLE,
    GUIDELINES_PDF,
    LICENSE_NOTICE,
)

GREEN, IDLE = "#2ecc71", "#95a5a6"


def title_with_copyright(base: str, game_id: str = "") -> str:
    """Every window title carries the game id and the rights notice."""
    game = f"  |  Game: {game_id}" if game_id else ""
    return f"{base}{game}  -  {COPYRIGHT_TITLE}"


class PeerWindow:
    """Window chrome shared by live and replay modes."""

    def __init__(self, title: str, board_size: int, speed: float, game_id: str = ""):
        self.root = tk.Tk()
        self.root.title(title_with_copyright(title, game_id))
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

    def add_menu(self, about: dict, with_pdf: bool = True) -> None:
        """Menu bar: Help -> About, and Help -> Open guidelines PDF."""
        menubar = tk.Menu(self.root)
        helpm = tk.Menu(menubar, tearoff=0)
        helpm.add_command(label="About", command=lambda: self._show_about(about))
        if with_pdf:
            helpm.add_command(label="Open guidelines PDF (new window)",
                              command=self._open_pdf)
        menubar.add_cascade(label="Help", menu=helpm)
        self.root.config(menu=menubar)

    def _show_about(self, about: dict) -> None:
        top = tk.Toplevel(self.root)
        top.title("About - Police-Thief P2P")
        header = (f"Police-Thief P2P Simulator\nCode version:  v{CODE_VERSION}\n"
                  f"Guidelines book version:  v{BOOK_VERSION}")
        tk.Label(top, text=header, justify="left", anchor="w",
                 font=("Segoe UI", 11, "bold"), padx=14, pady=(12, 6)).pack(fill="x")
        tk.Label(top, text="License & Copyright", justify="left", anchor="w",
                 font=("Segoe UI", 10, "bold"), padx=14).pack(fill="x")
        tk.Label(top, text=LICENSE_NOTICE, justify="left", anchor="w", wraplength=560,
                 font=("Segoe UI", 9), padx=14, pady=(2, 8)).pack(fill="x")
        spec = "\n".join(f"{key}: {value}" for key, value in about.items())
        tk.Label(top, text="System spec\n" + spec, justify="left", anchor="w",
                 font=("Consolas", 9), padx=14, pady=(0, 10)).pack(fill="x")
        tk.Button(top, text="Close", command=top.destroy).pack(pady=(0, 10))

    def _open_pdf(self) -> None:
        path = str(GUIDELINES_PDF)
        if not GUIDELINES_PDF.exists():
            self.set_label("status", f"Guidelines PDF not found: {path}")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # noqa: S606  (opens the OS default viewer)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError:
            webbrowser.open(f"file://{path}")

    def set_turn(self, mine: bool, text: str | None = None) -> None:
        self.banner.config(bg=GREEN if mine else IDLE,
                           text=text or ("MY TURN - thinking..." if mine else "WAITING..."))

    def set_label(self, key: str, value: str) -> None:
        self.labels[key].config(text=value)

    def render(self, view: dict) -> None:
        self.board.render(view["position"], view["role"], view["barriers"],
                          view["visited"], view["belief"],
                          view.get("opponent_position"), view.get("opponent_role"),
                          view.get("message"))
        self.set_label("step", str(view["step"]))
        if "barriers_used" in view:
            self.set_label("barriers",
                           f"{view['barriers_used']} / {view['barriers_max']}")
