# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""ReplayApp: the mandatory Visual Replay Player (book section 7).

Feeds a saved match log back through the pure domain (belief grid rebuilds
from the recorded smell grids) and re-verifies each step's commit hash live,
showing hint, verdict reveal, smell, and crypto status per step.
"""

import json
import tkinter as tk

from police_thief.domain.belief import BeliefGrid
from police_thief.domain.crypto import CommitReveal
from police_thief.exceptions import CryptoError


def normalize_log(log_data: dict) -> dict:
    """Accept EITHER the legacy match log (records/history/my_log nested under
    'summary') OR the standardized template log (records at top level, no smell
    'history'). Returns a uniform view; when the smell history is absent the
    belief heatmap simply stays flat while crypto re-verification still runs."""
    summary = log_data.get("summary", {})
    records = log_data.get("records") or summary.get("records", [])
    my_log = summary.get("my_log")
    if my_log is None:  # standardized format: rebuild a minimal move log from records
        my_log = [
            {"position": r["payload"].get("position", [0, 0]), "barrier": None}
            for r in records
            if r.get("payload", {}).get("type") != "system_spec"
        ]
    return {
        "summary": summary,
        "records": records,
        "history": summary.get("history", []),
        "my_log": my_log,
        "role": summary.get("role", "-"),
        "result": summary.get("result", "-"),
        "winner": summary.get("winner") or summary.get("winner_role", "-"),
        "group": summary.get("group_name") or summary.get("group_id", "unnamed"),
        "sub_game_number": summary.get("sub_game_number", 1),
        "duration_seconds": summary.get("duration_seconds", 0),
        "audit": summary.get("audit", {"passed": True}),
    }


class ReplayApp:
    """Steps through one peer's saved log with play/pause + speed control."""

    def __init__(self, config, log_data: dict):
        from police_thief.gui.window import PeerWindow

        view = normalize_log(log_data)
        self._summary = view["summary"]
        self._records = view["records"]
        self._history = view["history"]
        self._my_log = view["my_log"]
        self._role = view["role"]
        self._result = view["result"]
        self._winner = view["winner"]
        self._audit = view["audit"]
        size = config.get("board.size")
        self._belief = BeliefGrid(board_size=size)
        self._barriers: set = set()
        self._visited: set = set()
        self._index = 0
        self._playing = False
        self._window = PeerWindow(
            f"REPLAY: {view['group']} | sub-game {view['sub_game_number']} | "
            f"{view['role']} | {view['duration_seconds']}s",
            size, config.get("play.step_speed_seconds"))
        spec = next((r["payload"] for r in self._records
                     if r["payload"].get("type") == "system_spec"), {})
        if spec:
            self._window.add_about_button({
                "code_version": spec.get("code_version", "-"),
                "model": spec.get("model", "-"), **spec.get("spec", {}),
            })
            self._window.set_label("model", spec.get("model", "-"))
        self._records = [r for r in self._records
                         if r["payload"].get("type") != "system_spec"]
        controls = tk.Frame(self._window.root)
        controls.pack(pady=(0, 8))
        tk.Button(controls, text="Play / Pause", command=self._toggle).pack(side="left")
        tk.Button(controls, text="Step >", command=self._advance).pack(side="left", padx=6)

    def _verify_record(self, index: int) -> str:
        """Re-verify my sealed record for this step against its revealed nonce."""
        if index >= len(self._records):
            return "-"
        record = self._records[index]
        try:
            CommitReveal.verify(record["payload"], record["nonce"], record["commit"])
            return "verified OK"
        except CryptoError:
            return "TAMPERED!"

    def _advance(self) -> None:
        steps = max(len(self._my_log), len(self._history))
        if self._index >= steps:
            self._window.set_turn(False, f"REPLAY DONE: {self._result} - "
                                         f"winner {str(self._winner).upper()}")
            self._playing = False
            return
        i = self._index
        if i < len(self._my_log):
            entry = self._my_log[i]
            self._visited.add(tuple(entry["position"]))
            if entry.get("barrier"):
                self._barriers.add(tuple(entry["barrier"]))
            record = self._records[i] if i < len(self._records) else {}
            payload = record.get("payload", {})
            self._window.set_label("hint_out", payload.get("hint", "-"))
            self._window.set_label("model", payload.get("model", "-"))
            self._window.set_label(
                "tokens",
                f"{payload.get('tokens_step', 0):,} / {payload.get('tokens_total', 0):,}")
            self._window.set_label(
                "llm_time", f"{payload.get('response_seconds', 0):.2f}"
                            + (" [RANDOM]" if payload.get("random_move") else ""))
            self._window.set_label("verdict", f"{payload.get('verdict', '-')} (revealed)")
            self._window.set_label(
                "commit", f"{record.get('commit', '-')[:24]}... [{self._verify_record(i)}]")
        if i < len(self._history):
            message = self._history[i]
            self._belief.diffuse()
            self._belief.observe_smell(message["smell_grid"])
            if message.get("barrier_placed"):
                self._barriers.add(tuple(message["barrier_placed"]))
            self._window.set_label("hint_in", message["hint"])
        position = tuple(self._my_log[min(i, len(self._my_log) - 1)]["position"])
        self._window.render({
            "role": self._role, "step": i + 1, "position": position,
            "barriers": self._barriers, "visited": self._visited,
            "belief": self._belief.as_matrix(),
        })
        audit = self._audit
        self._window.set_label(
            "status", f"step {i + 1}/{steps} | opponent audit: "
                      f"{'PASSED' if audit['passed'] else 'FAILED'}")
        self._index += 1

    def _toggle(self) -> None:
        self._playing = not self._playing
        if self._playing:
            self._tick()

    def _tick(self) -> None:
        if not self._playing:
            return
        self._advance()
        delay_ms = max(50, int(self._window.speed.get() * 1000))
        self._window.root.after(delay_ms, self._tick)

    def run(self) -> None:
        self._window.set_turn(False, "REPLAY - press Play")
        self._window.root.mainloop()


def load_log_file(path: str) -> dict:  # small helper for ad-hoc use
    with open(path, encoding="utf-8") as f:
        return json.load(f)
