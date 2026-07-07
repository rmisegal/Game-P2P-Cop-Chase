"""Tests for the pre-game agreement + mutual signature exchange."""

import pytest

from police_thief.domain.negotiation import Negotiation
from police_thief.exceptions import CryptoError


@pytest.fixture
def terms():
    return {
        "board_size": 10,
        "smell_grid_size": 5,
        "decay_per_step": 0.1,
        "max_steps": 50,
        "setting": "New York",
    }


class TestNegotiation:
    def test_signature_roundtrip(self, terms):
        thief = Negotiation(terms)
        police = Negotiation(terms)
        police.verify_peer(thief.signed())   # police checks thief's signature
        thief.verify_peer(police.signed())   # thief checks police's signature

    def test_mismatched_terms_rejected(self, terms):
        thief = Negotiation(terms)
        police = Negotiation({**terms, "max_steps": 999})
        with pytest.raises(CryptoError):
            police.verify_peer(thief.signed())

    def test_tampered_signature_rejected(self, terms):
        thief = Negotiation(terms)
        message = thief.signed()
        message["signature"] = "0" * 64
        with pytest.raises(CryptoError):
            Negotiation(terms).verify_peer(message)

    def test_signed_message_contains_terms_and_nonce(self, terms):
        message = Negotiation(terms).signed()
        assert message["terms"] == terms
        assert len(message["nonce"]) == 32
        assert len(message["signature"]) == 64
