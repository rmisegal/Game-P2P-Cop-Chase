"""ControlLink: enable-handshake, status sharing, auto-approved restart, quit."""

from police_thief.peer.control_link import ControlLink
from police_thief.peer.controls import GameControls


class FakeControlTransport:
    """Loopback-ish double: records sent control messages, replays queued inbound."""

    def __init__(self, inbound=None):
        self.sent = []
        self._inbound = list(inbound or [])

    def send_control(self, message):
        self.sent.append(message)

    def poll_control(self):
        return self._inbound.pop(0) if self._inbound else None


def _link(inbound=None, controls=None):
    return ControlLink("police", FakeControlTransport(inbound), controls or GameControls())


def test_channel_active_only_when_both_enabled():
    link = _link()
    assert not link.active
    link.enable()
    assert link.i_enabled and not link.active          # peer not enabled yet
    link.drain()  # nothing inbound
    assert not link.active


def test_peer_enable_makes_it_active():
    link = _link(inbound=[{"kind": "enable", "sender": "thief"}])
    link.enable()
    link.drain()
    assert link.active


def test_enable_sends_an_enable_message():
    link = _link()
    link.enable()
    assert link._transport.sent == [
        {"kind": "enable", "sender": "police", "sub_game_number": 1,
         "status": "", "step_budget": 0.0, "payload": None}]


def test_status_broadcast_is_deduped():
    link = _link()
    link.enable()
    link._transport.sent.clear()
    link.broadcast_status("THINKING", 1, 1.0)
    link.broadcast_status("THINKING", 1, 1.0)   # unchanged -> not resent
    link.broadcast_status("WAITING", 1, 1.0)
    kinds = [m["status"] for m in link._transport.sent]
    assert kinds == ["THINKING", "WAITING"]


def test_status_not_sent_when_not_enabled():
    link = _link()
    link.broadcast_status("PLAYING", 1, 0.0)     # never enabled
    assert link._transport.sent == []
    assert link._controls.status == "PLAYING"    # local status still tracked


def test_inbound_status_updates_opponent_view():
    link = _link(inbound=[{"kind": "status", "sender": "thief",
                           "status": "PAUSED", "sub_game_number": 2, "step_budget": 3.0}])
    link.drain()
    assert link.opponent["status"] == "PAUSED"
    assert link.opponent["sub_game_number"] == 2


def test_inbound_restart_auto_approves_only_when_active():
    link = _link(inbound=[{"kind": "restart", "sender": "thief"}])
    link.enable()
    link._peer_enabled = True  # both enabled -> active
    link.drain()
    assert link.take_pending_restart()          # approved, consumed once
    assert not link.take_pending_restart()


def test_inbound_restart_ignored_when_inactive():
    link = _link(inbound=[{"kind": "restart", "sender": "thief"}])
    link.drain()  # channel not active
    assert not link.take_pending_restart()


def test_inbound_quit_marks_opponent_quit():
    link = _link(inbound=[{"kind": "quit", "sender": "thief", "status": "QUIT"}])
    events = link.drain()
    assert link.opponent["status"] == "QUIT"
    assert events[0]["type"] == "control_quit"


def test_send_restart_and_quit_put_messages_on_the_wire():
    link = _link()
    link.send_restart()
    link.send_quit()
    kinds = [m["kind"] for m in link._transport.sent]
    assert kinds == ["restart", "quit"]
    assert link._transport.sent[1]["status"] == "QUIT"


def test_drain_without_control_transport_is_safe():
    class NoControl:
        pass
    link = ControlLink("thief", NoControl(), GameControls())
    assert link.drain() == []          # transport lacks poll_control -> no crash
    link.enable()                       # send_control missing -> no crash


def test_controls_restart_and_quit_flags():
    controls = GameControls()
    assert not controls.restart_requested and not controls.quit_requested
    controls.request_restart()
    controls.request_quit()
    assert controls.restart_requested and controls.quit_requested
    controls.clear_restart()
    assert not controls.restart_requested
    controls.set_status("PLAYING")
    assert controls.status == "PLAYING"
