"""Tests for SimulationSdk: the single business-logic entry point."""

import json
import queue
import threading

from police_thief.sdk.sdk import SimulationSdk, StubLlm


class FakeTransport:
    def __init__(self, inbox, outbox):
        self._inbox, self._outbox = inbox, outbox

    def exchange_agreement(self, signed):
        self._outbox.put(("agreement", signed))
        return self._inbox.get(timeout=5)[1]

    def send_turn(self, message):
        self._outbox.put(("turn", message))

    def poll_turn(self, timeout):
        try:
            kind, payload = self._inbox.get(timeout=timeout)
            return payload if kind == "turn" else None
        except queue.Empty:
            return None

    def exchange_audit(self, payload):
        self._outbox.put(("audit", payload))
        try:
            return self._inbox.get(timeout=5)[1]
        except queue.Empty:
            return None


def paired_sdks(config_dir, tmp_path):
    a_to_b, b_to_a = queue.Queue(), queue.Queue()
    thief_sdk = SimulationSdk(config_dir, workdir=tmp_path / "thief")
    police_sdk = SimulationSdk(config_dir, workdir=tmp_path / "police")
    return (
        (thief_sdk, FakeTransport(b_to_a, a_to_b)),
        (police_sdk, FakeTransport(a_to_b, b_to_a)),
    )


class TestSimulationSdk:
    def test_run_peer_full_match_and_log_files(self, config_dir, tmp_path):
        (thief_sdk, thief_tr), (police_sdk, police_tr) = paired_sdks(config_dir, tmp_path)
        results = {}

        def run(name, sdk, role, transport):
            results[name] = sdk.run_peer(role, stub_llm=True, transport=transport)

        threads = [
            threading.Thread(target=run, args=("police", police_sdk, "police", police_tr),
                             daemon=True),
            threading.Thread(target=run, args=("thief", thief_sdk, "thief", thief_tr),
                             daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
            assert not t.is_alive()

        assert results["thief"]["summary"]["winner"] == results["police"]["summary"]["winner"]
        log_file = tmp_path / "thief" / "logs" / "thief_match.json"
        assert log_file.exists()
        saved = json.loads(log_file.read_text(encoding="utf-8"))
        assert saved["report"]["סוג_דוח"] == "משחק_ליגה_רשמי"
        assert results["thief"]["email"]["sent"] is False  # disabled in test config

    def test_replay_loads_saved_log(self, config_dir, tmp_path):
        workdir = tmp_path / "w"
        sdk = SimulationSdk(config_dir, workdir=workdir)
        log_path = workdir / "logs" / "x.json"
        log_path.parent.mkdir(parents=True)
        log_path.write_text(json.dumps({"summary": {"steps": 3}}), encoding="utf-8")
        assert sdk.load_log(log_path)["summary"]["steps"] == 3

    def test_stub_llm_reply_is_unparseable(self):
        assert "{" not in StubLlm().send("any prompt")
