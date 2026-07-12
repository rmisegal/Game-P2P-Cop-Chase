# Research Report & Performance Analysis
## Resource Consumption, Rate Limits, and Architectural Survivability of the Autonomous "Police vs. Thief" AI Agents

> **Scope & ground-truth rule.** This report benchmarks the LLM resource profile of the
> **v2.0 simulator in this repository** (`Game-P2P-Cop-Chase`). The **code is the ground
> truth** for all performance behaviour. The guidelines PDF (`docs/police_thief_p2p.pdf`)
> has **not yet been updated** to the v2.0 performance architecture; where the book and the
> code disagree (most importantly the fallback behaviour), **the code wins** and the book is
> used only as theoretical scaffolding, explicitly flagged.
>
> **Provider-limit numbers are 2026 snapshots**, largely community/secondary-sourced because
> OpenAI, Anthropic, and xAI no longer publish fixed message caps (they route live numbers to
> in-product dashboards). Treat every message-per-window figure as *approximate*. Sources and
> caveats are listed at the end.

---

## 1. Executive summary

The v2.0 refactor decouples the **game move** (pure Python, 0 tokens, instant) from the
**LLM**, which is now used *only* for optional "trash-talk" banter. The shipped default
provider is a **zero-token template**, so the reference game makes **0 LLM calls and consumes
0 tokens**. Rate limits only become a concern when a student *opts in* to an LLM banter
provider.

Under the book-mandated worst case — **6 sub-games × 35 moves, an LLM call every 3rd move ⇒
~70 calls per agent spread over ~140 minutes, 150–250 tokens per call** — the engineering
bottleneck is no longer token volume (TPM) but **request/message-count caps per rolling
window (RPM / "messages per N hours")**.

