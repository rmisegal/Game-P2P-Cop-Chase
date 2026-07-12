# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Bidirectional-control integration for the turn loop, kept out of runtime.py.

`pump` enables on request, drains inbound control, and broadcasts this peer's
live status; `check` turns control intents into game effects (quit / opponent
quit end the game, a restart raises RestartSeries for the series loop)."""

from police_thief.exceptions import RestartSeries
from police_thief.peer.control_link import (
    GAME_OVER,
    PAUSED,
    PLAYING,
    QUIT,
    STOPPED,
    THINKING,
    WAITING,
)

__all__ = ["pump", "check", "GAME_OVER", "PLAYING", "THINKING", "WAITING"]


def _status_for(rt, base: str) -> str:
    controls = rt.controls
    if controls.quit_requested:
        return QUIT
    if controls.stopped:
        return STOPPED
    if controls.paused:
        return PAUSED
    return base


def pump(rt, base: str) -> None:
    """Enable on request, process inbound control, and broadcast my status."""
    if rt.controls.enable_requested and not rt.link.i_enabled:
        rt.link.enable()
    rt.link.drain()
    budget = rt.controls.speed
    if budget is None:
        budget = rt._config.get("llm.step_deadline_seconds") or 0.0
    rt.link.broadcast_status(_status_for(rt, base), rt._sub_game_number, budget)


def check(rt) -> None:
    """React to control intents. Raises RestartSeries to restart the whole series."""
    if rt.controls.quit_requested:
        rt.link.send_quit()
        rt._result = ("quit", "-")
        return
    if rt.link.opponent_quit:
        rt._result = ("opponent_quit", rt.role.value)
        return
    if rt.controls.restart_requested:          # locally initiated
        rt.controls.clear_restart()
        rt.link.send_restart()
        raise RestartSeries()
    if rt.link.take_pending_restart():         # peer-initiated, already approved
        raise RestartSeries()
