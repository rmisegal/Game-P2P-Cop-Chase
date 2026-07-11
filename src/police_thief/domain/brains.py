# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Agent brains: the MOVE is chosen by a pure-Python strategy (the student's
seam) — the LLM is NEVER consulted for it. The LLM, if enabled at all, only
writes optional trash-talk banter (see ``strategy/trash_talk.py``). The shipped
banter provider is a zero-token template, so the game runs fast and free by
default and students compete on the algorithm, not on prompting a big model.

Override points for students (see ``docs/STRATEGY.md``):
  * ``_pick_move(moves, state, belief)`` — pick a legal move (the core heuristic).
  * ``_decide_move(state, belief, barriers_max)`` — full move incl. BARRIER (police).
"""

import logging
import random
import time
from dataclasses import dataclass

from police_thief.constants import Direction, MoveType, Role
from police_thief.domain.belief import BeliefGrid
from police_thief.domain.own_state import OwnGameState

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    """What the brain chose for this turn (move = Python, hint = trash talk)."""

    move_type: MoveType
    direction: Direction | None
    hint: str
    verdict: str
    fallback: bool = False       # reserved (move policy fell back to HOLD)
    random_move: bool = False    # reserved (kept for log/replay compatibility)
    response_seconds: float = 0.0
    prompt_text: str = ""        # the trash-talk prompt sent to the LLM ("" for template)
    reasoning: str = ""          # the model's one-line rationale ("" for template)


class BrainBase:
    """Decision policy. `_pick_move` / `_decide_move` is the student's seam;
    `decide` chooses the move in pure Python and never asks the LLM for it."""

    role: Role

    def __init__(self, llm=None, rng: random.Random | None = None, trash=None):
        self._llm = llm  # kept for provider=claude_cli trash talk; unused otherwise
        self._rng = rng or random.Random()
        if trash is None:  # lazy import avoids a brains<->strategy import cycle
            from police_thief.strategy.trash_talk import TrashTalk
            trash = TrashTalk(self._rng)
        self._trash = trash

    def decide(self, state: OwnGameState, belief: BeliefGrid, opponent_hint: str,
               setting: str, barriers_max: int, deadline_seconds: float | None = None,
               short_threshold: float = 0.0) -> Decision:
        # 1) MOVE — pure Python strategy. The LLM is NEVER consulted here, so the
        #    move is instant and free regardless of any LLM speed/availability.
        move_type, direction = self._decide_move(state, belief, barriers_max)
        # 2) HINT — trash talk. Template (zero tokens) by default; a small LLM only
        #    if [trash_talk] opts in. A slow/failed LLM falls back to the template.
        started = time.perf_counter()
        hint, verdict, reasoning, prompt = self._trash.say(
            self.role, state, belief, setting, opponent_hint, deadline_seconds)
        return Decision(
            move_type, direction, hint, verdict,
            fallback=(move_type is MoveType.HOLD and direction is None),
            reasoning=reasoning, prompt_text=prompt,
            response_seconds=round(time.perf_counter() - started, 2),
        )

    def _decide_move(self, state: OwnGameState, belief: BeliefGrid,
                     barriers_max: int) -> tuple[MoveType, Direction | None]:
        """Choose this turn's move. Base policy: step per `_pick_move`, else HOLD."""
        moves = state.board.legal_moves(state.position, state.barriers)
        if not moves:
            return MoveType.HOLD, None
        direction, _ = self._pick_move(moves, state, belief)
        return MoveType.MOVE, direction

    def _pick_move(self, moves, state, belief):
        raise NotImplementedError


class ThiefBrain(BrainBase):
    """Evade: maximize distance from the believed cop cell, prefer unvisited."""

    role = Role.THIEF

    def _pick_move(self, moves, state, belief):
        threat = belief.most_likely()
        return max(
            moves,
            key=lambda m: (state.board.distance(m[1], threat), m[1] not in state.visited),
        )


class PoliceBrain(BrainBase):
    """Chase: minimize distance to the believed thief cell; occasionally wall."""

    role = Role.POLICE
    barrier_chance = 0.15  # basic default barrier rate; students can improve this

    def _decide_move(self, state, belief, barriers_max):
        moves = state.board.legal_moves(state.position, state.barriers)
        if not moves:
            return MoveType.HOLD, None
        direction, _ = self._pick_move(moves, state, belief)
        # BARRIER is a police-only book mechanic. This basic default sometimes walls
        # the cell it would step onto instead of moving; students improve placement.
        if state.my_barriers < barriers_max and self._rng.random() < self.barrier_chance:
            return MoveType.BARRIER, direction
        return MoveType.MOVE, direction

    def _pick_move(self, moves, state, belief):
        target = belief.most_likely()
        return min(moves, key=lambda m: state.board.distance(m[1], target))
