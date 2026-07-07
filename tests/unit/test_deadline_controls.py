"""Tests for step-deadline enforcement, short prompts, and game controls."""

import threading
import time

from police_thief.constants import MoveType, Role
from police_thief.domain.belief import BeliefGrid
from police_thief.domain.brains import ThiefBrain
from police_thief.domain.own_state import OwnGameState
from police_thief.peer.controls import GameControls


class SlowLlm:
    """Never answers within a tight deadline."""

    def __init__(self, delay=1.0):
        self.delay = delay
        self.prompts = []

    def send(self, prompt):
        self.prompts.append(prompt)
        time.sleep(self.delay)
        return "too late anyway"


def view():
    return {
        "state": OwnGameState(role=Role.THIEF, start=(5, 5), board_size=10),
        "belief": BeliefGrid(board_size=10),
        "opponent_hint": "hi",
        "setting": "New York",
        "barriers_max": 20,
    }


class TestDeadline:
    def test_missed_deadline_moves_randomly(self):
        brain = ThiefBrain(SlowLlm(delay=1.0))
        decision = brain.decide(**view(), deadline_seconds=0.05)
        assert decision.random_move is True
        assert decision.move_type in (MoveType.MOVE, MoveType.HOLD)
        assert decision.response_seconds < 0.5  # enforced, did NOT wait for the LLM

    def test_short_deadline_uses_compact_prompt(self):
        llm = SlowLlm(delay=0.0)
        brain = ThiefBrain(llm)
        brain.decide(**view(), deadline_seconds=5, short_threshold=10)  # 5 < 10 -> short
        short_prompt = llm.prompts[-1]
        brain.decide(**view(), deadline_seconds=60, short_threshold=10)  # 60 > 10 -> full
        full_prompt = llm.prompts[-1]
        assert len(short_prompt) < len(full_prompt)
        assert "Evade the cop" not in short_prompt
        assert "Evade the cop" in full_prompt

    def test_no_deadline_waits_for_llm(self):
        brain = ThiefBrain(SlowLlm(delay=0.1))
        decision = brain.decide(**view())
        assert decision.random_move is False
        assert decision.response_seconds >= 0.1


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
