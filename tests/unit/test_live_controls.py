"""Pure helper behind the live control bar: the 1..6 sub-games clamp."""

from police_thief.gui.live_controls import clamp_subgames


def test_clamp_keeps_in_range():
    assert clamp_subgames(3) == 3
    assert clamp_subgames(1) == 1
    assert clamp_subgames(6) == 6


def test_clamp_bounds_and_bad_input():
    assert clamp_subgames(0) == 1
    assert clamp_subgames(99) == 6
    assert clamp_subgames("nope") == 1
    assert clamp_subgames(None) == 1
