# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Commit-reveal sealing — the cryptographic backbone of the distributed game.

Every step a peer seals its true (state, move, verdict) under
commit = SHA256(canonical_json(payload) | nonce) and sends ONLY the commit.
Nonces are revealed at end-of-game audit; both sides then re-verify every step,
so no location or action can be rewritten after the fact.
"""

import hashlib
import json
import secrets
from typing import Any

from police_thief.constants import NONCE_BYTES
from police_thief.exceptions import CryptoError


def _canonical(payload: dict[str, Any]) -> str:
    """Stable JSON so hashing is key-order independent."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class CommitReveal:
    """Seal, recompute and verify per-step commitments."""

    @staticmethod
    def commit_of(payload: dict[str, Any], nonce: str) -> str:
        digest = hashlib.sha256(f"{_canonical(payload)}|{nonce}".encode())
        return digest.hexdigest()

    @classmethod
    def seal(cls, payload: dict[str, Any]) -> dict[str, str]:
        """Generate a fresh nonce and the commit hash for a payload."""
        nonce = secrets.token_hex(NONCE_BYTES)
        return {"nonce": nonce, "commit": cls.commit_of(payload, nonce)}

    @classmethod
    def verify(cls, payload: dict[str, Any], nonce: str, commit: str) -> None:
        """Raise CryptoError unless (payload, nonce) hashes to commit."""
        actual = cls.commit_of(payload, nonce)
        if actual != commit:
            raise CryptoError(
                f"Commit mismatch: expected {commit[:16]}..., recomputed {actual[:16]}..."
            )


def audit_records(records: list[dict]) -> dict:
    """Post-game audit: re-verify every {payload, nonce, commit} record.

    Returns {'passed', 'verified_steps', 'failed_steps'} — both peers run this
    on the opponent's revealed log and must agree for mutual consensus.
    """
    failed: list[int] = []
    for record in records:
        try:
            CommitReveal.verify(record["payload"], record["nonce"], record["commit"])
        except CryptoError:
            failed.append(record["payload"].get("step", -1))
    return {
        "passed": not failed,
        "verified_steps": len(records) - len(failed),
        "failed_steps": failed,
    }
