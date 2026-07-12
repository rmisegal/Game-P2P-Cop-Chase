"""McpTransport.drain_inboxes clears stale turns/controls/audits (but not agreements)."""

from police_thief.infra.mcp_client import McpTransport
from police_thief.infra.mcp_server import PeerInboxes


def test_drain_clears_turns_controls_audits_keeps_agreements():
    inboxes = PeerInboxes()
    inboxes.turns.put({"stale": "turn"})
    inboxes.controls.put({"stale": "control"})
    inboxes.audits.put({"stale": "audit"})
    inboxes.agreements.put({"fresh": "agreement"})
    transport = McpTransport("http://opponent/mcp", inboxes)

    transport.drain_inboxes()

    assert inboxes.turns.empty()
    assert inboxes.controls.empty()
    assert inboxes.audits.empty()
    assert not inboxes.agreements.empty()  # left for the fresh handshake


def test_drain_is_safe_on_empty_inboxes():
    transport = McpTransport("http://opponent/mcp", PeerInboxes())
    transport.drain_inboxes()  # no raise
