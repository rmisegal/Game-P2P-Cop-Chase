# PLAN — GUI control channel, game modes, and sub-game controls

Status: **DRAFT for approval.** Scope: the six GUI/protocol requests below, built
SDK-first and OOP per `glb-quality-code-guidlines` (single SDK entry for business
logic, no duplication, ≤150 code lines/file, TDD, ruff-clean, ≥85% coverage).

## 1. Requirements (verbatim intent)

1. **Game mode + model field.** The move is always Python; the GUI must show the
   *verbal-game* mode from **book Table 22** and the correct model:
   `template → "Python (template)" / model "None"`, `ollama → "Ollama" / model`,
   `claude_api|claude_cli → "Remote LLM" / model`. Fixes the current bug where the
   Model field shows `claude-opus-4-8` even though the shipped game runs `template`.
2. **In-game restart via a bidirectional control channel**, and each side sees the
   **other side's status** (waiting / playing / paused / stopped / game-over /
   step-time-budget).
3. **Hint labels:** show the step number on `Opponent says (step N)` and on the own
   line, and **rename "I said" → "My response (step N)"**.
4. **Quit button:** clean local shutdown that also **informs the opponent** it quit.
5. **Tools menu → "Bidirectional control messages" checkbox.** Default OFF (behaves
   exactly as today). When ON it requests the channel; it becomes active only when
   **both** sides enable it, otherwise this side **waits** and the GUI shows that a
   request was sent and we are waiting for the opponent.
6. **Sub-games dropdown 1–6** (default 1) to set the series length before play.

## 2. Confirmed design decisions

