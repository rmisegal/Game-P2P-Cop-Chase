# Upgrade Plan — fit the simulator to the book + the 4 JSON files

> Source of truth for this upgrade. Granular task list: `docs/UPGRADE-4JSON-TODO.md`.

## Context
The reference simulator (`src/police_thief`) is handed to students as a working example and starting point;
their job is to **upgrade the strategy**. Today it plays **exactly one sub-game per invocation**, writes **one**
`logs/{role}_match.json`, and uses **8-direction king moves** — none of which matches the book. This upgrade
makes it fit the book and the four standardized JSON files (`declaration`, `config`, `log`, `result`), supports
**N sub-games** (shipped default **1**; the book mandates 6), stays on **localhost**, and exposes a clean
strategy seam.

Two peers run as separate processes (police / thief), each its own FastMCP server on its own port (8801/8802),
no central referee. Auth via browser-login `claude -p`.

## Decisions (confirmed)
- **All 4 artifact files stay JSON** (canonical-JSON hashing; stdlib read+write; nested + audited + emailed).
- **Movement: config-driven, default orthogonal** (4 dirs + STAY per book); king moves still available via `move_set`.
- **Config input: read shared game terms from a JSON config**; keep a small private per-peer local file.
- **Default shipped `num_games = 1`**; support N with role alternation.
- Each peer emits **its own** `declaration`/`log`/`result`; the `config` JSON is shared and signed.
- One **`game_uid`** (+ human `game_id`) agreed in the negotiation handshake, threaded through all four files.

## Already satisfied — REUSE, do not rebuild
- Symmetric scent (both peers emit `my_scent`, read opponent's) — `peer/runtime.py:55-59,155-166`.
- Barrier on an **adjacent** cell, police-only, capped — `domain/own_state.py:63-73`.
- Commit-reveal + mutual audit — `domain/crypto.py` (`CommitReveal`, `audit_records`); consensus signature — `report/report_writer.py:consensus_signature`.
- Step-0 hardware spec — `shared/sysinfo.py:collect_spec`; token accounting — `infra/llm_provider.py:_record_usage`; rate-limiter/Gatekeeper — `rate_limits.json`; negotiation/signature — `domain/negotiation.py`.

## Workstreams (summary)
- **WS1 Config** — JSON shared game terms + private per-peer local file; merge in `shared/config.py`; ship example (num_games=1, grid 7, thief [3,3], cop [0,0], scoring 20/5/5/10, tie 2, orthogonal move_set).
- **WS2 Movement** — orthogonal-by-default from `move_set`; Manhattan distance; 4-neighbour belief diffuse; STAY counts as a step.
- **WS3 Series** — N-sub-game loop in `sdk/sdk.py:run_peer`, keep servers alive, role alternation, live sub-game numbering, `game_uid`+`num_games` in signed terms.
- **WS4 Emitters** — `report/artifacts.py`: `build_declaration/config/log/result`, template schemas, `game_id`+`game_uid`+`links`, correct filenames.
- **WS5 Scoring** — `domain/scoring.py`: per-sub-game score per group, aggregate, series tie ⇒ `tie_score` each, `winner_group`.
- **WS6 prompt_discussion** — capture `llm_prompt`+`reasoning`(+`bluff_classification`) into the sealed step payload.
- **WS7 Strategy seam** — `strategy/base.py` `Strategy` protocol + default `HeuristicStrategy`; injectable brain in `PeerRuntime`; `docs/STRATEGY.md`.
- **WS8 Alignment** — email → book address; `game_uid=uuid4`; record `max_tokens_per_game`.
- **WS9 Tests/docs/verify** — unit + integration (stub, localhost), README/STRATEGY docs, regenerate `Json-examples/` from a real run.

## Critical files
`sdk/sdk.py` · `peer/runtime.py` · `peer/summary.py` · `peer/sealing.py` · `domain/brains.py` · `domain/prompts.py` ·
`domain/belief.py` · `domain/board.py` · `domain/constants.py` · `domain/smell.py` · `domain/negotiation.py` ·
`shared/config.py` · `shared/sysinfo.py` · `infra/email_sender.py` · **new:** `domain/scoring.py`, `report/artifacts.py`,
`strategy/base.py` · `config/{police,thief}/*` · `tests/**`.

## Verification (end-to-end, localhost)
1. Two terminals, `--stub`, `num_games=1` → `declaration_*.json`, `config_*_g01.json`, `log_*_g01.json`, `result_*.json` all written, one shared `game_uid`, identical `config_sha256`, audit `passed=true`.
2. `num_games=2` → role alternation, two per-sub-game logs, one aggregated `result`; force equal totals → `tie_score` applied.
3. `uv run pytest` green; `ruff` clean.
4. Each emitted file validates against the `Json-examples/` templates (keys, `links`, `game_uid`).
