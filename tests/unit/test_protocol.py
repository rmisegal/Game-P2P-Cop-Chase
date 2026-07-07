"""Tests for the peer-to-peer TurnMessage / AuditPayload wire format."""

import pytest

from police_thief.domain.protocol import AuditPayload, TurnMessage


@pytest.fixture
def message():
    return TurnMessage(
        step=3,
        sender="thief",
        hint="Grabbing a cab east toward First Avenue.",
        smell_grid={"center": [4, 4], "values": [[0.9]]},
        commit="ab" * 32,
        barrier_placed=None,
        capture_claim=None,
        claim_response=None,
        win_claim=None,
        timestamp="2026-07-06T10:00:00Z",
    )


class TestTurnMessage:
    def test_roundtrip(self, message):
        assert TurnMessage.from_dict(message.to_dict()) == message

    def test_optional_fields_roundtrip(self, message):
        message.capture_claim = [3, 7]
        message.claim_response = {"claim": [3, 7], "caught": False}
        restored = TurnMessage.from_dict(message.to_dict())
        assert restored.capture_claim == [3, 7]
        assert restored.claim_response["caught"] is False

    def test_missing_required_field_raises(self, message):
        data = message.to_dict()
        del data["commit"]
        with pytest.raises(TypeError):
            TurnMessage.from_dict(data)


class TestAuditPayload:
    def test_roundtrip(self):
        payload = AuditPayload(
            sender="police",
            records=[{"payload": {"step": 1}, "nonce": "aa", "commit": "bb"}],
            result_claim="capture",
        )
        assert AuditPayload.from_dict(payload.to_dict()) == payload
