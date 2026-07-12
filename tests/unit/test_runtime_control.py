"""runtime_control pump/check: status broadcast, quit, and whole-series restart."""

from types import SimpleNamespace

import pytest

from police_thief.constants import Role
from police_thief.exceptions import RestartSeries
from police_thief.peer import runtime_control
from police_thief.peer.control_link import ControlLink
from police_thief.peer.controls import GameControls


class FakeControlTransport:
    def __init__(self, inbound=None):
        self.sent = []
        self._inbound = list(inbound or [])

    def send_control(self, message):
        self.sent.append(message)

    def poll_control(self):
        return self._inbound.pop(0) if self._inbound else None


class Cfg:
    def get(self, key, default=None):
        return {"llm.step_deadline_seconds": 30}.get(key, default)


def _rt(inbound=None):
    controls = GameControls()
    transport = FakeControlTransport(inbound)
    link = ControlLink("police", transport, controls)
    rt = SimpleNamespace(controls=controls, link=link, _config=Cfg(),
                         _sub_game_number=1, _result=None, role=Role.POLICE)
    return rt, transport


def test_pump_enables_and_broadcasts_status():
    rt, transport = _rt()
    rt.controls.request_enable()
    runtime_control.pump(rt, runtime_control.WAITING)
    assert rt.link.i_enabled
    kinds = {m["kind"] for m in transport.sent}
    assert "enable" in kinds
    assert any(m["kind"] == "status" and m["status"] == "WAITING" for m in transport.sent)


def test_pump_broadcasts_paused_when_paused():
    rt, transport = _rt()
    rt.controls.request_enable()
    rt.controls.pause()
    runtime_control.pump(rt, runtime_control.WAITING)
    assert any(m["status"] == "PAUSED" for m in transport.sent)


def test_check_local_restart_raises_and_sends():
    rt, transport = _rt()
    rt.controls.request_restart()
    with pytest.raises(RestartSeries):
        runtime_control.check(rt)
    assert any(m["kind"] == "restart" for m in transport.sent)
    assert not rt.controls.restart_requested  # cleared so it fires once


def test_check_peer_restart_raises_without_resending():
    rt, transport = _rt(inbound=[{"kind": "enable", "sender": "thief"},
                                 {"kind": "restart", "sender": "thief"}])
    rt.controls.request_enable()
    runtime_control.pump(rt, runtime_control.WAITING)  # enable + drain -> active + pending
    with pytest.raises(RestartSeries):
        runtime_control.check(rt)
    assert not any(m["kind"] == "restart" for m in transport.sent)  # no echo


def test_check_quit_ends_game_and_notifies():
    rt, transport = _rt()
    rt.controls.request_quit()
    runtime_control.check(rt)
    assert rt._result == ("quit", "-")
    assert any(m["kind"] == "quit" for m in transport.sent)


def test_check_opponent_quit_ends_game():
    rt, _ = _rt(inbound=[{"kind": "quit", "sender": "thief", "status": "QUIT"}])
    runtime_control.pump(rt, runtime_control.WAITING)  # drains the quit
    runtime_control.check(rt)
    assert rt._result == ("opponent_quit", "police")
