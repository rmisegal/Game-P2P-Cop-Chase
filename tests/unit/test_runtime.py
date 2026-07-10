"""Integration test: two full PeerRuntimes play a distributed match over an
in-process fake transport (no central server, only message passing)."""

import queue
import threading

import pytest

from police_thief.constants import Role
from police_thief.peer.runtime import PeerRuntime


class FakeTransport:
    """One side of a queue-pair 'network' between the two peers."""

    def __init__(self, inbox: queue.Queue, outbox: queue.Queue):
        self._inbox = inbox
        self._outbox = outbox

    def exchange_agreement(self, signed: dict) -> dict:
        self._outbox.put(("agreement", signed))
        kind, payload = self._inbox.get(timeout=5)
        assert kind == "agreement"
        return payload

    def send_turn(self, message: dict) -> None:
        self._outbox.put(("turn", message))

    def poll_turn(self, timeout: float) -> dict | None:
        try:
            kind, payload = self._inbox.get(timeout=timeout)
        except queue.Empty:
            return None
        return payload if kind == "turn" else None

    def exchange_audit(self, payload: dict) -> dict | None:
        self._outbox.put(("audit", payload))
        try:
            kind, data = self._inbox.get(timeout=5)
        except queue.Empty:
            return None
        return data if kind == "audit" else None


class GarbageLlm:
    """Always unparseable -> brains use their deterministic fallback policy."""

    def send(self, prompt: str) -> str:
        return "no json here"


@pytest.fixture
def paired_runtimes(config):
    a_to_b: queue.Queue = queue.Queue()
    b_to_a: queue.Queue = queue.Queue()
    thief = PeerRuntime(
        role=Role.THIEF, config=config, llm=GarbageLlm(),
        transport=FakeTransport(inbox=b_to_a, outbox=a_to_b),
    )
    police = PeerRuntime(
        role=Role.POLICE, config=config, llm=GarbageLlm(),
        transport=FakeTransport(inbox=a_to_b, outbox=b_to_a),
    )
    return thief, police


def run_match(thief: PeerRuntime, police: PeerRuntime):
    results: dict = {}

    def runner(name, runtime):
        results[name] = runtime.run()

    threads = [
        threading.Thread(target=runner, args=("police", police), daemon=True),
        threading.Thread(target=runner, args=("thief", thief), daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
        assert not t.is_alive(), "peer runtime did not finish"
    return results


class TestDistributedMatch:
    def test_full_match_completes_and_agrees(self, paired_runtimes):
        thief, police = paired_runtimes
        results = run_match(thief, police)
        assert results["thief"]["result"] == results["police"]["result"]
        assert results["thief"]["winner"] == results["police"]["winner"]
        assert results["thief"]["result"] in ("capture", "survival")

    def test_audits_pass_both_ways(self, paired_runtimes):
        thief, police = paired_runtimes
        results = run_match(thief, police)
        assert results["thief"]["audit"]["passed"] is True
        assert results["police"]["audit"]["passed"] is True
        assert results["thief"]["audit"]["verified_steps"] > 0

    def test_logs_are_sealed_per_step(self, paired_runtimes):
        thief, police = paired_runtimes
        results = run_match(thief, police)
        for record in results["thief"]["records"]:
            assert set(record) >= {"payload", "nonce", "commit"}
            assert len(record["commit"]) == 64
        step_payloads = [r["payload"] for r in results["thief"]["records"]
                         if r["payload"].get("type") != "system_spec"]
        assert all("response_seconds" in p and "random_move" in p for p in step_payloads)

    def test_summary_carries_game_identity_and_timer(self, paired_runtimes):
        thief, police = paired_runtimes
        results = run_match(thief, police)
        for summary in results.values():
            assert summary["group_name"] == "TestGroup"
            assert summary["sub_game_number"] == 1
            assert summary["duration_seconds"] >= 0
            assert summary["started_at"]

    def test_timeout_when_opponent_silent(self, config):
        dead: queue.Queue = queue.Queue()
        lonely = PeerRuntime(
            role=Role.POLICE, config=config, llm=GarbageLlm(),
            transport=FakeTransport(inbox=queue.Queue(), outbox=dead),
        )
        lonely._negotiation_done = True  # skip handshake: nobody to shake with
        result = lonely.run(skip_negotiation=True)
        assert result["result"] == "timeout"
