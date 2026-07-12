# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""The Visual Replay Player control bar: Play/Pause, Step, Restart, jump-to-step,
and a sub-game selector. Wired to ReplayApp methods; kept separate so replay.py
stays focused on stepping/rendering (and within the 150-line file budget)."""

import tkinter as tk


def build_controls(app, subgames: list, current_sub: int) -> None:
    """Attach the control bar to app._window.root, wired to app's methods."""
    bar = tk.Frame(app._window.root)
    bar.pack(pady=(0, 8))
    tk.Button(bar, text="Play / Pause", command=app._toggle).pack(side="left")
    tk.Button(bar, text="Step >", command=app._advance).pack(side="left", padx=6)
    tk.Button(bar, text="Restart", command=app._restart).pack(side="left")

    tk.Label(bar, text="  Go to step:").pack(side="left")
    step_var = tk.StringVar(value="1")
    tk.Spinbox(bar, from_=1, to=9999, width=5, textvariable=step_var).pack(side="left")
    tk.Button(bar, text="Go",
              command=lambda: app._goto(_as_int(step_var.get(), 1))).pack(side="left", padx=6)

    if subgames:
        tk.Label(bar, text="  Sub-game:").pack(side="left")
        sub_var = tk.IntVar(value=current_sub if current_sub in subgames else subgames[0])
        options = [str(n) for n in subgames]
        menu = tk.OptionMenu(bar, tk.StringVar(value=str(sub_var.get())), *options,
                             command=lambda v: app._select_subgame(int(v)))
        menu.pack(side="left")


def _as_int(text: str, default: int) -> int:
    try:
        return int(text)
    except (TypeError, ValueError):
        return default
