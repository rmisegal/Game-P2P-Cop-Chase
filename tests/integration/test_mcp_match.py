"""End-to-end distributed match over REAL MCP HTTP servers on two ports.

Mimics two students on the internet: each peer has only its own server and
the other's URL. No central server exists.
"""

import threading

import pytest

from police_thief.constants import Role
from police_thief.infra.mcp_client import McpTransport
from police_thief.infra.mcp_server import start_peer_server

THIEF_PORT = 18801
POLICE_PORT = 18802
HOST = "127.0.0.1"


class GarbageLlm:
    def send(self, prompt: str) -> str:
        return "not json -> deterministic fallback policy"


@pytest.fixture(scope="module")
def peer_pair():
    thief_in = start_peer_server("thief", HOST, THIEF_PORT)
    police_in = start_peer_server("police", HOST, POLICE_PORT)
    thief_transport = McpTransport(
        f"http://{HOST}:{POLICE_PORT}/mcp", thief_in, connect_timeout=30)
    police_transport = McpTransport(
        f"http://{HOST}:{THIEF_PORT}/mcp", police_in, connect_timeout=30)
    return thief_transport, police_transport


@pytest.mark.slow
def test_full_match_over_real_mcp(config, peer_pair):
    from police_thief.peer.runtime import PeerRuntime

    thief_transport, police_transport = peer_pair
    thief = PeerRuntime(Role.THIEF, config, GarbageLlm(), thief_transport)
    police = PeerRuntime(Role.POLICE, config, GarbageLlm(), police_transport)

    results: dict = {}
    threads = [
        threading.Thread(target=lambda: results.update(police=police.run()), daemon=True),
        threading.Thread(target=lambda: results.update(thief=thief.run()), daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
        assert not t.is_alive(), "distributed match did not finish"

    assert results["thief"]["result"] == results["police"]["result"]
    assert results["thief"]["winner"] == results["police"]["winner"]
    assert results["thief"]["audit"]["passed"] is True
    assert results["police"]["audit"]["passed"] is True
