"""Tests for the Hebrew JSON match report + consensus signature."""

import hashlib
import json

from police_thief.report.report_writer import build_report, consensus_signature


def summary(result="capture", winner="police"):
    return {
        "result": result, "winner": winner, "steps": 5, "role": "police",
        "audit": {"passed": True, "verified_steps": 5, "failed_steps": []},
        "records": [
            {"payload": {"step": 1, "position": [6, 5], "move": "MOVE:N",
                         "verdict": "truth", "hint": "Closing in."},
             "nonce": "aa", "commit": "bb" * 32}
        ],
        "history": [
            {"step": 1, "sender": "thief", "hint": "Taxi east!",
             "smell_grid": {"4,4": 0.9},
             "commit": "cc" * 32, "timestamp": "2026-07-06T10:00:00Z",
             "barrier_placed": None, "capture_claim": None,
             "claim_response": None, "win_claim": None},
        ],
        "my_log": [{"step": 1, "position": [6, 5], "move": "MOVE:N",
                    "unique_cells": 2, "barrier": None}],
    }


class TestBuildReport:
    def test_hebrew_schema_present(self, config):
        report = build_report(summary(), config, terms={"setting": "New York"})
        assert report["סוג_דוח"] == "משחק_ליגה_רשמי"
        assert report["תוצאה"] == "לכידה"
        assert report["מנצח"] == "police"
        assert report["הסכמה_הדדית"] is True
        assert len(report["לוג_צעדים_מאומת"]) == 1

    def test_thief_win_result_word(self, config):
        report = build_report(summary("survival", "thief"), config, terms={})
        assert report["תוצאה"] == "הישרדות"

    def test_step_log_fields(self, config):
        report = build_report(summary(), config, terms={})
        step = report["לוג_צעדים_מאומת"][0]
        assert step["מספר_צעד"] == 1
        assert step["חתימת_מצב"] == "cc" * 32  # from the received-messages history
        assert step["טביעת_זמן"]

    def test_consensus_signature_is_sha256_of_report(self, config):
        report = build_report(summary(), config, terms={})
        signature = report["חתימת_קונסנזוס_משותפת"]
        clone = dict(report)
        del clone["חתימת_קונסנזוס_משותפת"]
        expected = hashlib.sha256(
            json.dumps(clone, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        assert signature == expected

    def test_consensus_signature_helper_stable(self):
        data = {"a": 1, "b": [2, 3]}
        assert consensus_signature(data) == consensus_signature({"b": [2, 3], "a": 1})
