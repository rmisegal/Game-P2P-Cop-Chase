"""Tests for the smell field: radial trail deposit, global decay, cell-map I/O."""

import pytest

from police_thief.domain.smell import SmellField


class TestSmellField:
    def test_deposit_centers_field(self):
        field = SmellField(board_size=10, grid_size=5, decay=0.1, min_center=0.5)
        field.deposit(center=(5, 5), intensity=0.9)
        assert field.intensity_at((5, 5)) == 0.9   # center cell at full intensity
        assert len(field.snapshot()) == 25          # full 5x5 window, on-board

    def test_deposit_enforces_min_center_intensity(self):
        field = SmellField(board_size=10, grid_size=5, decay=0.1, min_center=0.5)
        with pytest.raises(ValueError):
            field.deposit(center=(5, 5), intensity=0.4)

    def test_deposit_falls_off_from_center(self):
        field = SmellField(board_size=10, grid_size=5, decay=0.1, min_center=0.5)
        field.deposit(center=(5, 5), intensity=1.0)
        assert field.intensity_at((5, 5)) > field.intensity_at((3, 3))

    def test_decay_all_reduces_and_clamps(self):
        field = SmellField(board_size=10, grid_size=5, decay=0.1, min_center=0.5)
        field.deposit(center=(5, 5), intensity=0.6)
        before = field.intensity_at((5, 5))
        field.decay_all()
        assert field.intensity_at((5, 5)) == pytest.approx(before - 0.1)
        for _ in range(20):
            field.decay_all()
        assert field.intensity_at((5, 5)) == 0.0   # clamped at zero

    def test_absorb_maps_cells_and_clips_at_edge(self):
        field = SmellField(board_size=10, grid_size=5, decay=0.1, min_center=0.5)
        field.absorb({"0,0": 0.8, "-1,0": 0.5})     # off-board cell silently dropped
        assert field.intensity_at((0, 0)) == 0.8
        assert field.intensity_at((-1, 0)) == 0.0

    def test_snapshot_is_position_free_cell_map(self):
        field = SmellField(board_size=10, grid_size=3, decay=0.1, min_center=0.5)
        field.deposit(center=(4, 4), intensity=0.7)
        snap = field.snapshot()
        assert "center" not in snap                 # no explicit position, only cells
        assert snap["4,4"] == 0.7
        assert len(snap) == 9                        # 3x3 window
