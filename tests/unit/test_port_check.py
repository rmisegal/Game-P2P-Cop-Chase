"""Tests for the MCP-port pre-flight check (WinError 10048 prevention)."""

import socket

import pytest

from police_thief.exceptions import SimulationError
from police_thief.infra.mcp_server import _ensure_port_free


class TestPortCheck:
    def test_free_port_passes(self):
        _ensure_port_free("127.0.0.1", 0)  # ephemeral port: always free

    def test_taken_port_raises_with_instructions(self):
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        port = holder.getsockname()[1]
        try:
            with pytest.raises(SimulationError) as excinfo:
                _ensure_port_free("127.0.0.1", port)
            message = str(excinfo.value)
            assert str(port) in message
            assert "Get-NetTCPConnection" in message   # actionable fix included
            assert "network.my_port" in message
        finally:
            holder.close()
