# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Per-peer Tkinter apps: LivePeerApp (my agent, live) and ReplayApp (log).

GREEN banner = my turn (opponent's message arrived) until my move is delivered.
The board shows MY truth (position/visited/barriers) and the opponent belief
heatmap — the opponent's true position is unknowable by design.
"""

import queue
import threading
import time
import tkinter as tk

from police_thief.gui.game_mode import mode_and_model
from police_thief.gui.replay import ReplayApp  # noqa: F401  (re-export for cli)
from police_thief.gui.window import PeerWindow, title_with_copyright


class LivePeerApp:
    """Runs my standalone agent in a thread and mirrors it in a window."""

    def __init__(self, sdk, role: str, stub_llm: bool = False):
        self._sdk = sdk
        self._role = role
        self._stub = stub_llm
        self._events: queue.Queue = queue.Queue()
        self._outcome: dict | None = None
        from police_thief.peer.controls import GameControls

        self._controls = GameControls()
        game_id = (f"{sdk.config.get('game.group_name', 'unnamed')}"
                   f"-vs-{sdk.config.get('game.opponent_group_name', 'opponent')}")
        self._title_base = title_with_copyright(
            f"{sdk.config.get('game.group_name', 'unnamed')} | "
            f"sub-game {sdk.config.get('game.sub_game_number', 1)} | "
            f"{role.upper()}", game_id)
        self._t0: float | None = None
        budget = sdk.config.get("llm.step_deadline_seconds", 30)
        self._window = PeerWindow(
            f"Police-Thief peer: {role.upper()}",
            sdk.config.get("board.size"),
            budget,  # slider = enforced step time budget, initial from config
        )
        self._controls.set_speed(budget)
        self._window.speed.trace_add(
            "write", lambda *_: self._controls.set_speed(self._window.speed.get()))
        from police_thief.shared.sysinfo import collect_spec
        from police_thief.shared.version import CODE_VERSION

        # Verbal-game mode + model per book Table 22 (the MOVE is always Python).
        game_mode, model_label = mode_and_model(sdk.config)
        self._window.add_menu({
            "code_version": CODE_VERSION, "role": role,
            "game_mode": game_mode, "model": model_label,
            **collect_spec(),
        })
        self._window.set_label("mode", game_mode)
        self._window.set_label("model", model_label)
        self._window.root.title(self._title_base)
        controls_bar = tk.Frame(self._window.root)
        controls_bar.pack(pady=(0, 6))
        tk.Button(controls_bar, text="Pause", command=self._pause).pack(side="left")
        tk.Button(controls_bar, text="Play", command=self._play).pack(side="left", padx=6)
        tk.Button(controls_bar, text="Stop", command=self._stop).pack(side="left")

    def _pause(self) -> None:
        self._controls.pause()
        self._window.set_turn(False, "PAUSED (my agent only)")

    def _play(self) -> None:
        self._controls.play()
        self._window.set_turn(True, "RESUMED - my turn continues")

    def _stop(self) -> None:
        self._controls.stop()
        self._window.set_turn(False, "STOPPED - game cancelled")

    def _tick_clock(self) -> None:
        if self._t0 is not None:
            elapsed = int(time.monotonic() - self._t0)
            self._window.root.title(
                f"{self._title_base} | {elapsed // 60:02d}:{elapsed % 60:02d}")
        self._window.root.after(1000, self._tick_clock)

    def _listener(self, event: dict) -> None:
        """Called from the runtime thread: enqueue for GUI, pace the game.

        The slider is the TOTAL step budget: a fast LLM answer is padded up to
        it, a slow one was already cut off by the enforced deadline. 0 = flat out.
        """
        self._events.put(event)
        if event["type"] == "moved":
            spent = event["decision"].response_seconds
            time.sleep(max(0.0, self._window.speed.get() - spent))

    def _worker(self) -> None:
        try:
            self._outcome = self._sdk.run_peer(self._role, stub_llm=self._stub,
                                               listener=self._listener,
                                               controls=self._controls)
        except Exception as exc:  # surface startup/runtime failures in the window
            self._events.put({"type": "error", "message": str(exc)})

    def _poll(self) -> None:
        while not self._events.empty():
            self._apply(self._events.get_nowait())
        self._window.root.after(100, self._poll)

    def _apply(self, event: dict) -> None:
        window = self._window
        kind = event["type"]
        if kind == "error":
            window.set_turn(False, "ERROR - see status")
            window.set_label("status", event["message"])
            return
        window.render(event["view"])
        if kind == "negotiated":
            self._t0 = time.monotonic()  # game clock starts at agreement
            window.set_label("status", "Agreement signed & verified (SHA-256)")
            window.set_turn(self._role == "thief")  # thief moves first
        elif kind == "incoming":
            message = event["message"]
            window.set_label("hint_in", f"step {message['step']}: {message['hint']}")
            window.set_turn(True)
        elif kind == "moved":
            decision = event["decision"]
            usage = event.get("usage", {})
            # The Model/Game-mode rows stay fixed to the Table-22 config mode; the
            # actual per-step token spend is shown in Tokens / LLM response instead.
            window.set_label("tokens",
                             f"{usage.get('total', 0):,} / {usage.get('match_total', 0):,}")
            window.set_label("llm_time", f"{decision.response_seconds:.2f}"
                             + (" [RANDOM - deadline missed]" if decision.random_move
                                else ""))
            window.set_label("hint_out", f"step {event['view']['step']}: {decision.hint}")
            window.set_label("verdict", decision.verdict
                             + (" (fallback policy)" if decision.fallback else ""))
            window.set_label("commit", event["commit"][:32] + "...")
            window.set_turn(False)
        elif kind == "game_over":
            summary = event["summary"]
            audit = summary["audit"]
            verdict = "PASSED" if audit["passed"] else "FAILED"
            window.set_turn(False, f"GAME OVER: {summary['result']} - "
                                   f"winner {summary['winner'].upper()}")
            self._t0 = None  # freeze the title clock
            window.set_label("status", f"Audit {verdict}: "
                                       f"{audit['verified_steps']} steps verified | "
                                       f"tokens total: {summary.get('tokens_total', 0):,} | "
                                       f"duration: {summary.get('duration_seconds', 0)}s")

    def run(self) -> dict:
        threading.Thread(target=self._worker, daemon=True).start()
        self._window.root.after(100, self._poll)
        self._window.root.after(1000, self._tick_clock)
        self._window.root.mainloop()
        return self._outcome or {"summary": {"result": "aborted", "winner": "-",
                                             "steps": 0}, "email": {"sent": False},
                                 "log_path": "-"}
