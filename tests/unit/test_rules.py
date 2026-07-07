"""Tests for win/end conditions evaluated on a peer's OWN state."""

from police_thief.constants import Direction, MoveType, Role
from police_thief.domain.own_state import OwnGameState
from police_thief.domain.rules import GameRules


def rules(max_steps=50, unique=50):
    return GameRules(max_steps=max_steps, unique_cells_to_win=unique)


class TestGameRules:
    def test_no_result_early(self):
        state = OwnGameState(role=Role.THIEF, start=(5, 5), board_size=10)
        assert rules().thief_result(state) is None

    def test_thief_survival_win_at_max_steps(self):
        state = OwnGameState(role=Role.THIEF, start=(5, 5), board_size=10)
        game_rules = rules(max_steps=3, unique=50)
        for direction in (Direction.N, Direction.S, Direction.N):
            state.apply_move(MoveType.MOVE, direction)
        assert game_rules.thief_result(state) == "survival"

    def test_thief_unique_cells_win(self):
        state = OwnGameState(role=Role.THIEF, start=(0, 0), board_size=10)
        game_rules = rules(max_steps=50, unique=3)
        state.apply_move(MoveType.MOVE, Direction.E)
        assert game_rules.thief_result(state) is None
        state.apply_move(MoveType.MOVE, Direction.E)
        assert game_rules.thief_result(state) == "unique_cells"

    def test_max_steps_configurable(self):
        state = OwnGameState(role=Role.THIEF, start=(5, 5), board_size=10)
        game_rules = rules(max_steps=1, unique=50)
        state.apply_move(MoveType.MOVE, Direction.N)
        assert game_rules.thief_result(state) == "survival"

    def test_capture_claim_check(self):
        state = OwnGameState(role=Role.THIEF, start=(5, 5), board_size=10)
        assert rules().is_captured(state, claim=(5, 5))
        assert not rules().is_captured(state, claim=(4, 5))
