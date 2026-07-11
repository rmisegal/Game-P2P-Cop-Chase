# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""SimulationSdk — every consumer (CLI, GUI, third parties) goes through here.

run_peer() runs one standalone agent through a whole SERIES of N sub-games (its
own MCP server, its own claude -p brain, its own state — connected to the
opponent only by URL). The transport/servers are built ONCE and kept alive
across the series; roles alternate each sub-game. It writes the four standardized
game JSON artifacts (declaration, config, log, result), keeps the legacy Hebrew
report/log for back-compat, and (if enabled) emails the result JSON.
"""

import json
from pathlib import Path

from police_thief.constants import Role
from police_thief.infra.email_sender import EmailSender
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
        """Play the whole series; write the four artifacts; email the result."""
        from police_thief.peer.sealing import terms_from_config
        from police_thief.report.emit import emit_series
        from police_thief.sdk.series import run_series

        peer_role = Role(role)
        # Build the transport (and this peer's MCP server) ONCE for the whole series.
        transport = transport or self._build_transport(peer_role)
        series = run_series(self.config, peer_role, self._build_llm(stub_llm),
                            transport, listener=listener, controls=controls)

        logs_dir = self._workdir / self.config.get("paths.logs_dir", "logs")
        result_json = emit_series(self.config, logs_dir, series)

        last = series.summaries[-1]
        report = build_report(last, self.config, terms=terms_from_config(self.config))
        self._save_log(peer_role, last, report)  # legacy Hebrew log (back-compat)

        winner = result_json["final_result"].get("winner_group") or last["winner"]
        subject = f"Police-Thief series result: winner {winner} (reported by {role})"
        email = EmailSender(self.config).send_report(result_json, subject)
        result_path = logs_dir / f"result_{series.game_id}.json"
        return {"summary": last, "report": report, "email": email,
                "summaries": series.summaries, "result": result_json,
                "log_path": str(result_path)}

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
