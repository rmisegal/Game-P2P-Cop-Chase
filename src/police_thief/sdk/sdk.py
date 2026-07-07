# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""SimulationSdk — every consumer (CLI, GUI, third parties) goes through here.

run_peer() runs ONE standalone agent: its own MCP server, its own claude -p
brain, its own state — connected to the opponent only by URL. It saves the
match log, builds the Hebrew report and (if enabled) emails it.
"""

import json
from pathlib import Path

from police_thief.constants import Role
from police_thief.infra.email_sender import EmailSender
from police_thief.peer.runtime import PeerRuntime
from police_thief.report.report_writer import build_report
from police_thief.shared.config import ConfigManager


class StubLlm:
    """Unparseable on purpose: forces the deterministic fallback policy."""

    last_usage = {"model": "stub", "in": 0, "out": 0, "total": 0}
    tokens_consumed = 0

    def send(self, prompt: str) -> str:
        return "stub reply - no structured move here"


class GatedLlm:
    """claude -p provider routed through the API gatekeeper."""

    def __init__(self, provider, gatekeeper):
        self._provider = provider
        self._gatekeeper = gatekeeper

    @property
    def last_usage(self) -> dict:
        return self._provider.last_usage

    @property
    def tokens_consumed(self) -> int:
        return self._provider.tokens_consumed

    def send(self, prompt: str) -> str:
        return self._gatekeeper.execute(self._provider.send, prompt)


class SimulationSdk:
    """Facade over the whole simulation."""

    def __init__(self, config_dir: str | Path, workdir: str | Path = "."):
        self.config = ConfigManager(config_dir)
        self._workdir = Path(workdir)

    def _build_llm(self, stub: bool):
        if stub:
            return StubLlm()
        from police_thief.infra.llm_provider import ClaudeCliProvider
        from police_thief.shared.gatekeeper import ApiGatekeeper

        return GatedLlm(
            ClaudeCliProvider(self.config), ApiGatekeeper(self.config, service="claude")
        )

    def _build_transport(self, role: Role):
        from police_thief.infra.mcp_client import McpTransport
        from police_thief.infra.mcp_server import start_peer_server

        # Total separation: MY config knows only MY port and the opponent's URL —
        # exactly what one student knows about the other over the internet.
        cfg = self.config
        inboxes = start_peer_server(role.value, cfg.get("network.host", "127.0.0.1"),
                                    cfg.get("network.my_port"))
        return McpTransport(
            cfg.get("network.opponent_url"), inboxes,
            connect_timeout=cfg.get("network.connect_timeout_seconds", 60),
            retry_interval=cfg.get("network.retry_interval_seconds", 1.0),
            audit_send_timeout=cfg.get("network.audit_send_timeout_seconds", 10),
        )

    def run_peer(self, role: str, stub_llm: bool = False, transport=None,
                 listener=None, controls=None) -> dict:
        """Run one agent to completion; persist log; build report; email it."""
        peer_role = Role(role)
        runtime = PeerRuntime(
            role=peer_role, config=self.config,
            llm=self._build_llm(stub_llm),
            transport=transport or self._build_transport(peer_role),
            listener=listener, controls=controls,
        )
        summary = runtime.run()
        from police_thief.peer.sealing import terms_from_config

        report = build_report(summary, self.config, terms=terms_from_config(self.config))
        log_path = self._save_log(peer_role, summary, report)
        subject = (
            f"Police-Thief match result: {summary['result']} "
            f"(winner: {summary['winner']}, reported by {role})"
        )
        email = EmailSender(self.config).send_report(report, subject)
        return {"summary": summary, "report": report, "email": email,
                "log_path": str(log_path)}

    def _save_log(self, role: Role, summary: dict, report: dict) -> Path:
        logs_dir = self._workdir / self.config.get("paths.logs_dir", "logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        pattern = self.config.get("paths.log_filename", "{role}_match.json")
        path = logs_dir / pattern.format(role=role.value)
        path.write_text(
            json.dumps({"summary": summary, "report": report}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def load_log(path: str | Path) -> dict:
        """Load a saved match log (for the replay player)."""
        return json.loads(Path(path).read_text(encoding="utf-8"))
