# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Send the match report to the lecturer via the global gg:email skill.

Safety defaults: disabled unless config says otherwise, and 'draft' mode
creates a Gmail draft rather than sending. All invocations pass through the
ApiGatekeeper (service 'email').
"""

import json
import subprocess

from police_thief.exceptions import ProviderCliError
from police_thief.shared.config import ConfigManager
from police_thief.shared.gatekeeper import ApiGatekeeper


class EmailSender:
    """Creates the report email as a Gmail draft through gg:email."""

    def __init__(self, config: ConfigManager):
        self._config = config
        self._gatekeeper = ApiGatekeeper(config, service="email")

    def send_report(self, report: dict, subject: str) -> dict:
        if not self._config.get("email.enabled", False):
            return {"sent": False, "reason": "disabled"}
        try:
            self._gatekeeper.execute(self._invoke_skill, report, subject)
            return {"sent": True, "mode": self._config.get("email.mode", "draft")}
        except ProviderCliError as exc:
            return {"sent": False, "reason": str(exc)}

    def _invoke_skill(self, report: dict, subject: str) -> None:
        body = json.dumps(report, ensure_ascii=False, indent=2)
        command = [
            "uv", "run", "--project", self._config.get("email.skill_lib"),
            "python", self._config.get("email.draft_script"),
            "--to", self._config.get("email.recipient"),
            "--subject", subject,
            "--body", body,
        ]
        result = subprocess.run(
            command, capture_output=True, text=True,
            timeout=self._config.get("email.timeout_seconds", 120),
            encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            raise ProviderCliError(
                result.stderr.strip() or result.stdout.strip() or "gg:email failed"
            )
