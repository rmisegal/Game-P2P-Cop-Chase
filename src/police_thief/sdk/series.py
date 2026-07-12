# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Run a SERIES of N sub-games between two peers with role alternation.

The transport (and thus each peer's MCP server) is built ONCE by the caller and
reused across sub-games — it is never torn down between them. Each sub-game gets
a fresh PeerRuntime (fresh state/belief/smell/commit-chain). Roles alternate: a
peer plays its config-natural role on odd sub-games and the opposite on even ones,
so the two peers always stay consistent (when A is cop, B is thief).
"""

from dataclasses import dataclass

from police_thief.constants import Role
from police_thief.exceptions import RestartSeries
from police_thief.peer.control_link import ControlLink
from police_thief.peer.controls import GameControls
from police_thief.peer.runtime import PeerRuntime
from police_thief.peer.sealing import identity_from_config

MAX_RESTARTS = 10  # backstop so a restart storm can never loop forever


@dataclass
class SeriesResult:
    """Everything the emitters need after a whole series has been played."""

    summaries: list[dict]
    own_identity: dict
    peer_identity: dict
    game_id: str | None
    game_uid: str | None


def role_for(natural: Role, sub_game_number: int) -> Role:
    """Natural role on odd sub-games, the opposite on even ones (alternation)."""
    if sub_game_number % 2 == 1:
        return natural
    return Role.THIEF if natural is Role.POLICE else Role.POLICE


def _play_all(config, natural_role, llm, transport, own_identity, listener, controls,
              link) -> SeriesResult:
    """One full pass over the sub-games (the whole series) with a shared ControlLink."""
    num_games = config.get("game.num_games", 1)
    summaries: list[dict] = []
    peer_identity: dict = {}
    game_id = game_uid = None
    for sub_game_number in range(1, num_games + 1):
        runtime = PeerRuntime(
            role=role_for(natural_role, sub_game_number), config=config, llm=llm,
            transport=transport, listener=listener, controls=controls,
            own_identity=own_identity, sub_game_number=sub_game_number, link=link,
        )
        summaries.append(runtime.run())
        peer_identity = runtime.peer_identity or peer_identity
        game_id, game_uid = runtime.game_id, runtime.game_uid
    return SeriesResult(summaries, own_identity, peer_identity, game_id, game_uid)


def run_series(config, natural_role: Role, llm, transport,
               listener=None, controls=None) -> SeriesResult:
    """Play the whole series; a control-channel RestartSeries restarts it from
    sub-game 1 (the ControlLink is shared so the enable state survives a restart)."""
    own_identity = identity_from_config(config)
    controls = controls or GameControls()
    link = ControlLink(natural_role.value, transport, controls, listener)
    attempt = 0
    while True:
        try:
            return _play_all(config, natural_role, llm, transport, own_identity,
                             listener, controls, link)
        except RestartSeries:
            attempt += 1
            # Clear any stale turn/control messages from the aborted sub-game so the
            # restarted series never consumes them (both peers drain before the fresh
            # handshake, and no new turn arrives until after it).
            drain = getattr(transport, "drain_inboxes", None)
            if drain is not None:
                drain()
            if listener is not None:
                listener({"type": "series_restart", "attempt": attempt})
            if attempt > MAX_RESTARTS:
                raise
