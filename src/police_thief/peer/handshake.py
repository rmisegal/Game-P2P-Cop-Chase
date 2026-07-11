# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""The pre-game handshake step of a PeerRuntime, split out to keep runtime.py
small: exchange signed terms + identity, verify, and derive the shared ids."""

import time

from police_thief.domain.game_ids import derive_game_ids
from police_thief.domain.negotiation import Negotiation
from police_thief.peer.sealing import terms_from_config


def negotiate(rt) -> None:
    """Run the mutual agreement + identity exchange for one sub-game.

    Sets rt.peer_identity, rt.game_id, rt.game_uid and (re)starts the game clock.
    """
    terms = terms_from_config(rt._config)
    negotiation = Negotiation(terms, identity=rt._own_identity)
    peer_message = rt._transport.exchange_agreement(negotiation.signed())
    negotiation.verify_peer(peer_message)
    rt.peer_identity = negotiation.peer_identity
    rt.game_id, rt.game_uid = derive_game_ids(
        terms,
        rt._own_identity.get("group_id", "unknown-group"),
        rt.peer_identity.get("group_id", "unknown-group"),
    )
    rt._started_monotonic = time.monotonic()  # game clock starts at agreement
