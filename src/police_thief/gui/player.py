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

from police_thief.gui import live_apply
from police_thief.gui.game_mode import mode_and_model
from police_thief.gui.live_controls import LiveControls, clamp_subgames
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
        group = sdk.config.get("game.group_name", "unnamed")
        opponent = sdk.config.get("game.opponent_group_name", "opponent")
        self._title_base = title_with_copyright(
            f"{group} | sub-game {sdk.config.get('game.sub_game_number', 1)} | "
            f"{role.upper()}", f"{group}-vs-{opponent}")
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
        self._bidi_i = False   # I opted into the bidirectional channel
        self._bidi_peer = False  # the opponent opted in
        self._window.add_menu({
            "code_version": CODE_VERSION, "role": role,
            "game_mode": game_mode, "model": model_label,
            **collect_spec(),
        }, on_bidirectional=self._toggle_bidirectional)
        self._window.set_label("mode", game_mode)
        self._window.set_label("model", model_label)
        self._window.root.title(self._title_base)
        self._started = False
        self._bar = LiveControls(
            self._window.root, self, clamp_subgames(sdk.config.get("game.num_games", 1)))

    def _start(self) -> None:
        """Begin the series: apply the chosen sub-game count, then run the worker."""
        if self._started:
            return
        self._started = True
        num_games = self._bar.selected_subgames()
        self._sdk.config.override("game.num_games", num_games)
        self._bar.mark_started()
        self._window.set_turn(False, f"STARTING - {num_games} sub-game(s)")
        threading.Thread(target=self._worker, daemon=True).start()
        self._window.root.after(1000, self._tick_clock)

    def _quit(self) -> None:
        """Clean shutdown of THIS peer; the runtime sends a quit notice to the
        opponent on its next control check, so give it a moment before closing."""
        self._controls.request_quit()
        self._controls.stop()
        self._window.set_turn(False, "QUITTING - notifying opponent...")
        self._window.root.after(400, self._window.root.destroy)

    def _restart(self) -> None:
        """Ask the opponent to restart the whole series (auto-approved when active)."""
        self._controls.request_restart()
        self._window.set_turn(False, "RESTART requested (whole series)")

    def _toggle_bidirectional(self, enabled: bool) -> None:
        """Tools menu: opt into the bidirectional control channel (one-way for the
        session). Active only once the opponent opts in too."""
        if enabled and not self._bidi_i:
            self._bidi_i = True
            self._controls.request_enable()
            self._window.set_label("opp_status", "waiting for opponent to enable...")
            live_apply.activate_if_ready(self)

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
        live_apply.apply_event(self, event)

    def run(self) -> dict:
        # The window opens idle; the worker starts only when the user presses Start.
        self._window.set_turn(False, "READY - choose sub-games, then press Start")
        self._window.root.after(100, self._poll)
        self._window.root.mainloop()
        return self._outcome or {"summary": {"result": "aborted", "winner": "-",
                                             "steps": 0}, "email": {"sent": False},
                                 "log_path": "-"}
