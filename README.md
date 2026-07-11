# Police-vs-Thief: Fully Distributed AI Pursuit Simulation

<!-- VERSIONS: auto-synced by scripts/sync_versions.py via the pre-commit hook. Do not edit the values between the markers by hand. -->
> <!--CODE_VERSION_START-->**Code `v1.12`**<!--CODE_VERSION_END--> · <!--BOOK_VERSION_START-->based on the **guidelines book `v1.0.36`**<!--BOOK_VERSION_END--> — the full rules & guidelines PDF is bundled at [`docs/police_thief_p2p.pdf`](docs/police_thief_p2p.pdf).
>
> These two versions are **deep-linked**: the book's cover and its reference appendix display this code version (read at LaTeX compile time), and this line is refreshed from the book on every `git commit` (pre-commit hook). This code implements a **minimal subset** of that book.

Final-project simulation for Dr. Segal's "AI Agent Orchestration"
course: two **standalone AI agent peers** (Police and Thief) chase each other on a
configurable grid (currently **7×7**) — **no central server, no shared state, no
referee**. Each peer is a fully independent process, like two students playing over
the internet from two different PCs: its own FastMCP server, its own config, its own
`claude -p` brain (CLI browser login, never an API key), its own LLM model choice,
and its own Tkinter GUI. The entire game's integrity rests on **per-step SHA-256
commit-reveal sealing** verified by a mutual post-game audit.