| Question | Answer (grounded in this repo's code) |
|---|---|
| Does the reduced load complete a full game on **free** accounts? | **Yes for Ollama (native, unlimited local) and Gemini's free API.** For Claude/ChatGPT/Grok free chat tiers the quota is exhausted mid-game, **but the game still finishes** because the Python fallback takes over the banter. |
| Are **$20 premium** subscriptions stable under 70 calls / 140 min? | **ChatGPT Plus and Gemini AI Pro: fully stable** (load ≪ cap). **SuperGrok: stable.** **Claude Pro: borderline** — all 70 calls land in a single 5-hour window; see §6. |
| Does the **fallback** change the outcome vs. the old architecture? | **Decisively.** Old design (book): any block/timeout/quota **freezes the game loop → failed match**. New design (code): **graceful degradation** — the move continues in Python, only the banter goes robotic, and **every match completes**. |

---

## 2. The workload, measured from the code (not assumed)

All figures below are read directly from the repository, not from the book.

### 2.1 Game dimensions — `config/<role>/game.json`

| Parameter | Value | Source |
|---|---|---|
| Board | 7×7 | `board_and_agents.grid_size` |
| Move set | `["N","S","E","W","STAY"]` (4-orthogonal + stay) | `movement_and_barriers.move_set` |
| Moves per sub-game per side | **35** | `movement_and_barriers.max_moves` / `survival_threshold` |
| Sub-games in a series | `num_games` = **1 shipped default**; **book mandates 6** | `network_and_league.num_games` (+ README) |
| Token budget per series | **200,000** | `network_and_league.token_budget_per_series` |
| Local gatekeeper | 30 RPM, 2 concurrent, queue depth 100, retry 5 s ×3 | `rate_limiter_gatekeeper` / `rate_limits.json` |

### 2.2 The LLM is opt-in — `strategy/trash_talk.py`, `strategy/talk_providers.py`

The move is chosen by `BrainBase.decide()` **step 1** in pure Python (`_decide_move` →
`_pick_move`); the LLM is **never** consulted for it. **Step 2** produces the banter via a
*trash-talk provider*:

| Provider | Native in code? | Token cost / call | Auth & limit surface |
|---|---|---|---|
| `template` **(default)** | ✅ native | **0** (canned Python) | none — offline, instant |
| `ollama` | ✅ native | 0 API tokens (local) | none — local HTTP, no RPM |
| `claude_api` | ✅ native | **~150–250** (`max_tokens=200`, Haiku default) | Anthropic **API** RPM/TPM, pay-per-token |
| `claude_cli` | ✅ native | **heavy** (full Claude Code system-prompt overhead) | Claude **subscription** 5-h/weekly message window (browser login) |
| ChatGPT / Gemini / Grok | ⚠️ **add-on** (~10-line `ask()`, see `_ollama_asker`/`_claude_api_asker` pattern) | model-dependent | that provider's chat/API caps |

> **Add-on note.** The `[trash_talk]` seam accepts any callable `ask(prompt, deadline)`.
> Claude (CLI + API) and Ollama ship natively; ChatGPT, Gemini, and Grok each require a
> small custom asker. They are analysed below because the assignment requires all four, but
> their integration is a student add-on, not shipped code.

### 2.3 Derived load (book-mandated 6-game series, `every_n_steps = 3`)

`LlmTrashTalk.say()` increments a per-sub-game turn counter and calls the model only when
`_turn % every_n_steps == 0`; every other turn uses the free template.

- Moves per agent per series: 6 × 35 = **210**
- LLM calls per agent: ⌊35/3⌋ × 6 = **66** (design ceiling **~70**)
- Duration at ~20 s/move: **~140 min (2.33 h)**
- Call rate: **~0.5 calls/min = 1 call every ~2 min** per agent
- Token consumption (`claude_api` Haiku): ~70 × ~250 ≈ **17.5 k tokens/series** — **8.75 %**
  of the 200 k budget
- Token consumption (`claude_cli`): full Claude Code overhead per call ⇒ order **10³–10⁴×**
  higher; the README records the old LLM-per-move design at **~2.4 M tokens/sub-game** — this
  is why `claude_cli` is labelled "expensive" and blows the 200 k budget.

> **Shipped-default reality check.** With `num_games = 1` and `template` banter (as shipped),
> a full run is **~11 calls at most and 0 tokens**. The 70-call profile is the *opt-in,
> 6-game, LLM-banter* worst case.

### 2.4 The window arithmetic that decides everything

140 min < 180 min (3 h) < 240 min (4 h) < 300 min (5 h). **The entire series' ~70 calls fall
inside a single 3-, 4-, and 5-hour rolling window.** You therefore cannot rely on a mid-game
window reset — the relevant comparison is **70 calls vs. the per-window cap, directly**. Peak
RPM (0.5) is trivial against every provider's RPM ceiling (15–500).

---

## 3. Free-tier analysis (per provider)

*Free chat-tier message caps are 2026 approximations; see caveats. The load is 0.5 RPM / ~70
calls / all within one 5-h window / 150–250 tokens.*

### Google Gemini — the only robust free path *if wired as an add-on*
- **Free API (AI Studio):** Gemini 2.5 Flash-Lite ≈ **15 RPM, ~1,000 RPD, 250 k TPM**
  (post-Dec-2025 quota cut). The game's 0.5 RPM / ~70 RPD / <200 TPM sits far below every
  limit → **completes cleanly, no fallback triggered**.
- **Caveats:** enabling **Cloud Billing on the project cancels the free tier** (usage bills
  from token 1); free-tier traffic **may be used to train Google's models**.
- **Verdict:** ✅ full game on free — but requires a custom asker (add-on).

### OpenAI ChatGPT — completes via OpenAI's *own* soft fallback
- **Free chat:** flagship (GPT-5.x "Instant") ≈ **~10 messages / 5 h**, then **auto-downgrades
  to a "mini" model** rather than hard-blocking. So the game **finishes** — the first ~10
  calls are flagship, the remaining ~85 % are mini → **quality dip, no Python fallback needed**.
- **Free API:** ≈ 3 RPM, no starter credits since mid-2025 → effectively unusable.
- **Web/CLI risk:** driving the *chat UI* invites Cloudflare/CAPTCHA blocks — exactly the
  failure the Python fallback absorbs.
- **Verdict:** ✅ completes (degraded text) — add-on; prefer API over UI automation.

### Anthropic Claude — hard block, saved by *this repo's* fallback
- **Free chat (Sonnet 5 / Haiku 4.5):** ≈ **15–40 messages / 5 h**, **no automatic model
  fallback** — quota exhaustion returns a **hard error**.
- Driven via `claude_cli` on a free login, the agent exhausts its quota **mid-game (≈ minute
  30–80)**. There is no provider-side rescue.
- **What saves the game is architectural, not the provider:** `LlmTrashTalk.say()` catches the
  error and returns the template line; the move was already chosen in Python. The match
  **completes with robotic banter** for its remainder.
- **Verdict:** ⚠️ provider quota fails mid-game; ✅ **game still completes** via Python fallback.

### xAI Grok — earliest to fail, same graceful landing
- **Free chat:** ≈ **10–12 messages / 2 h** (Grok-3), no internal fallback → exhausted in
  **< 20 min**.
- **Verdict:** ⚠️ provider fails early; ✅ game completes via Python fallback (robotic banter
  for most of the match).

### Ollama — the native, genuinely-unlimited free path (recommended)
- Local model over `http://localhost:11434`. **No RPM, no message cap, no tokens, no network
  dependency.** Shipped natively (`_ollama_asker`).
- **Verdict:** ✅✅ the correct free choice for this simulator — full LLM banter, every game,
  zero external limits.

**Free-tier summary**

| Provider (free) | Approx. 2026 cap | Provider's own fallback | Finishes *without* the Python fallback? |
|---|---|---|---|
| **Ollama** (native) | none (local) | n/a | ✅ Yes — no limits at all |
| **Gemini** free API (add-on) | 15 RPM / 1,000 RPD / 250 k TPM | n/a (limit ≫ load) | ✅ Yes |
| **ChatGPT** free chat (add-on) | ~10 msg / 5 h | ✅ auto → mini model | ✅ Yes (degraded text ~30 min in) |
| **Claude** free chat (native cli) | ~15–40 msg / 5 h | ❌ none (hard error) | ❌ No — Python fallback carries the rest |
| **Grok** free chat (add-on) | ~10–12 msg / 2 h | ❌ none | ❌ No — Python fallback carries the rest |

---

## 4. Premium-tier analysis ($20–$30)

*The premium tiers exist to keep the banter *intelligent* for the whole match (never touching
the Python fallback). Load unchanged: ~70 calls, 0.5 RPM, all within one window.*

### ChatGPT Plus ($20)
- ≈ **160 messages / rolling 3 h** on the flagship; overflow soft-falls to mini (not a hard
  error). In any 3-h window the game emits ≤ ~35 calls → **< 45 % of cap**.
- API Tier-1 ≈ 500 RPM — 0.5 RPM is nothing.
- **Stability: very high. Fallback probability: ~0.**

### Gemini AI Pro / Advanced ($20)
- Consumer tier moved to **compute-based** metering in May 2026 (~4× the free limits); API
  Tier-1 ≈ **150–300 RPM**.
- 0.5 RPM / 250-token payload is invisible to Google's infrastructure, even on flagship models.
- **Stability: absolute. Fallback probability: ~0.**

### SuperGrok ($30)
- ≈ **100–150 messages / rolling 4 h**. 70 calls fit comfortably.
- Anti-burst throttling only triggers on bursts (> ~30 RPM) or **> 3 rate-limit breaches / 24 h**;
  the game's **~20–40 s spacing between an agent's calls never bursts**.
- **Stability: high. Fallback probability: very low.**

### Claude Pro ($20) — the one genuine risk; see §6 for the deep dive
- Legacy ≈ **45 messages / 5 h**; **doubled (~90 / 5 h) in May 2026**, plus a **new weekly
  "active-hours" cap**; **no fallback model** (hard error on exhaustion).
- Because all ~70 calls fall in **one 5-h window**, the comparison is **70 vs. the 5-h cap
  directly** — over the legacy 45, under the doubled ~90.
- **Stability: medium (borderline). Fallback probability: moderate, and higher via `claude_cli`
  than `claude_api`.**

**Premium-tier summary**

| Provider (premium) | Approx. 2026 cap | Load as % of window cap | Stability | Fallback risk |
|---|---|---|---|---|
| ChatGPT Plus ($20) | ~160 / 3 h (+mini overflow) | ≤ ~45 % (per 3 h) | Very high | ~0 |
| Gemini AI Pro ($20) | compute-based / 150–300 RPM API | ≪ 1 % | Absolute | ~0 |
| SuperGrok ($30) | ~100–150 / 4 h | ~50–70 % (per 4 h) | High | Very low |
| **Claude Pro ($20)** | ~45 (legacy) → ~90 / 5 h + weekly | **~78 % of ~90, or 155 % of 45** | **Medium** | **Moderate (cli ≫ api)** |

---

## 5. Local defence in depth — the gatekeeper (code)

Before any request leaves the machine, `shared/gatekeeper.py` + `shared/rate_limiter.py`
enforce the `rate_limits.json` policy (`claude`: 30 RPM, 2 concurrent, retry 5 s ×3, queue
depth 100, 300 s timeout). `RateLimiter.acquire()` is a sliding-window token bucket that
**queues** rather than errors when full.

At **0.5 RPM demand vs. 30 RPM local budget**, the gatekeeper never queues and never trips.
Its value is *insurance*: if a strategy ever bursts (e.g., `every_n_steps = 1` plus fast
pacing), it smooths traffic locally instead of letting the remote provider issue a 429. This
mirrors the book's **Token Bucket / Quota Manager / DOS Detector** guard stack (theory
scaffolding) — but the concrete limits are the code's, not the book's.

