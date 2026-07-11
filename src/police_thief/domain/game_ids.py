# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Deterministic shared game identifiers.

Both peers derive the SAME game_id (human) and game_uid (stable UUID) from data
they BOTH hold after the handshake — the agreed terms plus the two group ids —
so no extra round-trip is needed to agree on them. Because the derivation is a
pure function of shared inputs, the two peers always compute identical values.
"""

import hashlib
import json
import uuid


def _canonical(data) -> str:
    """The same canonical JSON used by the crypto layer (key-order independent)."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def derive_game_ids(terms: dict, group_a: str, group_b: str) -> tuple[str, str]:
    """Return (game_id, game_uid), identical for both peers.

    game_id  = "<sorted_gid_a>-vs-<sorted_gid_b>" (human-readable, order-stable).
    game_uid = UUID over sha256(canonical(terms) | sorted group ids) — a stable
    128-bit id both peers reproduce without exchanging it.
    """
    pair = sorted([group_a, group_b])
    game_id = f"{pair[0]}-vs-{pair[1]}"
    seed = f"{_canonical(terms)}|{'|'.join(pair)}"
    game_uid = str(uuid.UUID(bytes=hashlib.sha256(seed.encode()).digest()[:16]))
    return game_id, game_uid
