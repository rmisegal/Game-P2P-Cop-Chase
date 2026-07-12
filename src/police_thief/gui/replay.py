# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""ReplayApp: the mandatory Visual Replay Player (book section 7).

Feeds a saved match log back through the pure domain (belief grid rebuilds from
the recorded smell grids) and re-verifies each step's commit hash live. When the
opponent's sibling log is found, BOTH true positions are drawn on the one board.
"""

import json

from police_thief.domain.belief import BeliefGrid
from police_thief.domain.crypto import CommitReveal
from police_thief.exceptions import CryptoError
from police_thief.gui.replay_data import (  # noqa: F401  (normalize_log re-exported)
    discover_subgames,
    frozen_message,
    move_labels,
    normalize_log,
    opponent_positions,
    subgame_log_path,
)

_OPPONENT = {"police": "thief", "thief": "police", "cop": "thief"}


class ReplayApp:
    """Steps through one peer's saved log with play/pause, restart, jump-to-step,
    sub-game switching, and the opponent overlaid on the same board."""

    def __init__(self, config, log_data: dict, log_path=None):
        from police_thief.gui.replay_controls import build_controls
        from police_thief.gui.window import PeerWindow

        self._config = config
        self._log_path = log_path
        self._size = config.get("board.size")
        self._game_id = log_data.get("game_id", "")
        self._window = PeerWindow("REPLAY", self._size,
                                  config.get("play.step_speed_seconds"), self._game_id)
        self._ingest(log_data)
        subs = discover_subgames(log_path, log_data)
        build_controls(self, subs, self._sub_game)

    def _ingest(self, log_data: dict) -> None:
        """Load one sub-game's log into the player and reset stepping state."""
        view = normalize_log(log_data)
        self._records = [r for r in view["records"]
                         if r["payload"].get("type") != "system_spec"]
        self._history = view["history"]
        self._my_log = view["my_log"]
        self._role = view["role"]
        self._result, self._winner, self._audit = (
            view["result"], view["winner"], view["audit"])
        self._sub_game = view["sub_game_number"]
        self._opponent_pos = opponent_positions(self._log_path, log_data)
        self._opponent_role = _OPPONENT.get(self._role, "thief")
        spec = next((r["payload"] for r in view["records"]
                     if r["payload"].get("type") == "system_spec"), {})
        self._window.add_menu({
            "code_version": spec.get("code_version", "-"),
            "model": spec.get("model", "-"), **spec.get("spec", {}),
        })
        self._window.set_label("model", spec.get("model", "-"))
        self._window.root.title(
            f"REPLAY: {view['group']} | sub-game {self._sub_game} | "
            f"{self._role} | {view['duration_seconds']}s"
            f"  |  Game: {self._game_id}  -  (c) 2026 Dr. Yoram Segal - all rights reserved")
        self._reset_state()

    def _reset_state(self) -> None:
        self._belief = BeliefGrid(board_size=self._size)
        self._barriers, self._visited = set(), set()
        self._index, self._playing = 0, False

    def _total_steps(self) -> int:
        # Run until the LONGEST track is exhausted so the extra steps of a peer
        # that moved more times are still shown (the shorter one freezes).
        return max(len(self._my_log), len(self._history), len(self._opponent_pos))

    def _verify_record(self, index: int) -> str:
        if index >= len(self._records):
            return "-"
        record = self._records[index]
        try:
            CommitReveal.verify(record["payload"], record["nonce"], record["commit"])
            return "verified OK"
        except CryptoError:
            return "TAMPERED!"

    def _advance(self) -> None:
        steps = self._total_steps()
        if self._index >= steps:
            self._window.set_turn(False, f"REPLAY DONE: {self._result} - "
                                         f"winner {str(self._winner).upper()} "
                                         f"(press Restart to replay)")
            self._playing = False
            return
        i = self._index
        if i < len(self._my_log):
            entry = self._my_log[i]
            self._visited.add(tuple(entry["position"]))
            if entry.get("barrier"):
                self._barriers.add(tuple(entry["barrier"]))
            record = self._records[i] if i < len(self._records) else {}
            labels = move_labels(record.get("payload", {}),
                                 record.get("commit", "-"), self._verify_record(i))
            for key, value in labels.items():
                self._window.set_label(key, value)
        if i < len(self._history):
            message = self._history[i]
            self._belief.diffuse()
            self._belief.observe_smell(message["smell_grid"])
            if message.get("barrier_placed"):
                self._barriers.add(tuple(message["barrier_placed"]))
            self._window.set_label("hint_in", message["hint"])
        my_len, opp_len = len(self._my_log), len(self._opponent_pos)
        position = tuple(self._my_log[min(i, my_len - 1)]["position"]) if my_len else None
        opp = tuple(self._opponent_pos[min(i, opp_len - 1)]) if opp_len else None
        self._window.render({
            "role": self._role, "step": i + 1, "position": position,
            "barriers": self._barriers, "visited": self._visited,
            "belief": self._belief.as_matrix(),
            "opponent_position": opp, "opponent_role": self._opponent_role,
            "message": frozen_message(i, my_len, self._role, opp_len,
                                      self._opponent_role),
        })
        both = " | BOTH agents shown" if self._opponent_pos else " | opponent log missing"
        self._window.set_label(
            "status", f"step {i + 1}/{steps} | opponent audit: "
                      f"{'PASSED' if self._audit['passed'] else 'FAILED'}{both}")
        self._index += 1

    def _restart(self) -> None:
        self._reset_state()
        self._window.render({
            "role": self._role, "step": 0, "position": None, "barriers": set(),
            "visited": set(), "belief": self._belief.as_matrix()})
        self._window.set_turn(False, "RESTARTED - press Play")

    def _goto(self, step: int) -> None:
        self._reset_state()
        target = max(1, min(step, self._total_steps()))
        for _ in range(target):
            self._advance()

    def _select_subgame(self, sub: int) -> None:
        path = subgame_log_path(self._log_path, {"game_id": self._game_id}, sub)
        if not path.exists():
            self._window.set_label("status", f"sub-game log not found: {path.name}")
            return
        self._log_path = str(path)
        self._ingest(json.loads(path.read_text(encoding="utf-8")))
        self._window.set_turn(False, f"Loaded sub-game {sub} - press Play")

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