---

## 6. Claude Pro deep dive — 70 messages in 140 minutes vs. the 5-hour window

This is the assignment's central question, and the only premium case that is genuinely tight.

**The window trap.** 140 min < 300 min, so **all ~70 calls fall inside a single 5-hour
window** — there is no reset to lean on. The comparison is blunt:

- vs. **legacy ~45 / 5 h** → **exceeds by ~55 %** → would hard-block around call ~45 (≈ minute
  90) and spend the last ~50 min on the Python fallback.
- vs. **doubled ~90 / 5 h** (May 2026) → **fits, but at ~78 %** — tight, and the **weekly
  active-hours cap** plus demand-driven variance can still bite across repeated series.

**Why the code's design is the best case for Claude's length-based metering.** Anthropic's
quota burns faster with longer *conversations* (the whole growing context is reprocessed each
turn). This repo **never accumulates a conversation**:
- `claude_api` (`talk_providers._claude_api_asker`) builds a **fresh** `messages=[{user:
  prompt}]` with `max_tokens=200` on **every** call — stateless, ~250 tokens, Haiku.
- `claude_cli` pipes a **fresh temp file** per call — no chat history carried forward.

So each call is a genuine "short message," which is the friendliest possible shape for the
5-hour cap.

**But `claude_cli` is the trap within the trap.** The CLI path authenticates via the browser
**subscription login** (the code deliberately strips `ANTHROPIC_API_KEY` in
`infra/llm_provider.py` `STRIP_KEYS`), so its calls **count against the Pro 5-hour / weekly
message window** *and* each call pays the **full Claude Code system-prompt overhead**. Seventy
heavy `claude_cli` calls in one 5-hour window is exactly what pushes a Pro subscriber over the
edge. `claude_api` (Haiku, 200 tokens, stateless) is far lighter and comfortably survives.

