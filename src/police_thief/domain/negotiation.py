# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Pre-game negotiation: agree on terms, exchange mutual SHA-256 signatures.

Each peer signs SHA256(canonical_terms | nonce) and verifies the opponent's
signature over the SAME terms. Play starts only after both verifications pass.
"""

import secrets

from police_thief.domain.crypto import CommitReveal
from police_thief.exceptions import CryptoError


class Negotiation:
    """One peer's side of the agreement handshake."""

    def __init__(self, terms: dict, identity: dict | None = None):
        self.terms = terms
        self.identity = identity or {}
        self._nonce = secrets.token_hex(16)
        self.peer_identity: dict = {}

    def signed(self) -> dict:
        """My agreement message: terms + nonce + signature over both, plus my own
        group identity. Identity differs per group, so it is NOT a must-match term
        and is NOT covered by the signature — the terms are what both peers verify."""
        return {
            "terms": self.terms,
            "nonce": self._nonce,
            "signature": CommitReveal.commit_of(self.terms, self._nonce),
            "identity": self.identity,
        }

    def verify_peer(self, message: dict) -> None:
        """Verify the opponent signed the SAME terms; raise CryptoError otherwise.
        Also capture the opponent's identity for the declaration (not signed)."""
        if message["terms"] != self.terms:
            raise CryptoError(
                f"Agreement terms mismatch: mine={self.terms} theirs={message['terms']}"
            )
        CommitReveal.verify(message["terms"], message["nonce"], message["signature"])
        self.peer_identity = message.get("identity", {})
