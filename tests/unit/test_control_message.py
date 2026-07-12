"""ControlMessage: the out-of-band bidirectional-control wire format."""

import pytest

from police_thief.domain.protocol import ControlMessage
from police_thief.infra.mcp_server import PeerInboxes


def test_round_trips_through_dict():
    msg = ControlMessage(kind="status", sender="thief", sub_game_number=2,
                         status="THINKING", step_budget=1.5)
    restored = ControlMessage.from_dict(msg.to_dict())
    assert restored == msg
    assert restored.status == "THINKING" and restored.step_budget == 1.5


def test_defaults_for_minimal_message():
    msg = ControlMessage(kind="quit", sender="police")
    assert msg.sub_game_number == 1 and msg.status == "" and msg.payload is None


def test_from_dict_ignores_unknown_keys():
    data = {"kind": "restart", "sender": "thief", "extra": "ignore-me"}
    msg = ControlMessage.from_dict(data)
    assert msg.kind == "restart" and msg.sender == "thief"


def test_from_dict_requires_kind_and_sender():
    with pytest.raises(TypeError):
        ControlMessage.from_dict({"status": "PLAYING"})


def test_inboxes_have_a_controls_queue():
    assert PeerInboxes().controls.empty()
