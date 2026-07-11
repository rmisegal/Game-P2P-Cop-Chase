# Strategy seam — how to upgrade the agent's brain

This reference simulator ships a **deliberately simple** decision policy. Your
mission is to **replace it with a smarter one**. This document shows exactly
*where* and *how*, from a one-line heuristic tweak to a fully custom policy — with
**zero changes to the engine, the protocol, or the four JSON artifacts**.

Everything below lives behind one small package: `police_thief.strategy`.

```python
from police_thief.strategy import (
    BrainBase,      # the base class every brain extends
    ThiefBrain,     # shipped heuristic evader (extend this)
    PoliceBrain,    # shipped heuristic chaser (extend this)
    Decision,       # what a brain returns each turn
    resolve_brain,  # the factory PeerRuntime uses to pick your class
)
```

## Fast by default: the move is Python, the LLM is only banter

**The MOVE is chosen entirely in Python — the LLM is NEVER consulted for it.** Each
turn, `BrainBase.decide(...)` (1) picks the move with your Python policy
(`_decide_move` → `_pick_move`), then (2) generates the *trash-talk hint* with a
**trash-talk provider**. The shipped provider is a zero-token **template** (canned
Python lines), so the game runs **fast, free, and offline** by default — and the
only way to win is a better **algorithm**, not a bigger model.

