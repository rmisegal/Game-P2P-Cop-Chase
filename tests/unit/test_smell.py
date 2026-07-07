"""Tests for the smell field: local MxM emission, global decay, clamping."""

import pytest

from police_thief.domain.smell import SmellField


class TestSmellField:
    def test_emit_centers_grid(self):
        field = SmellField(board_size=10, grid_size=5, decay=0.1, min_center=0.5)
        grid = field.emit(center=(5, 5), intensity=0.9)
        assert grid["center"] == [5, 5]
        assert len(grid["values"]) == 5
        assert grid["values"][2][2] == 0.9  # middle cell of 5x5

    def test_emit_enforces_min_center_intensity(self):
        field = SmellField(board_size=10, grid_size=5, decay=0.1, min_center=0.5)
        with pytest.raises(ValueError):
            field.emit(center=(5, 5), intensity=0.4)

    def test_emit_falls_off_from_center(self):
        field = SmellField(board_size=10, grid_size=5, decay=0.1, min_center=0.5)
        vals = field.emit(center=(5, 5), intensity=1.0)["values"]
        assert vals[2][2] > vals[0][0]

    def test_decay_all_reduces_and_clamps(self):
        field = SmellField(board_size=10, grid_size=5, decay=0.1, min_center=0.5)
        field.absorb(field.emit(center=(5, 5), intensity=0.6))
        before = field.intensity_at((5, 5))
        field.decay_all()
        assert field.intensity_at((5, 5)) == pytest.approx(before - 0.1)
        for _ in range(20):
            field.decay_all()
        assert field.intensity_at((5, 5)) == 0.0  # clamped at zero

    def test_absorb_clips_grid_at_board_edge(self):
        field = SmellField(board_size=10, grid_size=5, decay=0.1, min_center=0.5)
        field.absorb(field.emit(center=(0, 0), intensity=0.8))
        assert field.intensity_at((0, 0)) == 0.8  # off-board cells silently dropped

    def test_configurable_grid_size(self):
        field = SmellField(board_size=10, grid_size=3, decay=0.1, min_center=0.5)
        assert len(field.emit(center=(4, 4), intensity=0.7)["values"]) == 3
