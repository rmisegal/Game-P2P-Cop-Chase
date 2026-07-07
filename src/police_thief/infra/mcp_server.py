# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Each peer's OWN FastMCP server — there is no central server, ever.

The server is this agent's public mailbox: the opponent (the only other party
on the 'internet') pushes negotiation messages, turn messages and audit
payloads into thread-safe inboxes that the local PeerRuntime consumes.
"""

import queue
import socket
import threading

from fastmcp import FastMCP

from police_thief.exceptions import SimulationError


def _ensure_port_free(host: str, port: int) -> None:
    """Fail fast with a helpful message if my MCP port is already taken."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError as exc:
        raise SimulationError(
            f"Port {port} on {host} is already in use - a previous peer is probably "
            f"still running. Find and stop it (PowerShell):\n"
            f"  Get-NetTCPConnection -LocalPort {port} -State Listen | "
            f"Select-Object OwningProcess\n"
            f"  Stop-Process -Id <PID>\n"
            f"or change network.my_port in this peer's config/<role>/game.toml."
        ) from exc
    finally:
        probe.close()


class PeerInboxes:
    """Thread-safe mailboxes filled by MCP tools, drained by the runtime."""

    def __init__(self):
        self.agreements: queue.Queue = queue.Queue()
        self.turns: queue.Queue = queue.Queue()
        self.audits: queue.Queue = queue.Queue()


def build_peer_server(role: str, inboxes: PeerInboxes) -> FastMCP:
    """A FastMCP app exposing this peer's three receive tools."""
    mcp = FastMCP(name=f"police-thief-{role}")

    @mcp.tool
    def negotiate(message: dict) -> dict:
        """Receive the opponent's signed game agreement."""
        inboxes.agreements.put(message)
        return {"ok": True}

    @mcp.tool
    def receive_turn(message: dict) -> dict:
        """Receive the opponent's turn message (passes the turn token to me)."""
        inboxes.turns.put(message)
        return {"ok": True}

    @mcp.tool
    def submit_audit(payload: dict) -> dict:
        """Receive the opponent's end-of-game audit reveal (records + nonces)."""
        inboxes.audits.put(payload)
        return {"ok": True}

    return mcp


def start_peer_server(role: str, host: str, port: int) -> PeerInboxes:
    """Start this peer's MCP server on its own port in a background thread."""
    _ensure_port_free(host, port)
    inboxes = PeerInboxes()
    server = build_peer_server(role, inboxes)
    thread = threading.Thread(
        target=lambda: server.run(
            transport="http", host=host, port=port, show_banner=False,
            log_level="warning",  # keep peers' consoles readable
        ),
        daemon=True,
        name=f"mcp-{role}",
    )
    thread.start()
    return inboxes
