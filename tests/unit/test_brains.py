"""Tests for agent brains: prompt building, strict parsing, legal fallback."""

import json

from police_thief.constants import Direction, MoveType, Role
from police_thief.domain.belief import BeliefGrid
from police_thief.domain.brains import PoliceBrain, ThiefBrain
from police_thief.domain.own_state import OwnGameState


class StubLlm:
    """Scripted LLM: returns queued replies, records prompts."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def send(self, prompt):
        self.prompts.append(prompt)
        return self.replies.pop(0)


def make_view(role=Role.THIEF, start=(5, 5)):
    return {
        "state": OwnGameState(role=role, start=start, board_size=10),
        "belief": BeliefGrid(board_size=10),
        "opponent_hint": "I am near the park.",
        "setting": "New York",
        "barriers_max": 20,
    }


GOOD_REPLY = json.dumps(
    {"message": "Heading to the docks!", "move": {"type": "MOVE", "dir": "N"}, "verdict": "lie"}
)


class TestBrainParsing:
    def test_valid_reply_parsed(self):
        brain = ThiefBrain(StubLlm([GOOD_REPLY]))
        decision = brain.decide(**make_view())
        assert decision.move_type is MoveType.MOVE
        assert decision.direction is Direction.N
        assert decision.verdict == "lie"
        assert "docks" in decision.hint

    def test_illegal_move_falls_back_to_legal(self):
        reply = json.dumps(
            {"message": "hi", "move": {"type": "MOVE", "dir": "N"}, "verdict": "truth"}
        )
        brain = ThiefBrain(StubLlm([reply]))
        decision = brain.decide(**make_view(start=(0, 0)))  # N is off-board
        assert decision.move_type in (MoveType.MOVE, MoveType.HOLD)
        if decision.move_type is MoveType.MOVE:
            state = make_view(start=(0, 0))["state"]
            assert state.board.step((0, 0), decision.direction, set()) is not None

    def test_garbage_reply_falls_back(self):
        brain = ThiefBrain(StubLlm(["I like to move north-ish maybe?"]))
        decision = brain.decide(**make_view())
        assert decision.move_type is not None
        assert decision.hint  # fallback still produces a hint

    def test_thief_barrier_request_downgraded(self):
        reply = json.dumps(
            {"message": "wall!", "move": {"type": "BARRIER", "dir": "N"}, "verdict": "truth"}
        )
        decision = ThiefBrain(StubLlm([reply])).decide(**make_view())
        assert decision.move_type is not MoveType.BARRIER  # thief can't barrier

    def test_police_barrier_allowed(self):
        reply = json.dumps(
            {"message": "roadblock deployed", "move": {"type": "BARRIER", "dir": "N"},
             "verdict": "truth"}
        )
        decision = PoliceBrain(StubLlm([reply])).decide(
            **make_view(role=Role.POLICE, start=(7, 5))
        )
        assert decision.move_type is MoveType.BARRIER
        assert decision.direction is Direction.N


class TestPromptContent:
    def test_prompt_contains_own_view_only(self):
        stub = StubLlm([GOOD_REPLY])
        ThiefBrain(stub).decide(**make_view())
        prompt = stub.prompts[0]
        assert "(5, 5)" in prompt or "[5, 5]" in prompt   # my true position
        assert "New York" in prompt                        # negotiated setting
        assert "I am near the park." in prompt             # opponent's NL hint

    def test_police_prompt_mentions_lie_detection(self):
        stub = StubLlm([GOOD_REPLY])
        PoliceBrain(stub).decide(**make_view(role=Role.POLICE, start=(7, 5)))
        assert "lie" in stub.prompts[0].lower()

    def test_llm_exception_falls_back(self):
        class BoomLlm:
            def send(self, prompt):
                raise RuntimeError("cli exploded")

        decision = ThiefBrain(BoomLlm()).decide(**make_view())
        assert decision.move_type is not None
        assert decision.fallback is True
