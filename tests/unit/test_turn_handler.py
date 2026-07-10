"""Tests for TurnHandler: applying an opponent's TurnMessage to my own view."""

import pytest

from police_thief.constants import Role
from police_thief.domain.belief import BeliefGrid
from police_thief.domain.own_state import OwnGameState
from police_thief.domain.protocol import TurnMessage
from police_thief.domain.rules import GameRules
from police_thief.domain.smell import SmellField
from police_thief.peer.turn_handler import TurnHandler


@pytest.fixture
def handler():
    state = OwnGameState(role=Role.THIEF, start=(5, 5), board_size=10)
    belief = BeliefGrid(board_size=10)
    smell = SmellField(board_size=10, grid_size=5, decay=0.1, min_center=0.5)
    rules = GameRules(max_steps=50)
    return TurnHandler(state=state, belief=belief, smell_field=smell, rules=rules)


def msg(**overrides):
    base = {
        "step": 1,
        "sender": "police",
        "hint": "Closing in from the flank.",
        "smell_grid": {"7,5": 0.8},
        "commit": "cc" * 32,
        "timestamp": "2026-07-06T10:00:00Z",
        "barrier_placed": None,
        "capture_claim": None,
        "claim_response": None,
        "win_claim": None,
    }
    base.update(overrides)
    return TurnMessage.from_dict(base)


class TestTurnHandler:
    def test_updates_belief_toward_smell(self, handler):
        handler.process(msg())
        probs = handler.belief.as_matrix()
        assert probs[7][5] > probs[0][0]

    def test_notes_declared_barrier(self, handler):
        handler.process(msg(barrier_placed=[6, 4]))
        assert (6, 4) in handler.state.barriers

    def test_capture_claim_hit(self, handler):
        outcome = handler.process(msg(capture_claim=[5, 5]))  # my true cell
        assert outcome.i_am_caught is True
        assert outcome.claim_response == {"claim": [5, 5], "caught": True}

    def test_capture_claim_miss(self, handler):
        outcome = handler.process(msg(capture_claim=[2, 2]))
        assert outcome.i_am_caught is False
        assert outcome.claim_response == {"claim": [2, 2], "caught": False}

    def test_opponent_win_claim_flagged(self, handler):
        outcome = handler.process(msg(win_claim={"type": "survival"}))
        assert outcome.opponent_won is True

    def test_caught_confirmation_means_i_won(self, handler):
        outcome = handler.process(msg(claim_response={"claim": [3, 3], "caught": True}))
        assert outcome.i_won is True

    def test_plain_message_no_flags(self, handler):
        outcome = handler.process(msg())
        assert not outcome.i_won and not outcome.i_am_caught and not outcome.opponent_won
        assert outcome.claim_response is None
