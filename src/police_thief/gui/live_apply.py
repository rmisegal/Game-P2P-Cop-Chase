# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Apply one runtime event to the live window. Split from player.py so the app
stays focused on lifecycle (and within the 150-line rule). Also renders the
opponent's shared status/quit and flips Restart on once the channel is active."""

import time


def activate_if_ready(app) -> None:
    """When BOTH sides have enabled the channel, allow Restart and say so."""
    if app._bidi_i and app._bidi_peer:
        app._bar.set_restart_enabled(True)
        app._window.set_label("opp_status", "bidirectional channel ACTIVE")


def _apply_control(app, event: dict) -> None:
    window, kind = app._window, event["type"]
    if kind == "control_enable":
        app._bidi_peer = True
        window.set_label("opp_status", "opponent enabled bidirectional control")
        activate_if_ready(app)
    elif kind == "control_status":
        window.set_label("opp_status", f"{event.get('status')} | sub-game "
                         f"{event.get('sub_game_number')} | budget "
                         f"{event.get('step_budget')}s")
    elif kind == "control_quit":
        window.set_label("opp_status", "QUIT")
        window.set_turn(False, "OPPONENT QUIT")
    elif kind == "control_restart":
        granted = "granted" if event.get("granted") else "ignored (both must enable)"
        window.set_label("status", f"opponent restart {granted}")


def apply_event(app, event: dict) -> None:
    """Dispatch a single runtime/control event onto the live window."""
    window, kind = app._window, event["type"]
    if kind == "error":
        window.set_turn(False, "ERROR - see status")
        window.set_label("status", event["message"])
        return
    if kind.startswith("control_"):
        _apply_control(app, event)
        return
    if kind == "series_restart":
        window.set_turn(False, f"SERIES RESTARTED (attempt {event.get('attempt')})")
        return
    window.render(event["view"])
    if kind == "negotiated":
        app._t0 = time.monotonic()  # game clock starts at agreement
        window.set_label("status", "Agreement signed & verified (SHA-256)")
        window.set_turn(app._role == "thief")  # thief moves first
    elif kind == "incoming":
        message = event["message"]
        window.set_label("hint_in", f"step {message['step']}: {message['hint']}")
        window.set_turn(True)
    elif kind == "moved":
        _apply_moved(app, event)
    elif kind == "game_over":
        _apply_game_over(app, event)


def _apply_moved(app, event: dict) -> None:
    window, decision, usage = app._window, event["decision"], event.get("usage", {})
    window.set_label("tokens",
                     f"{usage.get('total', 0):,} / {usage.get('match_total', 0):,}")
    window.set_label("llm_time", f"{decision.response_seconds:.2f}"
                     + (" [RANDOM - deadline missed]" if decision.random_move else ""))
    window.set_label("hint_out", f"step {event['view']['step']}: {decision.hint}")
    window.set_label("verdict", decision.verdict
                     + (" (fallback policy)" if decision.fallback else ""))
    window.set_label("commit", event["commit"][:32] + "...")
    window.set_turn(False)


def _apply_game_over(app, event: dict) -> None:
    window, summary = app._window, event["summary"]
    audit = summary["audit"]
    verdict = "PASSED" if audit["passed"] else "FAILED"
    window.set_turn(False, f"GAME OVER: {summary['result']} - "
                           f"winner {summary['winner'].upper()}")
    app._t0 = None  # freeze the title clock
    window.set_label("status", f"Audit {verdict}: {audit['verified_steps']} steps "
                     f"verified | tokens total: {summary.get('tokens_total', 0):,} | "
                     f"duration: {summary.get('duration_seconds', 0)}s")