- **Launch:** add an explicit **Start** button. The live window opens **idle**; you set
  the sub-games count and (optionally) the bidirectional checkbox, then click **Start**
  to negotiate and play. (Removes today's auto-start.) `--no-gui` keeps auto-start.
- **Restart scope:** a granted restart restarts the **whole series from sub-game 1**;
  everything played so far is discarded.
- **Restart approval:** **auto-approve** — if the opponent also has bidirectional
  control enabled, a restart request is granted automatically (no click).
- **Quit:** **always** shuts this peer down cleanly; **additionally** notifies the
  opponent when bidirectional control is active (else the opponent falls back to its
  normal turn-timeout technical win, as today).

## 3. Book alignment

- **Table 22 (Appendix, newer book rev — not in the bundled v1.0.38 PDF)** — the four
  verbal-game LLM modes = the code's `trash_talk.provider`. Drives requirement 1
  (mapping table above).
- **§8.3 State Machine (Figure 11, in the bundled PDF)** — the legal turn phases:
  `WAITING_FOR_OPPONENT → COMPUTING_MOVE → COMMITTING → AWAITING_REVEAL → VERIFYING →`
  (loop), `TECHNICAL_LOSS` terminal; `CONTROLLED_SHUTDOWN`/`StatePersistence` for clean
  quit (§8.4.2). Requirement 2 statuses are **not** in a table, so the broadcast status
  reuses these phase names for the turn layer and adds the control overlay:

  | Broadcast status | Meaning | Source |
  |---|---|---|
  | `WAITING` (`WAITING_FOR_OPPONENT`) | opponent's turn; I'm idle | §8.3 |
  | `THINKING` (`COMPUTING_MOVE`) | my turn, computing | §8.3 |
  | `PLAYING` | running (control overlay) | control |
  | `PAUSED` | user paused this peer | control |
  | `STOPPED` | user stopped this peer | control |
  | `GAME_OVER` | series/sub-game finished | terminal |
  | `QUIT` (`CONTROLLED_SHUTDOWN`) | user quit; clean shutdown | §8.4.2 |

  Each status broadcast also carries the live `step_time_budget` (seconds) and the
  current `sub_game_number`.

## 4. Architecture (SDK + OOP, no duplication)

New/changed pieces, each a small single-concern unit:

- **`domain/protocol.py`** — add `ControlMessage` dataclass
  (`kind`, `sender`, `sub_game_number`, `status`, `step_budget`, `payload`), same
  `to_dict`/`from_dict` contract as `TurnMessage`. `kind ∈ {enable, status,
  restart, quit}`.
- **`infra/mcp_server.py`** — add a `controls` inbox + a `receive_control` tool.
- **`infra/mcp_client.py`** (+ test `FakeTransport`) — add `send_control(message)` and
  `poll_control(timeout)`, mirroring `send_turn`/`poll_turn`.
- **`peer/control_link.py`** (NEW, OOP) — `ControlLink`: owns the bidirectional
  handshake (I-enabled / peer-enabled → active), the opponent's last known status, and
  the outbound `enable/status/restart/quit` sends. Pure logic over an injected
  transport; unit-testable with the fake transport. No Tk, no threads.
- **`peer/controls.py`** — extend `GameControls`: add a `restart` event, a `quit`
  event + `quit_requested`, a `status` string, and expose the current step budget.
- **`peer/runtime.py`** — in the turn loop: drain the control inbox via `ControlLink`,
  broadcast my status on each phase change, and honor `restart`/`quit`. A granted
  restart raises a small `RestartSeries` signal caught by the series loop; quit ends the
  loop with `("quit", "-")` after notifying.
- **`sdk/series.py`** — catch `RestartSeries` and re-run the series from sub-game 1
  (bounded retry count logged).
- **`sdk/sdk.py`** — expose the control capability as the single business entry:
  `run_peer(...)` keeps working; add `SimulationSdk.game_mode()` (Table-22 mode+model
  helper) and pass a `ControlLink` into the runtime. GUI calls only the SDK.
- **`gui/`** — split to stay ≤150 lines:
  - `gui/game_mode.py` (NEW, pure) — `mode_and_model(config) -> (mode, model)` per
    Table 22 (also usable headless/tested).
  - `gui/live_controls.py` (NEW) — the Start button, Tools menu (bidirectional
    checkbox), Quit/Restart buttons, sub-games dropdown, opponent-status panel.
  - `gui/player.py` — `LivePeerApp` wires GUI actions → `GameControls`/SDK and control
    events → the existing event queue; Start gates the worker thread.
  - `gui/window.py` — Model row shows `mode` + `model`; hint rows show the step number
    and the "My response" label; add an "Opponent status" row.

## 5. Phased, test-driven build order

Each phase ends green (ruff + pytest + coverage) and is a separate commit.

- **P0 — low-risk GUI/labels (no protocol):** req 1 (`game_mode.py` + Model row),
  req 3 (step-numbered hint rows + "My response"), req 6 dropdown + req-2/5 **Start**
  gate scaffolding (buttons present, wired to local `GameControls` only). Tests:
  `game_mode.mode_and_model` for all four providers.
- **P1 — control transport:** `ControlMessage`, `receive_control` tool, `controls`
  inbox, `send_control`/`poll_control` on real + fake transport. Tests: round-trip.
- **P2 — control logic (OOP):** `ControlLink` + `GameControls` extension. Tests:
  enable-handshake becomes active only when both enable; status tracking;
  restart/quit sends.
- **P3 — runtime/series integration:** status broadcast on phase changes, auto-approve
  restart (whole series), quit notification, `RestartSeries` handling. Tests via the
  fake transport driving a runtime.
- **P4 — GUI wiring:** Tools menu checkbox with "waiting for opponent" indicator,
  opponent-status panel, Quit/Restart buttons active only per the rules, Start gate.
- **P5 — docs + release:** README (Tools menu, statuses, Start flow, game modes),
  STRATEGY if needed, version bump, full verify.

## 6. Risks / notes

- **`num_games` is a signed term.** The dropdown sets it locally before Start; if the
  two peers pick different values the existing signature check refuses to play with a
  clear message. Documented as expected behavior.
- **Bidirectional channel is a runtime opt-in, NOT a signed term** — it changes no game
  outcome, so it stays out of `game.json`/`terms_from_config`.
- **GUI files are coverage-omitted**; all new *pure* logic (`game_mode`, `ControlLink`,
  `ControlMessage`) lives outside `gui/` or is factored so it is unit-tested.
