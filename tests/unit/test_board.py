"""Tests for pure board geometry: king moves, bounds, barriers."""

from police_thief.constants import ORTHOGONAL, Direction, directions_from_move_set
from police_thief.domain.board import Board


class TestOrthogonalBoard:
    """Book default: 4 orthogonal moves (+ STAY handled by caller), Manhattan distance."""

    def test_move_set_translation(self):
        assert directions_from_move_set(["N", "S", "E", "W", "STAY"]) == ORTHOGONAL
        assert len(directions_from_move_set(None)) == 8  # king default

    def test_orthogonal_center_has_four_neighbours(self):
        board = Board(size=10, moves=ORTHOGONAL)
        assert len(board.neighbors((5, 5))) == 4
        assert (4, 4) not in board.neighbors((5, 5))  # no diagonal

    def test_orthogonal_step_rejects_diagonal(self):
        board = Board(size=10, moves=ORTHOGONAL)
        assert board.step((5, 5), Direction.NE) is None
        assert board.step((5, 5), Direction.N) == (4, 5)

    def test_distance_manhattan_when_orthogonal(self):
        board = Board(size=10, moves=ORTHOGONAL)
        assert not board.diagonal
        assert board.distance((0, 0), (2, 3)) == 5

    def test_distance_chebyshev_when_king(self):
        board = Board(size=10)  # default king
        assert board.diagonal
        assert board.distance((0, 0), (2, 3)) == 3


class TestBoard:
    def test_apply_direction(self):
        board = Board(size=10)
        assert board.step((5, 5), Direction.N) == (4, 5)
        assert board.step((5, 5), Direction.SE) == (6, 6)

    def test_step_off_board_returns_none(self):
        board = Board(size=10)
        assert board.step((0, 0), Direction.N) is None
        assert board.step((9, 9), Direction.SE) is None

    def test_neighbors_center_has_eight(self):
        board = Board(size=10)
        assert len(board.neighbors((5, 5))) == 8

    def test_neighbors_corner_has_three(self):
        board = Board(size=10)
        assert sorted(board.neighbors((0, 0))) == [(0, 1), (1, 0), (1, 1)]

    def test_barrier_blocks_step(self):
        board = Board(size=10)
        assert board.step((5, 5), Direction.N, barriers={(4, 5)}) is None

    def test_legal_moves_exclude_barriers(self):
        board = Board(size=10)
        moves = board.legal_moves((0, 0), barriers={(0, 1)})
        assert (0, 1) not in [cell for _, cell in moves]
        assert len(moves) == 2

    def test_in_bounds(self):
        board = Board(size=8)
        assert board.in_bounds((7, 7))
        assert not board.in_bounds((8, 0))
        assert not board.in_bounds((-1, 3))

    def test_configurable_size(self):
        assert Board(size=5).in_bounds((4, 4))
        assert not Board(size=5).in_bounds((5, 5))
