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

    def test_identity_exchanged_and_captured(self, terms):
        thief_id = {"group_id": "team-thief", "group_name": "T"}
        police_id = {"group_id": "team-police", "group_name": "P"}
        thief = Negotiation(terms, identity=thief_id)
        police = Negotiation(terms, identity=police_id)
        police.verify_peer(thief.signed())
        thief.verify_peer(police.signed())
        assert police.peer_identity == thief_id  # each captured the other's identity
        assert thief.peer_identity == police_id

    def test_identity_is_not_a_signed_term(self, terms):
        # Different identities but identical terms still verify (identity != term).
        thief = Negotiation(terms, identity={"group_id": "a"})
        police = Negotiation(terms, identity={"group_id": "b"})
        police.verify_peer(thief.signed())  # no CryptoError


class TestTermsAndIds:
    def test_terms_from_config_includes_num_games(self, config):
        from police_thief.peer.sealing import terms_from_config

        assert terms_from_config(config)["num_games"] == 1

    def test_game_ids_deterministic_and_order_independent(self, terms):
        from police_thief.domain.game_ids import derive_game_ids

        a = derive_game_ids(terms, "team-07", "team-13")
        b = derive_game_ids(terms, "team-13", "team-07")  # swapped order
        assert a == b  # sorted pair -> identical id/uid for both peers
        assert a[0] == "team-07-vs-team-13"
        assert len(a[1]) == 36  # canonical UUID string

    def test_game_uid_changes_with_terms(self, terms):
        from police_thief.domain.game_ids import derive_game_ids

        base = derive_game_ids(terms, "team-07", "team-13")[1]
        other = derive_game_ids({**terms, "num_games": 6}, "team-07", "team-13")[1]
        assert base != other
