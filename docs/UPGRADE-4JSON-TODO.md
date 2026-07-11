# Upgrade TODO — fit the simulator to the book + 4 JSON files

Plan: `docs/UPGRADE-4JSON-PLAN.md`. Templates: `../Json-examples/{1..4}-*.json`.
Rules: TDD (write/adjust the test first, then implement to green). End each phase with a **gate** (`uv run pytest`
+ `ruff check`) and a commit. Keep files small. Do not break the existing single-game flow until WS3 replaces it.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done.

---

## Phase 0 — Baseline & scaffolding
- [ ] Run `uv run pytest` and `ruff check` on a clean checkout; record the green baseline.
- [ ] Read the 4 templates in `../Json-examples/`; copy their exact key sets into a fixtures module `tests/fixtures/json_schemas.py` (expected top-level + nested keys per file) for schema assertions.
- [ ] Create a feature branch `feat/4json-nsubgames`.
- [ ] **Gate + commit.**

## Phase 1 (WS1) — Config: shared JSON terms + private local file
- [ ] Test `tests/unit/test_config.py`: loading a shared `config_*.json` (template-2 schema) exposes `grid_size, thief_start, cop_start, move_set, max_barriers, max_moves, survival_threshold, scoring.*, pheromones.*, network_and_league.num_games, rate_limiter.*`.
- [ ] Test: merge precedence — private local file (port/url/llm/gui/seed/belief/email/**group identity**) overlays; shared terms cannot be overridden locally.
- [ ] Test: mismatched shared config between peers is rejected by the signature check (extend `test_negotiation.py`).
- [ ] Implement in `shared/config.py`: JSON game-config loader + merge with the per-peer local file; internal accessor mapping (`board.size↔grid_size`, `smell.*↔pheromones.*`, `rules.max_steps↔survival_threshold`, new `max_moves`). Keep `.get(dotted, default)` API stable.
- [ ] Add **group identity** keys to the private local file: `group_id, group_name, members[], repos{cop,thief}, mcp_servers{cop,thief}`.
- [ ] Author example configs: shared `config/shared/game.json` (num_games=1, grid_size=7, thief_start=[3,3], cop_start=[0,0], move_set=["N","S","E","W","STAY"], max_barriers=14, max_moves=35, survival_threshold=35, scoring 20/5/5/10, tie_score=2, pheromones 0.9/0.10/5, rate_limiter from current `rate_limits.json`); trim `config/{police,thief}/game.toml` to local-only + identity.
- [ ] **Gate + commit.**

## Phase 2 (WS2) — Orthogonal movement (config-driven)
- [ ] Test `tests/unit/test_board.py`: with `move_set=4+STAY`, `legal_moves` yields only N/S/E/W(+HOLD); no diagonals; barriers still block; STAY legal.
- [ ] Test: with `move_set=king`, 8 dirs still available (back-compat).
- [ ] Test `tests/unit/test_brains.py`: cop minimizes **Manhattan** to `belief.most_likely()`, thief maximizes it with unvisited tiebreak, under orthogonal moves.
- [ ] Test `tests/unit/test_belief.py`: `diffuse` spreads to the 4-neighbour (von Neumann) set under orthogonal.
- [ ] Implement: `domain/constants.py` DELTAS derived from `move_set`; `domain/board.py` step/legal_moves honor it; `domain/brains.py` `_manhattan` (select metric by move_set); `domain/belief.py` diffuse neighbourhood by move_set; `domain/smell.py` falloff metric by move_set. Confirm STAY increments the survival-step counter.
- [ ] **Gate + commit.**

## Phase 3 (WS5) — Scoring + tie (pure, test-first; no I/O)
- [ ] Test `tests/unit/test_scoring.py`: `(capture, cop=g1)`→ g1 `capture_cop`, g2 `capture_thief`; `(survival, thief=g2)`→ scores; technical loss → 0/0; aggregate over sub-games; equal totals ⇒ both get `tie_score`; `winner_group` correct.
- [ ] Implement `domain/scoring.py`: `score_subgame(result, role_of_group, cfg)`, `aggregate(subgame_scores, cfg)` → `{total_score, sub_games_won, ties, winner_group, series_tie}`.
- [ ] **Gate + commit.**

## Phase 4 (WS6) — prompt_discussion capture
- [ ] Test `tests/unit/test_sdk.py`/`test_brains.py`: a decided step exposes `llm_prompt` (sent text) and `llm_reasoning`; stub path fills sensible defaults.
- [ ] Test `tests/unit/test_crypto.py` (via sealing): sealed step payload includes `state, intent, prompt_discussion{llm_prompt,llm_reasoning,bluff_classification}` and still round-trips through `audit_records`.
- [ ] Implement: `domain/prompts.py` `REPLY_CONTRACT` adds a short `reasoning`; `domain/brains.py:decide` returns/retains prompt text + reasoning in the `Decision`; `peer/sealing.py:sealed_step_record` adds `state, intent`(=verdict), `prompt_discussion`.
- [ ] **Gate + commit.**

## Phase 5 (WS4) — The four JSON emitters
- [ ] Test `tests/unit/test_report_writer.py` (or new `test_artifacts.py`): each builder returns a dict whose keys equal the template fixtures (Phase 0), carrying `game_id`, `game_uid`, and a `links` block.
- [ ] Test: `config_sha256` == sha256 of the canonical config; `signature` via existing `consensus_signature`; `hardware_spec` uses `gpu_model` (renamed from `gpu_type`) and only the 6 book fields.
- [ ] Implement `report/artifacts.py`:
  - [ ] `build_declaration(match_ctx, own_identity, opponent_identity, spec, ...)`
  - [ ] `build_config_artifact(terms, game_id, game_uid, sub_game_number)` (+ `config_name`, `config_sha256`)
  - [ ] `build_log(summary, game_id, game_uid, group_id)` (adds `ended_at`, `state`, `intent`, `prompt_discussion`)
  - [ ] `build_result(all_summaries, scores, game_id, game_uid, groups)` (`sub_games[]` + `final_result` + `groups[]` + `mutual_agreement`)
- [ ] Filename helpers: `declaration_<game_id>.json`, `config_<game_id>_g<NN>.json`, `log_<game_id>_g<NN>.json`, `result_<game_id>.json`.
- [ ] **Gate + commit.**

## Phase 6 (WS3 + WS8) — N-sub-game series, role alternation, identity/uid exchange
- [ ] Test `tests/integration/test_mcp_match.py`: `num_games=1` stub match on localhost emits all 4 files with a shared `game_uid`; audit passes.
- [ ] Test: `num_games=2` alternates roles, writes two per-sub-game logs + one aggregated `result`; forced-equal path applies `tie_score`.
- [ ] Test `test_negotiation.py`: signed terms now include `game_id`, `game_uid`, `num_games`; peers exchange group identity (id/name/members/repos/mcp).
- [ ] Implement:
  - [ ] `domain/negotiation.py` + `peer/sealing.py:terms_from_config`: add `game_id`, `game_uid` (`uuid4`, proposed by initiator), `num_games`; exchange opponent identity.
  - [ ] `peer/runtime.py`: support per-sub-game rebuild (`reset(role, sub_game_number)` or re-instantiate); do NOT tear down the MCP server between sub-games; replace static `sub_game_number` reads with the live index (`peer/summary.py:62`, `peer/sealing.py:26`, `report/report_writer.py:65`, `gui/*`).
  - [ ] `sdk/sdk.py:run_peer`: `for i in range(num_games)` loop, alternate role, collect summaries, then emit `declaration` (once), per-sub-game `config`+`log`, and final `result`; wire `EmailSender` to send the `result` JSON.
  - [ ] `infra/email_sender.py` + config: recipient → `rmisegal+uoh26finalgame@gmail.com`.
- [ ] **Gate + commit.**

## Phase 7 (WS7) — Strategy seam for students
- [ ] Test `tests/unit/test_brains.py`: a custom `Strategy` injected into `PeerRuntime` is used for move selection; default `HeuristicStrategy` reproduces current heuristic behaviour.
- [ ] Implement `strategy/base.py`: `Strategy` protocol `decide(state, belief, opponent_hint, board, cfg)->Decision`; `HeuristicStrategy` (Manhattan) as default; small registry/factory selectable via config `[strategy] class = "module:Class"`.
- [ ] `peer/runtime.py:__init__`: accept an injected strategy/brain instead of the hard-coded `brain_cls` (default = registry lookup).
- [ ] **Gate + commit.**

## Phase 8 (WS9) — Docs, regeneration, final verify
- [ ] `docs/STRATEGY.md`: exactly where/how a student plugs in a smarter policy (the `Strategy.decide` seam + config selector), with a worked example.
- [ ] Update `README.md`: multi-game (`num_games`), the 4 JSON files, the strategy seam, localhost run steps.
- [ ] Run a real `num_games=1` stub match; copy the 4 emitted files over `../Json-examples/` (keep them the canonical examples the book references); confirm keys still match the book's Appendix-F variable names.
- [ ] Final end-to-end: two terminals `--stub` (num_games=1 then 2); assert files, shared `game_uid`, identical `config_sha256`, audit passed, tie path.
- [ ] `uv run pytest` (all green) + `ruff check` + coverage not regressed.
- [ ] **Gate + final commit + tag `v-4json-upgrade`.**

---

## Cross-cutting acceptance (Definition of Done)
- One invocation with `num_games=1` produces exactly the 4 JSON files, all sharing one `game_uid`, filenames derived from `game_id`.
- `num_games=6` runs a full series with alternating roles and a correct aggregated `result` (scores, winner, tie).
- Movement is orthogonal by default and matches the book; king moves remain opt-in via `move_set`.
- Every emitted file validates 1:1 against the `Json-examples/` templates and the Appendix-F variable names.
- Students have a documented `Strategy` seam; the shipped default is the basic heuristic they will replace.
