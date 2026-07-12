# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""LiveControls: the live-peer control bar. The window opens idle; the user picks
the number of sub-games, then presses Start to negotiate & play. Pause/Play/Stop
steer THIS peer; Quit shuts it down cleanly; Restart (enabled only under the
bidirectional channel) asks the opponent to restart the whole series."""

import tkinter as tk

SUB_GAME_CHOICES = (1, 2, 3, 4, 5, 6)


class LiveControls:
    """Owns the control-bar widgets; the app reads the dropdown and flips states."""

    def __init__(self, root, app, default_subgames: int):
        bar = tk.Frame(root)
        bar.pack(pady=(0, 6))
        tk.Label(bar, text="Sub-games:").pack(side="left")
        default = default_subgames if default_subgames in SUB_GAME_CHOICES else 1
        self.subgames = tk.IntVar(value=default)
        tk.OptionMenu(bar, self.subgames, *SUB_GAME_CHOICES).pack(side="left")
        self.start = tk.Button(bar, text="Start", command=app._start)
        self.start.pack(side="left", padx=(8, 0))
        self.pause = tk.Button(bar, text="Pause", command=app._pause, state="disabled")
        self.pause.pack(side="left", padx=(8, 0))
        self.play = tk.Button(bar, text="Play", command=app._play, state="disabled")
        self.play.pack(side="left")
        self.stop = tk.Button(bar, text="Stop", command=app._stop, state="disabled")
        self.stop.pack(side="left")
        self.restart = tk.Button(bar, text="Restart", command=app._restart,
                                 state="disabled")
        self.restart.pack(side="left", padx=(8, 0))
        self.quit = tk.Button(bar, text="Quit", command=app._quit)
        self.quit.pack(side="left", padx=(8, 0))

    def selected_subgames(self) -> int:
        return clamp_subgames(self.subgames.get())

    def mark_started(self) -> None:
        """Once the game is running: lock Start/dropdown, enable the live steers."""
        self.start.config(state="disabled")
        for button in (self.pause, self.play, self.stop):
            button.config(state="normal")

    def set_restart_enabled(self, enabled: bool) -> None:
        self.restart.config(state="normal" if enabled else "disabled")


def clamp_subgames(value) -> int:
    """Keep the sub-games count within the agreed 1..6 range (default 1)."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 1
    return min(6, max(1, number))
