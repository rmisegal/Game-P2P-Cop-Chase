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

## The two hooks you can override

A brain is asked to choose an action every turn via `BrainBase.decide(...)`, which
(a) builds a prompt, (b) asks the LLM, (c) parses/validates the reply, and (d) on
any illegal or unusable answer, **falls back to a deterministic policy**. Two clean
override points sit inside that flow — override **either or both**:

### 1. `_pick_move(moves, state, belief)` — the heuristic hook

This is the deterministic fallback policy: given the **legal** moves for this turn,
your own `state`, and your `belief` heatmap of where the opponent probably is,
return the `(direction, cell)` tuple you want to play. It runs whenever the LLM is
skipped, times out, or returns something illegal — so a strong `_pick_move` makes
your agent robust even when the model misbehaves.

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

### 2. `prompt_builder` — the LLM prompt hook

`prompt_builder` is a static callable that turns your view into the text prompt sent
to the model. Override it to give the LLM better situational framing, few-shot
examples, or a tighter reasoning contract. It **must keep the JSON reply contract**
(see below) so the parser accepts the answer; otherwise `decide` silently falls
back to `_pick_move`.

```python
from police_thief.domain import prompts

class MyThiefBrain(ThiefBrain):
    prompt_builder = staticmethod(prompts.thief_prompt)  # or your own builder
```

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

If you override `prompt_builder`, the model's reply must still parse to
`{"message", "move": {"type","dir"}, "verdict", "reasoning"}`. Illegal moves and
unparseable replies are rejected and routed to your `_pick_move` fallback — the loop
never stalls.

## What is logged / audited

Every sealed step records the exact `llm_prompt` sent and the model's `reasoning`
inside a `prompt_discussion` block (plus state, intent/verdict, tokens, response
time, and whether the move was random due to a missed deadline). These are hashed
into the per-step commit chain and re-verified by the mutual post-game audit, and
they surface in the emitted `log_<game_id>_g<NN>.json` artifact. Your strategy is
free to bluff in `hint`/`verdict`, but the prompt and reasoning behind each move are
permanently on the record — design accordingly.