That means your grade rides on the Python you write here, and a slow or missing LLM
can never stall or change your move. LLM banter is strictly optional (see
[Trash talk](#trash-talk-optional-llm-banter)).

## The move hooks you override

Override **either or both**:

### 1. `_pick_move(moves, state, belief)` — the core move policy

Given the **legal** moves for this turn, your own `state`, and your `belief` heatmap
of where the opponent probably is, return the `(direction, cell)` tuple you want to
play. This IS the move (not a fallback) — a strong `_pick_move` is the heart of a
strong agent.

- `moves` — a list of `(Direction, (row, col))` legal moves (already filtered for
  the board edges and barriers, per the negotiated `move_set`).
- `state` — your `OwnGameState`: `state.position`, `state.visited`,
  `state.barriers`, `state.board` (with `board.distance(a, b)`).
- `belief` — a `BeliefGrid`; `belief.most_likely()` returns the single cell the
  opponent is most likely on.

The shipped defaults:

```python
class ThiefBrain(BrainBase):          # evade: maximise distance, prefer unvisited
    def _pick_move(self, moves, state, belief):
        threat = belief.most_likely()
        return max(moves, key=lambda m: (state.board.distance(m[1], threat),
                                          m[1] not in state.visited))

class PoliceBrain(BrainBase):         # chase: minimise distance to the belief peak
    def _pick_move(self, moves, state, belief):
        target = belief.most_likely()
        return min(moves, key=lambda m: state.board.distance(m[1], target))
```

### 2. `_decide_move(state, belief, barriers_max)` — full move control (incl. BARRIER)

`_pick_move` returns a single step; `_decide_move` returns the whole move —
`(MoveType, Direction | None)` — so this is where you decide **BARRIER vs MOVE vs
HOLD**. The base policy just steps per `_pick_move`; the shipped `PoliceBrain`
overrides it to *occasionally* wall a cell (a basic default you should improve):

```python
class PoliceBrain(BrainBase):
    barrier_chance = 0.15   # basic default; tune or replace the whole policy
    def _decide_move(self, state, belief, barriers_max):
        moves = state.board.legal_moves(state.position, state.barriers)
        if not moves:
            return MoveType.HOLD, None
        direction, _ = self._pick_move(moves, state, belief)
        if state.my_barriers < barriers_max and self._rng.random() < self.barrier_chance:
            return MoveType.BARRIER, direction   # wall instead of stepping
        return MoveType.MOVE, direction
```

## Trash talk (optional LLM banter)

The `message`/hint each agent sends is produced by a **trash-talk provider**, chosen
in the private per-peer `[trash_talk]` config block. The MOVE is unaffected by this —
it only changes *who writes the banter*:

| `provider` | Cost / speed | Notes |
|---|---|---|
| `template` (**default**) | 0 tokens, instant, offline | Canned Python lines; ships as the default. |
| `ollama` | free, local, no RPM | A small local model via Ollama (`ollama_url`, `model`). |
| `claude_api` | ~200 tokens/call | Small Anthropic model (default `claude-haiku-4-5`); needs `anthropic` + a key/login. |
| `claude_cli` | expensive | Reuses this peer's `claude -p` — still pays the full Claude Code system-prompt overhead. |

`every_n_steps = N` calls the LLM only every Nth turn (template on the rest). Any LLM
error or deadline miss falls back to the template, so banter never stalls the game.
The hint + `verdict` (truth/lie) are still sealed and audited exactly as before —
only the *source* of the sentence changes. Write a custom template by subclassing
`police_thief.strategy.trash_talk.TrashTalk` and overriding `_template`.

## Worked example — a custom ThiefBrain

A "corner-hugging" evader that flees toward the least-visited corner instead of just
maximising raw distance:

```python
# my_team/strategy.py
from police_thief.strategy import ThiefBrain

class CornerThiefBrain(ThiefBrain):
    """Evade toward the farthest board corner, breaking ties by unvisited cells."""

    def _pick_move(self, moves, state, belief):
        threat = belief.most_likely()
        n = state.board.size - 1
        corners = [(0, 0), (0, n), (n, 0), (n, n)]
        safest = max(corners, key=lambda c: state.board.distance(c, threat))
        return min(
            moves,
            key=lambda m: (state.board.distance(m[1], safest),
                           m[1] in state.visited),
        )
```

## Plugging it in — the config selector (no code edits to the engine)

`PeerRuntime` never hard-codes the brain: it calls
`resolve_brain(config, role, llm, rng)`. The factory reads an **optional** selector
from your private `config/<role>/game.toml`:

```toml
[strategy]
thief_class  = "my_team.strategy:CornerThiefBrain"   # dotted "package.module:ClassName"
police_class = "my_team.strategy:MyPoliceBrain"
```

- Set **only the role(s) you customise** — the other falls back to the shipped brain.
- Leave the whole `[strategy]` section commented out (as it ships) to keep the
  default heuristic. With no selector, behaviour is **byte-identical** to the
  reference simulator.
- Roles alternate across a series, so a peer may need **both** a thief and a police
  class if it wants a custom policy on every sub-game.
- The target must subclass `police_thief.domain.brains.BrainBase` (in practice,
  `ThiefBrain` or `PoliceBrain`); a malformed selector or a non-brain target fails
  fast at startup (`ValueError` / `TypeError`).

Prefer to inject in code instead of via config? Subclass `PeerRuntime` and assign
`self.brain = resolve_brain_cls(config, role)(llm, rng=...)`, or simply
`self.brain = CornerThiefBrain(llm, rng=...)`.

## The `Decision` contract

Whatever route you take, every turn must yield a `Decision`:

| field         | meaning                                                             |
|---------------|--------------------------------------------------------------------|
| `move_type`   | `MOVE`, `HOLD`, or `BARRIER` (police only).                        |
| `direction`   | a `Direction` for `MOVE`/`BARRIER`; `None` for `HOLD`.            |
| `hint`        | your free natural-language message to the opponent (**may lie**). |
| `verdict`     | `"truth"` or `"lie"` — your self-declared honesty for this hint.  |
| `reasoning`   | a one-line rationale, logged for audit (**prompt_discussion**).   |

`move_type`/`direction` come from your Python policy; `hint`/`verdict`/`reasoning`
come from the trash-talk provider (template by default). If you enable an LLM
provider, its reply must parse to `{"message", "verdict", "reasoning"}` — any bad or
slow reply falls back to the template, so the loop never stalls.

## What is logged / audited

Every sealed step records the trash-talk `llm_prompt` sent (empty for the template
provider) and the `reasoning` inside a `prompt_discussion` block (plus state,
intent/verdict, tokens, response time). These are hashed into the per-step commit
chain and re-verified by the mutual post-game audit, and they surface in the emitted
`log_<game_id>_g<NN>.json` artifact. Your strategy is free to bluff in
`hint`/`verdict`, but everything is permanently on the record — design accordingly.
