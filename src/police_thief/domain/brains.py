# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Agent brains: claude -p decides message + move + truth/lie from the peer's
OWN view. Strict JSON contract; any illegal or unparseable answer falls back to
a deterministic legal policy so the autonomous loop never stalls.
"""

import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass

from police_thief.constants import FALLBACK_HINT, VERDICT_TRUTH, Direction, MoveType, Role
from police_thief.domain import prompts
from police_thief.domain.belief import BeliefGrid
from police_thief.domain.own_state import OwnGameState

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    """What the brain chose for this turn."""

    move_type: MoveType
    direction: Direction | None
    hint: str
    verdict: str
    fallback: bool = False       # heuristic policy used (LLM reply unusable)
    random_move: bool = False    # deadline missed -> random legal move
    response_seconds: float = 0.0
    prompt_text: str = ""        # the exact prompt sent to the LLM (for the log)
    reasoning: str = ""          # the model's one-line rationale (for the log)


class BrainBase:
    """Shared LLM-call / parse / deadline / fallback machinery."""

    role: Role
    prompt_builder = staticmethod(prompts.thief_prompt)

    def __init__(self, llm, rng: random.Random | None = None):
        self._llm = llm  # anything with .send(prompt) -> str (provider or stub)
        self._rng = rng or random.Random()

    def decide(self, state: OwnGameState, belief: BeliefGrid, opponent_hint: str,
               setting: str, barriers_max: int, deadline_seconds: float | None = None,
               short_threshold: float = 0.0) -> Decision:
        if deadline_seconds is not None and deadline_seconds <= 0.05:
            return self._random_move(state)  # budget ~zero: don't even ask the LLM
        short = bool(deadline_seconds) and deadline_seconds < short_threshold
        prompt = type(self).prompt_builder(state, belief, opponent_hint, setting,
                                           barriers_max, short=short)
        started = time.perf_counter()
        try:
            reply = self._ask(prompt, deadline_seconds)
            decision = self._parse(reply, state, barriers_max)
            if decision is None:  # LLM answered, but unusable -> heuristic policy
                decision = self._fallback(state, belief)
        except FutureTimeout:  # deadline ENFORCED: no answer in time -> random move
            logger.warning("%s brain missed the %ss deadline", self.role, deadline_seconds)
            decision = self._random_move(state)
        except Exception as exc:
            logger.warning("%s brain LLM failed: %s", self.role, exc)
            decision = self._fallback(state, belief)
        decision.prompt_text = prompt
        if not decision.reasoning:
            decision.reasoning = (
                "deadline missed: random legal move" if decision.random_move
                else "heuristic fallback (LLM reply unusable)" if decision.fallback
                else ""
            )
        decision.response_seconds = round(time.perf_counter() - started, 2)
        return decision

    def _ask(self, prompt: str, deadline: float | None) -> str:
        if deadline is None:
            return self._llm.send(prompt)
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            return executor.submit(self._llm.send, prompt).result(timeout=deadline)
        finally:  # abandoned call finishes in background and is discarded
            executor.shutdown(wait=False, cancel_futures=True)

    def _random_move(self, state: OwnGameState) -> Decision:
        moves = state.board.legal_moves(state.position, state.barriers)
        if not moves:
            return Decision(MoveType.HOLD, None, FALLBACK_HINT, VERDICT_TRUTH,
                            random_move=True)
        direction, _ = self._rng.choice(moves)
        return Decision(MoveType.MOVE, direction, FALLBACK_HINT, VERDICT_TRUTH,
                        random_move=True)

    def _parse(self, reply: str, state: OwnGameState, barriers_max: int) -> Decision | None:
        try:
            data = json.loads(reply)
            move_type = MoveType(data["move"]["type"])
            direction = Direction(data["move"]["dir"]) if data["move"].get("dir") else None
            hint = str(data["message"]).strip()
            verdict = str(data.get("verdict", VERDICT_TRUTH))
            reasoning = str(data.get("reasoning", "")).strip()
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return None
        if not hint or not self._is_legal(move_type, direction, state, barriers_max):
            return None
        return Decision(move_type, direction, hint, verdict, reasoning=reasoning)

    def _is_legal(self, move_type: MoveType, direction: Direction | None,
                  state: OwnGameState, barriers_max: int) -> bool:
        if move_type is MoveType.HOLD:
            return True
        if direction is None:
            return False
        if move_type is MoveType.BARRIER:
            return (
                self.role is Role.POLICE
                and state.my_barriers < barriers_max
                and state.board.step(state.position, direction, state.barriers) is not None
            )
        return state.board.step(state.position, direction, state.barriers) is not None

    def _fallback(self, state: OwnGameState, belief: BeliefGrid) -> Decision:
        moves = state.board.legal_moves(state.position, state.barriers)
        if not moves:
            return Decision(MoveType.HOLD, None, self._fallback_hint(), VERDICT_TRUTH, True)
        direction, _ = self._pick_move(moves, state, belief)
        return Decision(MoveType.MOVE, direction, self._fallback_hint(), VERDICT_TRUTH, True)

    def _pick_move(self, moves, state, belief):
        raise NotImplementedError

    def _fallback_hint(self) -> str:
        return FALLBACK_HINT


class ThiefBrain(BrainBase):
    """Evade: maximize distance from the believed cop cell, prefer unvisited."""

    role = Role.THIEF
    prompt_builder = staticmethod(prompts.thief_prompt)

    def _pick_move(self, moves, state, belief):
        threat = belief.most_likely()
        return max(
            moves,
            key=lambda m: (state.board.distance(m[1], threat), m[1] not in state.visited),
        )


class PoliceBrain(BrainBase):
    """Chase: minimize distance to the believed thief cell."""

    role = Role.POLICE
    prompt_builder = staticmethod(prompts.police_prompt)

    def _pick_move(self, moves, state, belief):
        target = belief.most_likely()
        return min(moves, key=lambda m: state.board.distance(m[1], target))
