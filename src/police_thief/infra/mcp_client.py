# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""McpTransport: the peer-to-peer 'network' — my inboxes + the opponent's URL.

Implements the same transport protocol as the test FakeTransport:
exchange_agreement / send_turn / poll_turn / exchange_audit. Outbound calls go
to the OPPONENT's MCP server; inbound arrives in MY server's inboxes.
"""

import asyncio
import contextlib
import queue
import time

from fastmcp import Client

from police_thief.exceptions import SimulationError
from police_thief.infra.mcp_server import PeerInboxes


class McpTransport:
    """One peer's view of the wire: push to opponent, pull from own inboxes."""

    def __init__(self, opponent_url: str, inboxes: PeerInboxes,
                 connect_timeout: float = 60.0, retry_interval: float = 1.0,
                 audit_send_timeout: float = 10.0, control_send_timeout: float = 2.0):
        self._url = opponent_url
        self._inboxes = inboxes
        self._connect_timeout = connect_timeout
        self._retry = retry_interval
        self._audit_timeout = audit_send_timeout
        self._control_timeout = control_send_timeout

    def _call(self, tool: str, argument: dict) -> None:
        async def invoke():
            async with Client(self._url) as client:
                await client.call_tool(tool, {"message": argument}
                                       if tool != "submit_audit" else {"payload": argument})

        asyncio.run(invoke())

    def _call_with_retry(self, tool: str, argument: dict,
                         timeout: float | None = None) -> None:
        """Retry until the opponent's server is up (peers may start seconds apart)."""
        deadline = time.time() + (timeout if timeout is not None else self._connect_timeout)
        while True:
            try:
                self._call(tool, argument)
                return
            except Exception as exc:
                if time.time() >= deadline:
                    raise SimulationError(
                        f"Opponent MCP server unreachable at {self._url}: {exc}"
                    ) from exc
                time.sleep(self._retry)

    def exchange_agreement(self, signed: dict) -> dict:
        self._call_with_retry("negotiate", signed)
        try:
            return self._inboxes.agreements.get(timeout=self._connect_timeout)
        except queue.Empty as exc:
            raise SimulationError("Opponent never sent its agreement") from exc

    def send_turn(self, message: dict) -> None:
        self._call_with_retry("receive_turn", message)

    def poll_turn(self, timeout: float) -> dict | None:
        try:
            return self._inboxes.turns.get(timeout=timeout)
        except queue.Empty:
            return None

    def send_control(self, message: dict) -> None:
        """Best-effort control send: a short timeout + suppressed error so a slow or
        departed opponent never stalls the game loop (control msgs are advisory)."""
        with contextlib.suppress(SimulationError):
            self._call_with_retry("receive_control", message,
                                  timeout=self._control_timeout)

    def poll_control(self) -> dict | None:
        """Non-blocking drain of one pending control message (None if the inbox is empty)."""
        try:
            return self._inboxes.controls.get_nowait()
        except queue.Empty:
            return None

    def drain_inboxes(self) -> None:
        """Discard stale turn/control/audit messages so a restarted series starts from
        a clean slate. Safe because both peers drain BEFORE re-negotiating and no new
        turn is sent until after the fresh handshake completes (agreements are already
        empty post-handshake, so they are left untouched)."""
        for inbox in (self._inboxes.turns, self._inboxes.controls, self._inboxes.audits):
            try:
                while True:
                    inbox.get_nowait()
            except queue.Empty:
                pass

    def exchange_audit(self, payload: dict) -> dict | None:
        # Best-effort send: the winner's process may exit right after reading its
        # inbox, killing its server mid-response. Our payload usually landed anyway,
        # and THEIR payload may already sit in OUR inbox — always check it.
        with contextlib.suppress(SimulationError):
            self._call_with_retry("submit_audit", payload, timeout=self._audit_timeout)
        try:
            return self._inboxes.audits.get(timeout=self._connect_timeout)
        except queue.Empty:
            return None
