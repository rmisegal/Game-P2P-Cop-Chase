# Plan v2: FULLY DISTRIBUTED Cop-vs-Thief Simulation (no central server)

## Context — architecture correction (user-mandated, supersedes v1)

Each AI agent (Police / Thief) is a **standalone peer process** that cannot see the other's
activities. There is **NO central server, NO referee, NO shared board state — mandatory.**
Each peer runs its **own FastMCP server** managing its own activities; the only a-priori
knowledge is the **opponent's MCP URL** (localhost, different ports). The simulation mimics
two students playing over the internet. The **entire game relies on cryptographic sealing
keys** (per-step SHA-256 commit + end-of-game nonce reveal & audit) that guarantee locations
and actions are verifiable after the game — this is the core idea.

**Gameplay UX:** open 2 terminals; each runs one peer with its own Tkinter GUI showing:
- my TRUE position + my smell values (only my own truth),
- a **belief heatmap** predicting the opponent's location (from their NL hints + smell grids),
- **green turn indicator**: I turn green when the opponent's message arrives; I stop being
  green once I've moved and delivered my message; then the opponent turns green. Ping-pong.

All prior locked decisions stand: `claude -p` (browser login, env stripped) decides
move+hint+truth/lie; SHA-256 commit-reveal; both grids configurable in TOML; email report
(draft, disabled by default) via gg:email; all 14 glb-quality rules.

## Distributed protocol (peer ↔ peer over MCP HTTP)

Message per turn (sent by the mover to the opponent's MCP `receive_turn` tool):
```json
{
  "step": 7, "sender": "thief",
  "hint": "<free NL, contains location cue, may lie>",
  "smell_grid": {"center": [r,c], "values": [[...MxM...]]},
  "barrier_placed": null | [r,c],          // public: impassable for both
  "commit": "sha256(state|move|verdict|nonce)",   // sealed BEFORE truth knowable
  "capture_claim": null | [r,c],           // cop only: "I claim you are here"
  "claim_response": null | {"claim": [r,c], "caught": true|false},  // thief answers cop's claim
  "win_claim": null | {"type": "survival|unique_cells"},            // thief's victory claim
  "timestamp": "ISO-8601"
}
```
- **Turn token travels with the message** — receiving a turn makes you green.
- **Thief moves first.** Pre-game **negotiation phase** over MCP: exchange Agreement JSON
  (board size, smell size, decay, max steps, setting) + mutual `SHA256(agreement|nonce)`
  signatures; play starts only after both verified.
- **Capture protocol (no referee):** cop sends `capture_claim=[r,c]`; thief's peer compares
  to its TRUE position and must answer honestly (`caught`). A false answer is provably caught
  in the audit (hash mismatch vs revealed states) → forfeit. Same for thief's `win_claim`.
- **End-of-game audit:** both peers exchange full raw logs + all nonces via MCP
  `exchange_audit` tool; each independently re-computes every commit hash of the opponent;
  both must agree → `הסכמה_הדדית: true` in the report.

## Revised file layout (each .py ≤150 code lines)

```
src/police_thief/
├── __init__.py  __main__.py  cli.py  constants.py  exceptions.py    [DONE, keep]
├── shared/   version.py  config.py  gatekeeper.py  rate_limiter.py  [config DONE, rest as v1]
├── sdk/      sdk.py            # run_peer(role), replay(log), send_report — single entry
├── domain/
│   ├── board.py                # king moves, bounds, barrier validation (pure, no state)
│   ├── smell.py                # my smell field: MxM grid emit (center>=0.5), decay 0.1
│   ├── belief.py               # opponent-location heatmap: update from smell msg + hint + diffusion
│   ├── own_state.py            # OwnGameState: my pos, visited set, known barriers, step log
│   ├── rules.py                # win/lose checks on OWN state (unique cells, step cap, quota)
│   ├── crypto.py               # commit=SHA256(state|move|verdict|nonce); verify; audit_log()
│   ├── negotiation.py          # Agreement JSON + mutual signature exchange/verify
│   ├── protocol.py             # TurnMessage / AuditPayload dataclasses + (de)serialization
│   ├── agent_brain.py          # base: build prompt from OWN view, claude -p via gatekeeper, parse+fallback
│   ├── police_brain.py         # cop prompt: lie detection (hint vs smell), barriers, capture claims
│   └── thief_brain.py          # thief prompt: evade, deceptive hints, unique-cell coverage
├── peer/
│   ├── runtime.py              # PeerRuntime: negotiation → turn loop (recv → think → move → send) → audit
│   └── turn_handler.py         # applies incoming msg: belief update, claim handling, turn token
├── infra/
│   ├── llm_provider.py         # claude -p, login auth, env-strip (as v1)
│   ├── mcp_server.py           # FastMCP: tools receive_turn / negotiate / exchange_audit (own port)
│   ├── mcp_client.py           # calls the OPPONENT's MCP tools at its URL
│   └── email_sender.py         # gg:email draft via gatekeeper (as v1)
├── report/report_writer.py     # Hebrew JSON report from OWN log + audit result + consensus hash
└── gui/player.py               # per-peer GUI: my pos+smell, belief heatmap, GREEN turn state,
                                #   hints log, commit hashes, audit ✓/✗; replay mode from log
```

## Config additions (config/game.toml)

```toml
[network]
host = "127.0.0.1"
thief_port = 8801
police_port = 8802
turn_timeout_seconds = 180      # opponent silent longer than this -> technical result
```
(Everything else from v1 config stands. Opponent URL derived: http://host:other_role_port/mcp)

## How to run (two terminals, like two students)

```powershell
# Terminal 1 (student A):
uv run python -m police_thief peer --role police
# Terminal 2 (student B):
uv run python -m police_thief peer --role thief   # thief moves first once negotiation done
```
Each opens its own GUI. Replay: `uv run python -m police_thief replay --log logs/police_log.json`.

## Build order (TDD per module)

1. [DONE] Scaffold: uv, pyproject (ruff/coverage), configs, .env-example, constants, exceptions.
2. shared: ConfigManager → RateLimiter → ApiGatekeeper (+ tests).
3. domain: board → smell → belief → own_state → rules → crypto → negotiation → protocol (+ tests).
4. brains + llm_provider: claude -p provider (mocked in tests) → agent/police/thief brains
   with strict JSON contract + deterministic legal fallback (+ tests).
5. peer: turn_handler → PeerRuntime state machine (negotiate/wait/green/move/send/audit),
   tested with two in-process runtimes wired via fake transport.
6. infra MCP: FastMCP server (receive_turn/negotiate/exchange_audit) + client to opponent URL;
   integration: two real servers on 8801/8802 play a full stub-LLM match.
7. report + email (+ tests).
8. SDK + CLI (`peer --role`, `replay --log`) (+ tests).
9. GUI: per-peer Tkinter (green turn border, my truth, belief heatmap, crypto panel) + replay.
10. Quality gate (14 rules) + README + docs/PLAN.md copy.

## Verification

- Unit: `uv run pytest` ≥85% cov, ruff clean, all files ≤150 code lines.
- **Distributed E2E (stub LLM):** launch both peers on 8801/8802 → negotiation signatures
  verified → alternating turns to completion → audit PASS on both sides → two JSON logs whose
  cross-verification agrees.
- **Live E2E:** same with real `claude -p` in both terminals; GUIs ping-pong green.
- **Config proof:** change board.size/smell.grid_size/max_steps/ports → behavior follows.
- **Audit tamper test:** unit test corrupts one logged move → opponent's audit FAILS.
- Email: enabled+draft → Gmail draft created.
