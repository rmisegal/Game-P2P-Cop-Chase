"""Tests: the MOVE is pure-Python strategy (never the LLM); the hint is trash talk."""

from police_thief.constants import Direction, MoveType, Role
from police_thief.domain.belief import BeliefGrid
from police_thief.domain.brains import PoliceBrain, ThiefBrain
from police_thief.domain.own_state import OwnGameState


class BoomLlm:
    """Raises if the move path ever touches the LLM — it must not."""

    def send(self, prompt):
        raise AssertionError("the LLM must NOT be consulted for the move")


class FakeRng:
    """Deterministic rng: choice -> first element, random -> a fixed value."""

    def __init__(self, value=0.99):
        self._value = value

    def choice(self, seq):
        return seq[0]

    def random(self):
        return self._value


def make_view(role=Role.THIEF, start=(5, 5)):
    return {
        "state": OwnGameState(role=role, start=start, board_size=10),
        "belief": BeliefGrid(board_size=10),
        "opponent_hint": "I am near the park.",
        "setting": "New York",
        "barriers_max": 20,
    }


class TestMoveIsPurePython:
    def test_move_never_calls_the_llm(self):
        # BoomLlm raises if consulted; the default trash provider is template (no LLM).
        decision = ThiefBrain(BoomLlm()).decide(**make_view())
        assert decision.move_type in (MoveType.MOVE, MoveType.HOLD)

    def test_move_is_a_legal_step(self):
        view = make_view(start=(0, 0))
        decision = ThiefBrain(BoomLlm(), rng=FakeRng()).decide(**view)
        if decision.move_type is MoveType.MOVE:
            assert view["state"].board.step((0, 0), decision.direction, set()) is not None

    def test_thief_never_places_a_barrier(self):
        # even with an rng that would trigger a barrier, the thief can't wall.
        decision = ThiefBrain(BoomLlm(), rng=FakeRng(value=0.0)).decide(**make_view())
        assert decision.move_type is not MoveType.BARRIER

    def test_no_legal_move_holds(self):
        view = make_view(start=(5, 5))
        state = view["state"]
        for direction in Direction:  # wall every neighbour of (5, 5)
            cell = state.board.step((5, 5), direction, set())
            if cell:
                state.barriers.add(cell)
        decision = ThiefBrain(BoomLlm()).decide(**view)
        assert decision.move_type is MoveType.HOLD


class TestPoliceBarrier:
    def test_police_can_place_a_barrier(self):
        decision = PoliceBrain(BoomLlm(), rng=FakeRng(value=0.0)).decide(
            **make_view(role=Role.POLICE, start=(7, 5)))
        assert decision.move_type is MoveType.BARRIER
        assert decision.direction is not None

    def test_police_moves_when_barrier_roll_fails(self):
        decision = PoliceBrain(BoomLlm(), rng=FakeRng(value=0.99)).decide(
            **make_view(role=Role.POLICE, start=(7, 5)))
        assert decision.move_type is MoveType.MOVE


class TestTrashTalkHint:
    def test_default_hint_is_a_free_template(self):
        decision = ThiefBrain(BoomLlm()).decide(**make_view())
        assert decision.hint                       # a canned banter line
        assert decision.verdict in ("truth", "lie")
        assert decision.prompt_text == ""          # template => no LLM prompt logged
        assert decision.reasoning == ""
        assert decision.response_seconds < 0.5     # instant, no network