**And if it trips anyway, nothing breaks.** Claude returns a hard error → `LlmTrashTalk.say()`
`except Exception` → template line; the move was already made in Python; `PeerRuntime`'s
`# never stall the loop` guarantees the turn advances. The match **completes**, degrading only
the banter.

**Recommendation for a Claude-based agent on Pro:** use **`claude_api` with Haiku** (or
**Ollama**), **not `claude_cli`**. Keep `every_n_steps ≥ 3`. Expect to *finish every game*
regardless, with occasional robotic banter if the 5-hour cap is reached late in a series.

---

## 7. The fallback mechanism — and how it redefines "game success"

### 7.1 Old architecture (as the **book** still describes it — flagged as outdated)
Decision-making was coupled to the LLM: the model was asked to pick the move, loading the full
game context (~35 k tokens/step). A CAPTCHA (Cloudflare), a `Rate limit reached`, or a
`Timeout` **froze the game loop**. A match interrupted at move 40 was a **failed match**.
Completion depended on cloud availability.

> **Code-vs-book contradiction (code wins).** The v2.0 code does **not** work this way. This
> section documents the *old* behaviour only to contrast it; the book has not yet been updated.

### 7.2 New architecture (the **code** — ground truth)
Three code facts remove the cloud from the critical path:
1. **Move first, in Python.** `BrainBase.decide()` computes `_decide_move(...)` before any
   banter — the LLM is never on the move path.
