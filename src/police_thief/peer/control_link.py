# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""ControlLink: one peer's side of the opt-in bidirectional control channel.

Pure coordination logic over an injected transport (`send_control`/`poll_control`)
and a GameControls. The channel is ACTIVE only when BOTH peers enabled it. While
active it shares live status, and honors a whole-series restart (auto-approved)
and a clean quit. No Tk and no threads here, so it is fully unit-testable."""

from police_thief.domain.protocol import ControlMessage

# Statuses a peer broadcasts (book §8.3 turn phases + control overlay).
WAITING, THINKING, PLAYING = "WAITING", "THINKING", "PLAYING"
PAUSED, STOPPED, GAME_OVER, QUIT = "PAUSED", "STOPPED", "GAME_OVER", "QUIT"


class ControlLink:
    """Enable-handshake + status/restart/quit signalling for one peer."""

    def __init__(self, role: str, transport, controls, listener=None):
        self._role = role
        self._transport = transport
        self._controls = controls
        self._listen = listener or (lambda event: None)
        self._i_enabled = False
        self._peer_enabled = False
        self._opponent = {"status": "-", "sub_game_number": None, "step_budget": None}
        self._last_status_key = None

    @property
    def active(self) -> bool:
        """True only once BOTH sides have enabled the channel."""
        return self._i_enabled and self._peer_enabled

    @property
    def i_enabled(self) -> bool:
        return self._i_enabled

    @property
    def opponent(self) -> dict:
        return dict(self._opponent)

    def enable(self) -> None:
        """Local user opted in; announce it so the peer can match (then active)."""
        self._i_enabled = True
        self._send("enable")

    def broadcast_status(self, status: str, sub_game_number: int,
                         step_budget: float) -> None:
        """Record + send my status, but only on change (never spam the wire)."""
        self._controls.set_status(status)
        key = (status, round(step_budget or 0.0, 2))
        if not self._i_enabled or key == self._last_status_key:
            return
        self._last_status_key = key
        self._send("status", status=status, sub_game_number=sub_game_number,
                   step_budget=step_budget)

    def send_restart(self) -> None:
        self._send("restart")

    def send_quit(self) -> None:
        self._send("quit", status=QUIT)

    def drain(self) -> list:
        """Process every pending inbound control message; return handler events."""
        poll = getattr(self._transport, "poll_control", None)
        if poll is None:
            return []
        events = []
        while (raw := poll()) is not None:
            events.append(self._handle(ControlMessage.from_dict(raw)))
        return events

    def _handle(self, msg: ControlMessage) -> dict:
        if msg.kind == "enable":
            self._peer_enabled = True
            event = {"type": "control_enable", "sender": msg.sender}
        elif msg.kind == "status":
            self._opponent = {"status": msg.status,
                              "sub_game_number": msg.sub_game_number,
                              "step_budget": msg.step_budget}
            event = {"type": "control_status", **self._opponent}
        elif msg.kind == "restart":
            if self.active:  # auto-approve when both enabled
                self._controls.request_restart()
            event = {"type": "control_restart", "granted": self.active}
        elif msg.kind == "quit":
            self._opponent["status"] = QUIT
            event = {"type": "control_quit", "sender": msg.sender}
        else:
            event = {"type": "control_unknown", "kind": msg.kind}
        self._listen(event)
        return event

    def _send(self, kind: str, **fields) -> None:
        send = getattr(self._transport, "send_control", None)
        if send is not None:
            send(ControlMessage(kind=kind, sender=self._role, **fields).to_dict())
