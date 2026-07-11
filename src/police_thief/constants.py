# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Immutable project constants: king-move directions, roles, move types.

These define the type system and physics vocabulary of the game; they are not
configuration and never change at runtime.
"""

from enum import StrEnum


class Role(StrEnum):
    """Which side an agent plays."""

    THIEF = "thief"
    POLICE = "police"


class MoveType(StrEnum):
    """The three legal actions an agent may take in a turn."""

    MOVE = "MOVE"       # step one cell in a king direction
    BARRIER = "BARRIER"  # (police only) place a barrier on a neighbour cell
    HOLD = "HOLD"       # stay put (idle; does not count toward thief's unique cells)


class Direction(StrEnum):
    """Eight king-move directions."""

    N = "N"
    NE = "NE"
    E = "E"
    SE = "SE"
    S = "S"
    SW = "SW"
    W = "W"
    NW = "NW"


# (row_delta, col_delta) for each direction. Row grows downward (south).
DELTAS: dict[Direction, tuple[int, int]] = {
    Direction.N: (-1, 0),
    Direction.NE: (-1, 1),
    Direction.E: (0, 1),
    Direction.SE: (1, 1),
    Direction.S: (1, 0),
    Direction.SW: (1, -1),
    Direction.W: (0, -1),
    Direction.NW: (-1, -1),
}

# The four orthogonal (rook) directions — the book's default move set.
ORTHOGONAL: tuple[Direction, ...] = (Direction.N, Direction.S, Direction.E, Direction.W)


def directions_from_move_set(move_set) -> tuple[Direction, ...]:
    """Translate a config `move_set` (e.g. ['N','S','E','W','STAY']) into the allowed
    board Direction members. STAY/HOLD are not board steps and are dropped here.
    A falsy/empty move_set means the legacy 8-direction king movement."""
    if not move_set:
        return tuple(Direction)
    dirs: list[Direction] = []
    for token in move_set:
        name = str(token).strip().upper()
        if name in ("STAY", "HOLD"):
            continue
        try:
            dirs.append(Direction(name))
        except ValueError:
            continue
    return tuple(dirs) or tuple(Direction)


VERDICT_TRUTH = "truth"
VERDICT_LIE = "lie"

# Crypto: nonce length (bytes) for commit-reveal sealing.
NONCE_BYTES = 16

# Fixed game texts (protocol messages, not tunables).
FALLBACK_HINT = "I keep moving through the streets."  # generic but contains a location cue
FINAL_CAUGHT_HINT = "You got me."
NO_HINT_PLACEHOLDER = "(silence)"