2. **Bounded, self-healing banter.** `LlmTrashTalk._ask_bounded()` enforces
   `step_deadline_seconds` (30 s) via a worker thread; **any** exception — timeout, 429,
   parse error, network, CAPTCHA — is caught and replaced by the template
   (`FALLBACK_HINT` / canned line). `every_n_steps` already uses the template on non-Nth turns.
3. **The loop cannot stall.** In `peer/runtime.py`, a rejected move falls back to `HOLD` with
   the comment `# never stall the loop`.

### 7.3 The redefinition
Success is no longer binary "did the cloud stay up." It is **"did the match reach a valid,
audited result,"** which is now **guaranteed**. The LLM affects only *entertainment quality*:

| | Old (book) | New (code) |
|---|---|---|
| LLM blocked/timed-out/quota-hit | **Game freezes → failed match** | Move continues in Python; banter → template |
| Claude 5-h cap reached mid-series | Wait 5 h to play the next move | Graceful degradation; series finishes on time |
| CAPTCHA on web/CLI | System halt | Absorbed by `except Exception` → template |
| Definition of "success" | Cloud-availability-dependent | **Every match completes**; only banter degrades |

This is decisive precisely for **Claude** (no provider-side fallback) and for any **web/CLI**
path exposed to Cloudflare — the two cases where the provider offers no safety net, the
architecture supplies one.

---

## 8. Recommendations

1. **Grading/dev runs:** keep the shipped **`template`** default — 0 tokens, 0 limits, fully
   deterministic; students compete on the Python algorithm.
2. **Want LLM banter for free & reliable:** use **`ollama`** (native, local, unlimited). This
   is the single best answer to "can a full game run for free?" — yes, always.
3. **Cloud banter on a budget:** **Gemini free API** (add-on) or **ChatGPT Plus** are the most
   headroom-rich. **Avoid `claude_cli` on Claude Pro** for a 6-game series; prefer
   **`claude_api` (Haiku)**.
4. **Keep `every_n_steps ≥ 3`** and rely on the local gatekeeper (30 RPM) as burst insurance.
5. **Trust the fallback:** no provider choice can *fail the game*; the worst case is robotic
   banter. Choose providers for banter *quality*, not for game *survival*.

---

## 9. Methodology & caveats

- **Code figures** (workload, token cost, fallback path, gatekeeper limits) are read directly
  from this repository (`config/*/game.json`, `strategy/trash_talk.py`,
  `strategy/talk_providers.py`, `infra/llm_provider.py`, `shared/rate_limiter.py`,
  `peer/runtime.py`, `sdk/series.py`) and are authoritative.
- **Provider-limit figures are 2026 snapshots**, mostly community/secondary-sourced. OpenAI,
  Anthropic, and xAI do not publish fixed message caps; only Google's Gemini API limits are
  officially documented (and now shown in the AI Studio dashboard). Notable moving targets:
  Gemini's Dec-2025 free-quota cut (~50–80 %); Anthropic's May-2026 doubling of the 5-hour Pro
  limit and the new weekly "active-hours" cap; ChatGPT/Grok caps that flex with server load.
  Treat all message-per-window numbers as approximate.
- **The "45 messages / 5 hours" Claude figure** is a community-origin number, never a current
  official constant, and is outdated on the low side for 2026 (post-doubling ≈ 90). The
  *mechanism* (length/model affects usage; hard error, no fallback) is officially acknowledged.
- **Book (PDF) content** — Dec-POMDP, belief/scent stigmergy, and the Gatekeeper guard stack
  (Token Bucket, Quota Manager, DOS Detector, Deadline Tracker, 429 back-off) — is used as
  theoretical scaffolding only. Where it contradicts the v2.0 code (notably the LLM-coupled
  game-halt), **the code is authoritative** and the book is pending update.

*Prepared against `Game-P2P-Cop-Chase` code v2.0.1 (2026-07-12). Provider limits current as of
mid-2026.*
