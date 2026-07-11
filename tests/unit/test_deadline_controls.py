"""Tests: the move is instant (never waits on the LLM), plus game controls."""

import threading
import time

from police_thief.constants import MoveType, Role
from police_thief.domain.belief import BeliefGrid
from police_thief.domain.brains import ThiefBrain
from police_thief.domain.own_state import OwnGameState
from police_thief.peer.controls import GameControls


def view():
    return {
        "state": OwnGameState(role=Role.THIEF, start=(5, 5), board_size=10),
        "belief": BeliefGrid(board_size=10),
        "opponent_hint": "hi",
        "setting": "New York",
        "barriers_max": 20,
    }


class TestMoveIsInstant:
    def test_move_does_not_wait_on_the_llm(self):
        # A slow/exploding LLM must not affect the move: the default trash provider
        # is template (no LLM), and the move is chosen in pure Python regardless.
        class SlowBoomLlm:
            def send(self, prompt):
                time.sleep(5)  # would blow any deadline — but it's never called
                raise AssertionError("LLM must not be consulted for the move")

        decision = ThiefBrain(SlowBoomLlm()).decide(**view(), deadline_seconds=0.05)
        assert decision.move_type in (MoveType.MOVE, MoveType.HOLD)
        assert decision.response_seconds < 0.5  # did NOT wait for any LLM


class TestGameControls:
    def test_pause_blocks_and_play_releases(self):
        controls = GameControls()
        controls.pause()
        released = threading.Event()

        def waiter():
            controls.wait_if_paused()
            released.set()

        threading.Thread(target=waiter, daemon=True).start()
        time.sleep(0.1)
        assert not released.is_set()  # still paused
        controls.play()
        assert released.wait(timeout=2)

    def test_stop_releases_paused_waiter(self):
        controls = GameControls()
        controls.pause()
        controls.stop()
        controls.wait_if_paused()  # returns instead of hanging
        assert controls.stopped

    def test_stop_aborts_runtime(self, config):
        import queue

        from police_thief.peer.runtime import PeerRuntime

        class DeadTransport:
            def poll_turn(self, timeout):
                try:
                    return queue.Queue().get(timeout=timeout)
                except queue.Empty:
                    return None

        class NoLlm:
            def send(self, prompt):
                return "x"

        controls = GameControls()
        runtime = PeerRuntime(Role.POLICE, config, NoLlm(), DeadTransport(),
                              controls=controls)
        result_box = {}

        def run():
            result_box["summary"] = runtime.run(skip_negotiation=True)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        time.sleep(0.2)
        controls.stop()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert result_box["summary"]["result"] == "stopped"
        assert result_box["summary"]["audit"].get("skipped") is True
