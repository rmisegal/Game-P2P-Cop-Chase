"""Tests for the opponent-location belief heatmap."""

import pytest

from police_thief.domain.belief import BeliefGrid


@pytest.fixture
def belief():
    return BeliefGrid(board_size=10)


class TestBeliefGrid:
    def test_starts_uniform(self, belief):
        probs = belief.as_matrix()
        assert probs[0][0] == pytest.approx(1 / 100)
        assert sum(sum(row) for row in probs) == pytest.approx(1.0)

    def test_smell_observation_concentrates_probability(self, belief):
        belief.observe_smell({"3,3": 0.7})
        probs = belief.as_matrix()
        assert probs[3][3] > probs[9][9]
        assert sum(sum(row) for row in probs) == pytest.approx(1.0)

    def test_diffuse_spreads_after_move(self, belief):
        belief.observe_smell({"3,3": 0.9})
        peak_before = belief.as_matrix()[3][3]
        belief.diffuse()
        after = belief.as_matrix()
        assert after[3][3] < peak_before  # opponent moved: certainty leaks to neighbors
        assert after[2][2] > 0
        assert sum(sum(row) for row in after) == pytest.approx(1.0)

    def test_orthogonal_diffuse_favours_von_neumann(self):
        b = BeliefGrid(board_size=10, orthogonal=True)
        b.observe_smell({"5,5": 1000.0})
        b.diffuse()
        m = b.as_matrix()
        # 4-neighbours get direct mass; the diagonal only tiny indirect leakage.
        assert m[4][5] > m[4][4] * 5
        assert m[5][4] > m[4][4] * 5

    def test_king_diffuse_reaches_diagonal(self):
        b = BeliefGrid(board_size=10, orthogonal=False)
        b.observe_smell({"5,5": 1000.0})
        b.diffuse()
        m = b.as_matrix()
        assert m[4][4] > 0  # king diffusion spreads to the diagonal too

    def test_exclude_cell_zeroes_and_renormalizes(self, belief):
        belief.exclude((0, 0))  # e.g. I stand here and opponent is not caught
        probs = belief.as_matrix()
        assert probs[0][0] == 0.0
        assert sum(sum(row) for row in probs) == pytest.approx(1.0)

    def test_most_likely_cell(self, belief):
        belief.observe_smell({"7,2": 0.8})
        assert belief.most_likely() == (7, 2)
