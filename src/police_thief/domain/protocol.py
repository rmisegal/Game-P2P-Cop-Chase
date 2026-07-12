# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Peer-to-peer wire format: the TurnMessage each mover sends its opponent,
and the AuditPayload exchanged after the game.

The turn token travels WITH the TurnMessage: receiving one makes it your turn.
"""

from dataclasses import MISSING, asdict, dataclass, fields


@dataclass
class TurnMessage:
    """Everything one peer tells the other about its turn — and nothing more.

    True position/move/verdict are NOT here in the clear; they are sealed
    inside `commit` and only proven at the end-of-game audit.
    """

    step: int
    sender: str                        # "thief" | "police"
    hint: str                          # free NL message with a location cue (may lie)
    smell_grid: dict                   # {"r,c": intensity} decaying scent trail (no position)
    commit: str                        # SHA256(state|move|verdict|nonce), nonce withheld
    timestamp: str                     # real-time ISO-8601 (book: mandatory per move)
    barrier_placed: list | None = None    # public declaration: impassable for both
    capture_claim: list | None = None     # police only: "I claim you are at [r,c]"
    claim_response: dict | None = None    # thief's honest {"claim": [r,c], "caught": bool}
    win_claim: dict | None = None         # thief's {"type": "survival"}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TurnMessage":
        required = {f.name for f in fields(cls) if f.default is MISSING}
        missing = required - data.keys()
        if missing:
            raise TypeError(f"TurnMessage missing fields: {sorted(missing)}")
        return cls(**data)


@dataclass
class ControlMessage:
    """Out-of-band control signal on the opt-in bidirectional control channel.

    NOT part of the sealed game record. Carries a peer's live status and its
    enable/restart/quit intents so each side can see the other's state and
    coordinate a whole-series restart or a clean quit.
    """

    kind: str                          # "enable" | "status" | "restart" | "quit"
    sender: str                        # "thief" | "police"
    sub_game_number: int = 1
    status: str = ""                   # WAITING/THINKING/PLAYING/PAUSED/STOPPED/...
    step_budget: float = 0.0           # live per-step time budget (seconds)
    payload: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ControlMessage":
        allowed = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})


@dataclass
class AuditPayload:
    """End-of-game reveal: full sealed records so the opponent can re-verify."""

    sender: str
    records: list                      # [{"payload": {...}, "nonce": str, "commit": str}]
    result_claim: str                  # "capture" | "survival" | "timeout"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AuditPayload":
        return cls(**data)
