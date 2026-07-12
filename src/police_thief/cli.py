# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""CLI: run one standalone peer (with its own GUI) or replay a saved log.

Zero business logic here — everything delegates to SimulationSdk.
Two terminals, two peers, no central server:
    uv run python -m police_thief peer --role thief
    uv run python -m police_thief peer --role police
"""

import argparse
import json
import sys
from pathlib import Path

from police_thief.sdk.sdk import SimulationSdk


def _default_config(role: str) -> str:
    """Each peer has its OWN config dir - two students, two setups."""
    return str(Path("config") / role)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="police_thief",
        description="Distributed cop-vs-thief AI simulation (peer-to-peer, no central server)",
    )
    sub = parser.add_subparsers(dest="command")

    peer = sub.add_parser("peer", help="run one standalone agent peer")
    peer.add_argument("--role", required=True, choices=["thief", "police"])
    peer.add_argument("--config", default=None,
                      help="config directory (default: config/<role>)")
    peer.add_argument("--stub-llm", action="store_true",
                      help="deterministic policy instead of claude -p (dev/dry runs)")
    peer.add_argument("--no-gui", action="store_true", help="headless (console only)")

    replay = sub.add_parser("replay", help="replay a saved match log visually")
    replay.add_argument("--log", required=True, help="path to a saved match JSON log")
    replay.add_argument("--config", default=_default_config("police"),
                        help="config directory (board/GUI settings for rendering)")
    return parser


def _launch_replay(config, log_data: dict, log_path: str) -> None:  # pragma: no cover - Tkinter
    from police_thief.gui.player import ReplayApp

    ReplayApp(config, log_data, log_path=log_path).run()


def _run_peer(args) -> int:
    from police_thief.exceptions import SimulationError

    try:
        return _run_peer_inner(args)
    except SimulationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _run_peer_inner(args) -> int:
    sdk = SimulationSdk(args.config or _default_config(args.role))
    if args.no_gui:
        outcome = sdk.run_peer(args.role, stub_llm=args.stub_llm)
    else:  # pragma: no cover - Tkinter
        from police_thief.gui.player import LivePeerApp

        outcome = LivePeerApp(sdk, args.role, stub_llm=args.stub_llm).run()
    summary = outcome["summary"]
    print(json.dumps(
        {"result": summary["result"], "winner": summary["winner"],
         "steps": summary["steps"], "log": outcome["log_path"],
         "email": outcome["email"]},
        ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.command == "peer":
        return _run_peer(args)
    if args.command == "replay":
        sdk = SimulationSdk(args.config)
        _launch_replay(sdk.config, sdk.load_log(args.log), args.log)
        return 0
    parser.print_help()
    return 2
