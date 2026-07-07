"""Tests for OwnGameState: one peer's private, authoritative-for-itself state."""

from police_thief.constants import Direction, MoveType, Role
from police_thief.domain.own_state import OwnGameState


def make_state(role=Role.THIEF, start=(5, 5), board_size=10):
    return OwnGameState(role=role, start=start, board_size=board_size)


class TestOwnGameState:
    def test_initial_position_and_visited(self):
        state = make_state()
        assert state.position == (5, 5)
        assert state.unique_cells == 1

    def test_move_updates_position_and_visited(self):
        state = make_state()
        assert state.apply_move(MoveType.MOVE, Direction.N)
        assert state.position == (4, 5)
        assert state.unique_cells == 2

    def test_hold_does_not_count_unique(self):
        state = make_state()
        state.apply_move(MoveType.HOLD, None)
        assert state.position == (5, 5)
        assert state.unique_cells == 1

    def test_revisit_does_not_count_unique(self):
        state = make_state()
        state.apply_move(MoveType.MOVE, Direction.N)
        state.apply_move(MoveType.MOVE, Direction.S)  # back to start
        assert state.unique_cells == 2

    def test_illegal_move_rejected(self):
        state = make_state(start=(0, 0))
        assert not state.apply_move(MoveType.MOVE, Direction.N)  # off board
        assert state.position == (0, 0)

    def test_police_barrier_placement_and_quota(self):
        state = make_state(role=Role.POLICE, start=(7, 5))
        assert state.apply_move(MoveType.BARRIER, Direction.N, barriers_max=2)
        assert (6, 5) in state.barriers
        assert state.position == (7, 5)  # barrier instead of moving
        assert state.apply_move(MoveType.BARRIER, Direction.E, barriers_max=2)
        assert not state.apply_move(MoveType.BARRIER, Direction.W, barriers_max=2)  # quota

    def test_thief_cannot_place_barrier(self):
        state = make_state(role=Role.THIEF)
        assert not state.apply_move(MoveType.BARRIER, Direction.N, barriers_max=20)

    def test_move_blocked_by_known_barrier(self):
        state = make_state()
        state.note_barrier((4, 5))  # opponent declared a barrier there
        assert not state.apply_move(MoveType.MOVE, Direction.N)

    def test_step_log_records_moves(self):
        state = make_state()
        state.apply_move(MoveType.MOVE, Direction.SE)
        assert state.step_number == 1
        entry = state.log[-1]
        assert entry["position"] == [6, 6]
        assert entry["move"] == "MOVE:SE"
