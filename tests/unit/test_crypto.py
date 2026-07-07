"""Tests for commit-reveal sealing: the cryptographic core of the game."""

import pytest

from police_thief.domain.crypto import CommitReveal, audit_records
from police_thief.exceptions import CryptoError


def make_payload(step=1, pos=(4, 4)):
    return {"step": step, "position": list(pos), "move": "N", "verdict": "lie"}


class TestCommitReveal:
    def test_commit_is_deterministic_given_nonce(self):
        sealed = CommitReveal.seal(make_payload())
        again = CommitReveal.commit_of(make_payload(), sealed["nonce"])
        assert sealed["commit"] == again

    def test_seal_produces_unique_nonces(self):
        a = CommitReveal.seal(make_payload())
        b = CommitReveal.seal(make_payload())
        assert a["nonce"] != b["nonce"]
        assert a["commit"] != b["commit"]

    def test_verify_accepts_honest_reveal(self):
        sealed = CommitReveal.seal(make_payload())
        CommitReveal.verify(make_payload(), sealed["nonce"], sealed["commit"])

    def test_verify_rejects_tampered_payload(self):
        sealed = CommitReveal.seal(make_payload(pos=(4, 4)))
        with pytest.raises(CryptoError):
            CommitReveal.verify(make_payload(pos=(5, 4)), sealed["nonce"], sealed["commit"])

    def test_verify_rejects_wrong_nonce(self):
        sealed = CommitReveal.seal(make_payload())
        with pytest.raises(CryptoError):
            CommitReveal.verify(make_payload(), "0" * 32, sealed["commit"])

    def test_payload_key_order_irrelevant(self):
        sealed = CommitReveal.seal({"a": 1, "b": 2})
        CommitReveal.verify({"b": 2, "a": 1}, sealed["nonce"], sealed["commit"])


class TestAudit:
    def _record(self, step, pos):
        payload = make_payload(step, pos)
        sealed = CommitReveal.seal(payload)
        return {"payload": payload, "nonce": sealed["nonce"], "commit": sealed["commit"]}

    def test_audit_passes_honest_log(self):
        log = [self._record(i, (i, i)) for i in range(1, 6)]
        result = audit_records(log)
        assert result["passed"] is True
        assert result["verified_steps"] == 5

    def test_audit_flags_tampered_step(self):
        log = [self._record(i, (i, i)) for i in range(1, 4)]
        log[1]["payload"]["position"] = [9, 9]  # cheat: rewrite history
        result = audit_records(log)
        assert result["passed"] is False
        assert 2 in result["failed_steps"]