> ### 📚 What this repo is — read this first
>
> This is the **public reference example** for the final project, described in the course
> guidelines book (appendix *"מאגר הקוד לדוגמה"*). Repository:
> **<https://github.com/rmisegal/Game-P2P-Cop-Chase>**
>
> It demonstrates the **basic game flow and a simple GUI, without strategy** — a **learning
> aid, not a submission skeleton**. It **intentionally does _not_ meet the full project
> specification**: there is **no point scoring**, movement uses **8-direction king moves**
> (the book mandates 4 orthogonal), capture-by-barrier and boxed-in capture are not
> implemented, and there is **no explicit state machine / watchdog**. **Do not start your
> submission from this repo.**
>
> You _may_ reuse or modify parts of the code, and use it to learn how a specific piece is
> implemented or to clarify anything left unclear in the book — but your **graded solution
> must meet the full specification on its own**. Where this repo differs from the book, the
> **book and its binding parameter table win**.
>
> **Tip — query the code with NotebookLM:** export all repo files to `.txt`, load them into
> [NotebookLM](https://notebooklm.google.com), and ask questions about the code as if you had
> a dedicated chatbot for the simulation — e.g. *"where is the belief map computed?"* or
> *"how is the commit-reveal protocol enforced?"*.

## Core idea

Each agent only ever knows:
1. Its **own** true position, visited cells and barrier quota.
2. The opponent's **free natural-language hints** (which may lie).
3. The opponent's **5×5 smell grids** (decaying 0.1/step) — fused into a belief heatmap.
4. The opponent's **sealed commits**: `SHA256(state|move|verdict|nonce)` sent every step,
   with nonces revealed only at the end-of-game audit. Nothing can be rewritten after the
   fact; a false capture answer or win claim is cryptographically caught and forfeits.

Capture protocol (no referee): the cop lands on a cell and sends a `capture_claim`; the
thief must answer honestly (the audit would expose a lie). The thief wins by surviving
`max_steps` (default 50) steps without being caught. A silent opponent past
`turn_timeout_seconds` is a technical loss.

Every sealed step payload records the **LLM model, token usage (delta-accounted:
a step that never called the LLM seals 0 tokens), response time, and whether the move
was random due to a missed deadline**. Each peer also seals a step-0 **host system
spec** record (CPU type/cores/frequency, RAM, GPU/VRAM, OS) plus its group name and
sub-game number — the book's §6 mandatory declaration, audit-verified like every move.

## Requirements

- Python 3.13+, [uv](https://docs.astral.sh/uv/), Claude CLI logged in via browser
  (`npm i -g @anthropic-ai/claude-code`, then run `claude` once). No API key — the
  provider strips `ANTHROPIC_API_KEY` etc. so the CLI always uses your subscription login.

## Install

```powershell
cd simulation
uv sync
```

## Play (two terminals — like two students over the internet)

```powershell
# Terminal 1
uv run python -m police_thief peer --role police

# Terminal 2
uv run python -m police_thief peer --role thief
```

Each peer automatically loads **its own config directory** (`config/police/`,
`config/thief/`) — two setups, optionally two different LLM models. The peers
negotiate the game agreement (mutual SHA-256 signatures over board size, smell size,
rules, start positions, setting) before the thief's first move; a mismatch refuses to
play. Everything then runs fully autonomously.

### The GUI (one per peer)

- **Title bar**: `<group name> | sub-game <n> | <ROLE> | mm:ss` — live game timer
  (starts at the signature exchange, freezes at game over).
- **Board**: my TRUE position, visited trail, known barriers, and a red **belief
  heatmap** of where the opponent probably is (their true position is unknowable).
- **Green banner** = my turn: lights when the opponent's message arrives, goes gray
  once my move is sealed and delivered.
- **Panel**: step, model, tokens step/total (thousands-formatted, e.g. `1,123,456`),
  **LLM response (s)** (with a `[RANDOM - deadline missed]` marker), barriers used /
  quota, both hints, my truth/lie verdict, my sealed commit, status.
- **Step time budget slider (0–60s)** — the ENFORCED total step time for MY agent:
  the LLM gets at most this long to answer; a miss plays a **random legal move**
  instantly, a fast answer is padded up to the budget. **0 = skip the LLM entirely**
  (pure random, maximum speed, zero tokens). Budgets under
  `short_prompt_threshold_seconds` automatically switch to a compact prompt so the
  model can answer in time. Watch the response-time label to find the smallest budget
  that avoids `[RANDOM]` moves.
- **Pause / Play / Stop**: Pause holds only MY agent before it thinks (a pause longer
  than the opponent's `turn_timeout_seconds` becomes its technical win, as in a real
  distributed game). Stop cancels my game (`result: "stopped"`, audit skipped) and
  closes the log session.
- **About / System spec** button: code version, role, model, and the full host spec.

## Replay a match (mandatory visual player)

```powershell
uv run python -m police_thief replay --log logs/police_match.json
```

Steps through the saved log with play/pause/step controls: hints, revealed truth/lie
verdicts, smell-driven belief, barriers, model + tokens + response time per step, and
a **live re-verification of every commit hash** (`verified OK` / `TAMPERED!`) plus the
mutual audit outcome and the sealed system-spec declaration (About button).

## Configuration — per-peer, total separation (config version 1.10)

Each agent has its **own complete config**: `config/<role>/game.toml` +
`config/<role>/rate_limits.json`. Nothing is hardcoded. **Signed game terms** (must
match the opponent, enforced cryptographically at negotiation) vs **private settings**
(each peer's own business):

| Key | Current | Signed term? | Meaning |
|-----|---------|:---:|---------|
| `game.group_name` | Segal-…-Team | – | my group identity (title bar, sealed log, report) |
| `game.sub_game_number` | 1 | – | which sub-game of the series this run is |
| `board.size` | **7** | ✔ | game grid N×N |
| `smell.grid_size` | **5** | ✔ | smell grid M×M |
| `smell.decay_per_step` | 0.10 | ✔ | smell decay per step |
| `smell.emit_intensity` | 0.9 | – | intensity at my smell center |
| `rules.max_steps` | 50 | ✔ | thief survives this many steps → thief wins |
| `rules.barriers_max` | 20 | ✔ | cop's barrier quota |
| `positions.thief_start` / `cop_start` | [3,3] / [5,3] | ✔ | start cells |
| `play.setting` | "New York" | ✔ | scenery vocabulary for NL hints |
| `play.step_speed_seconds` | 1.0 | – | replay pacing |
| `llm.model` | claude-opus-4-8[1m] | – | MY model — opponent may differ |
| `llm.step_deadline_seconds` | 30 | – | enforced LLM budget/step (slider initial) |
| `llm.short_prompt_threshold_seconds` | 10 | – | below this budget → compact prompt |
| `network.my_port` | 8801 / 8802 | – | MY MCP server port |
| `network.opponent_url` | http://127.0.0.1:88xx/mcp | – | the ONLY thing I know about the opponent |
| `network.turn_timeout_seconds` | 180 | – | silent opponent → technical result |
| `belief.smell_trust_weight` | 4.0 | – | my private belief tuning |
| `email.enabled` / `email.mode` | false / draft | – | report email safety switches |

Rate limits for all external calls (claude, email) live in each peer's own
`config/<role>/rate_limits.json` and are enforced by the `ApiGatekeeper`
(FIFO queue on overflow, retry on transient errors).

## Token accounting

The provider keeps a cumulative counter bumped only when a `claude -p` reply is
actually parsed; each step seals the **delta** since the previous step. Random/skipped
steps seal 0; a timed-out call whose reply lands later is charged to the step where it
arrived. The sealed `tokens_total` therefore always equals real consumption — exactly
what the book's 200k-token budget requires. The Hebrew report embeds the full
declaration under `הצהרת_מפרט_מחשב_וטוקנים`.

## Email report

At game end each peer builds the official Hebrew JSON report (game-book §8 schema:
group, sub-game number, start time, duration, verified step log, consensus SHA-256
signature) and — when `email.enabled = true` — creates a **Gmail draft** to the
lecturer via the global `gg:email` skill. Flip `email.mode = "send"` deliberately;
the default never sends anything.

## Architecture

```
CLI / Tkinter GUI (LivePeerApp, ReplayApp, PeerWindow)   ← presentation only
        │
   SimulationSdk                                         ← single business-logic entry point
        │
 PeerRuntime ── negotiate → turn loop → audit            ← one standalone agent
   ├─ peer:   turn_handler, sealing, summary, controls (pause/play/stop + live speed)
   ├─ domain: board, smell, belief, own_state, rules, crypto, negotiation, protocol,
   │          brains (deadline-enforced, short prompts, random fallback)
   ├─ infra:  ClaudeCliProvider (claude -p login, token metering),
   │          McpTransport ↔ opponent's FastMCP server, email_sender
   └─ shared: ConfigManager, ApiGatekeeper + RateLimiter, sysinfo, version
```

## Development

```powershell
uv run pytest tests/ -q                                  # full test suite
uv run pytest tests/ --cov=src --cov-report=term-missing # coverage ≥ 85%
uv run ruff check src/ tests/                            # zero violations
```

All Python files ≤ 150 code lines; TDD throughout; no secrets in source
(`.env-example` documents the deliberate absence of API keys).

## Troubleshooting

**`[WinError 10048] only one usage of each socket address ... 8801/8802`**
A previous peer process is still running and holding the port (e.g. a match that is
still waiting out its `turn_timeout_seconds`, or a window closed mid-game). The peer
now detects this at startup and refuses to start with this exact explanation. To fix:

```powershell
# who is holding the port?
Get-NetTCPConnection -LocalPort 8801 -State Listen | Select-Object OwningProcess
# stop it
Stop-Process -Id <PID>
```

Alternatively change `network.my_port` in that peer's `config/<role>/game.toml`
(and the matching `network.opponent_url` in the OTHER peer's config).

**GUI shows `ERROR - see status`** — the status label carries the full reason
(port conflict, missing Claude CLI login, unreachable opponent, bad config).

## Docs

- `docs/PLAN.md` — the authoritative build plan (distributed architecture rationale).
- Game rules: `../manus-final-project-game-book-V3.md`; worked example:
  `../5-step-game-simulation.md`.

## License & Copyright

**Copyright © 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
All rights reserved.**

This Software is licensed under a restrictive **Educational Use EULA** — see the
[LICENSE](LICENSE) file for the full, binding terms. In short:

- Use is limited to **formally enrolled students under Dr. Yoram Segal's direct
  academic instruction**, for personal educational purposes only.
- **No commercial use, no redistribution, no derivative works** outside the
  curriculum without prior explicit written consent from Dr. Yoram Segal or an
  authorized GTAI representative.
- By accessing, cloning, downloading, or using this repository you agree to be
  bound by the LICENSE terms.

**Licensing / authorization requests:** segal@gal-tech.ai · [www.gal-tech.ai](https://www.gal-tech.ai)
