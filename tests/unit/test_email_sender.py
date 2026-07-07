"""Tests for the gg:email-based report sender (draft mode, gatekeeper-routed)."""

from unittest.mock import MagicMock, patch

from police_thief.infra.email_sender import EmailSender


class TestEmailSender:
    def test_disabled_by_default_sends_nothing(self, config):
        sender = EmailSender(config)
        with patch("subprocess.run") as run:
            result = sender.send_report({"תוצאה": "לכידה"}, subject="match result")
        assert result["sent"] is False
        assert result["reason"] == "disabled"
        run.assert_not_called()

    def test_enabled_draft_invokes_skill_script(self, config):
        config._game["email"]["enabled"] = True
        sender = EmailSender(config)
        ok = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("subprocess.run", return_value=ok) as run:
            result = sender.send_report({"תוצאה": "לכידה"}, subject="match result")
        assert result["sent"] is True
        cmd = run.call_args[0][0]
        assert "draft.py" in " ".join(cmd)
        assert "--to" in cmd
        assert "someone@example.com" in cmd

    def test_failure_reported_not_raised(self, config):
        config._game["email"]["enabled"] = True
        sender = EmailSender(config)
        bad = MagicMock(returncode=1, stdout="", stderr="oauth expired")
        with patch("subprocess.run", return_value=bad):
            result = sender.send_report({}, subject="x")
        assert result["sent"] is False
        assert "oauth expired" in result["reason"]
