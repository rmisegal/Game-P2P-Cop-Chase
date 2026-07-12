# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Trash-talk providers: the natural-language hint each agent sends WITH its move.

The MOVE is always chosen by the Python strategy (``domain/brains.py``); this
module only produces the *banter*. The DEFAULT provider is ``template`` — canned
Python strings, ZERO tokens, instant, offline — so the shipped game runs fast and
free and students compete on the algorithm, not on prompting a big model. LLM
banter (``claude_cli`` / ``claude_api`` / ``ollama``) is opt-in via the
``[trash_talk]`` config block. See ``docs/STRATEGY.md``.
"""

import json
import logging
import random
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from police_thief.constants import VERDICT_LIE, VERDICT_TRUTH, Role

logger = logging.getLogger(__name__)

# Landmark vocabulary keyed by the negotiated `setting`; unknown settings use the
# generic fallback so a template line always has a location cue to name.
LANDMARKS: dict[str, list[str]] = {
    "New York": ["Times Square", "Central Park", "the Brooklyn Bridge",
                 "Wall Street", "Harlem", "the East Village"],
    "London": ["Big Ben", "Tower Bridge", "Camden", "Soho", "the Thames"],
    "Paris": ["the Eiffel Tower", "Montmartre", "the Louvre", "the Left Bank"],
}
_DEFAULT_LANDMARKS = ["downtown", "the old market", "the harbor", "the north gate"]

_THIEF_LINES = [
    "Catch me if you can - I'm slipping past {landmark}!",
    "Still one step ahead, near {landmark}.",
    "You'll never pin me down around {landmark}.",
    "Too slow, officer - {landmark} is mine.",
]
_POLICE_LINES = [
    "I'm closing in around {landmark}.",
    "Nowhere left to run past {landmark}.",
    "Corner by corner - starting at {landmark}.",
    "I can see your trail near {landmark}.",
]


class TrashTalk:
    """Template provider (the shipped default): pick and fill a canned line.
    No LLM, no tokens, no network. Returns (hint, verdict, reasoning, prompt)."""

    every_n_steps = 1
    uses_llm = False

    def __init__(self, rng: random.Random | None = None, max_words: int = 15):
        self._rng = rng or random.Random()
        self._turn = 0
        self.max_words = max(1, int(max_words))  # agreed hard cap on hint length

    def _cap(self, hint: str) -> str:
        """Enforce the negotiated word limit on any hint before it goes on the wire."""
        words = hint.split()
        return hint if len(words) <= self.max_words else " ".join(words[:self.max_words])

    def say(self, role, state, belief, setting, opponent_hint, deadline=None):
        hint, verdict = self._template(role, setting)
        return self._cap(hint), verdict, "", ""  # (hint, verdict, reasoning, prompt)

    def _template(self, role: Role, setting: str) -> tuple[str, str]:
        landmark = self._rng.choice(LANDMARKS.get(setting, _DEFAULT_LANDMARKS))
        lines = _THIEF_LINES if role is Role.THIEF else _POLICE_LINES
        hint = self._rng.choice(lines).format(landmark=landmark)
        # A template line may bluff: the thief lies ~40% of the time (names a place
        # it is NOT). The commit-reveal verdict is sealed and later audited.
        lying = role is Role.THIEF and self._rng.random() < 0.4
        return hint, (VERDICT_LIE if lying else VERDICT_TRUTH)


class LlmTrashTalk(TrashTalk):
    """LLM provider: ask a SMALL model for one taunt line + verdict. Calls the
    model only every ``every_n_steps`` turns; on any error or deadline miss it
    falls back to the free template, so a slow model never stalls the game."""

    uses_llm = True

    def __init__(self, ask, rng=None, every_n_steps=1, model="", max_words=15):
        super().__init__(rng, max_words)
        self._ask = ask  # ask(prompt, deadline, system) -> raw model reply (JSON string)
        self.every_n_steps = max(1, int(every_n_steps or 1))
        self._model = model

    def say(self, role, state, belief, setting, opponent_hint, deadline=None):
        self._turn += 1
        if self._turn % self.every_n_steps != 0:  # free, template-only step
            hint, verdict = self._template(role, setting)
            return self._cap(hint), verdict, "", ""
        system, user = self._system(setting), self._user(role, opponent_hint)
        logged = f"[system]\n{system}\n\n[user]\n{user}"  # full context, sealed for audit
        try:
            data = json.loads(_extract_json(self._ask_bounded(user, deadline, system)))
            hint = str(data["message"]).strip()
            if hint:
                verdict = str(data.get("verdict", VERDICT_TRUTH))
                return self._cap(hint), verdict, str(data.get("reasoning", "")).strip(), logged
        except Exception as exc:  # any failure => safe template fallback
            logger.warning("trash-talk LLM failed (%s); using template", exc)
        hint, verdict = self._template(role, setting)
        return self._cap(hint), verdict, "", logged  # prompt still logged even on fallback

    def _ask_bounded(self, prompt: str, deadline, system: str):
        if not deadline:
            return self._ask(prompt, deadline, system)
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            return executor.submit(self._ask, prompt, deadline,
                                   system).result(timeout=deadline)
        except FutureTimeout as exc:
            raise TimeoutError(f"trash-talk exceeded {deadline}s deadline") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _system(self, setting: str) -> str:
        """System prompt: pins the agreed real-world map area AND the negotiated word
        limit, so the model taunts with a landmark from THIS game's `world.map_area`
        and never exceeds `world.hint_max_words`."""
        area = setting or "an unnamed city"
        return (
            f"You are a witty agent in a cop-and-thief chase set in {area}. Every "
            f"taunt you write MUST name a real {area} landmark and use no more than "
            f"{self.max_words} words. You MAY lie about where you actually are. "
            'Answer with STRICT JSON only: {"message": "<taunt>", "verdict": '
            '"truth|lie", "reasoning": "<why, one clause>"}'
        )

    @staticmethod
    def _user(role: Role, opponent_hint: str) -> str:
        who = "THIEF" if role is Role.THIEF else "COP"
        return f'You are the {who}. The opponent just said: "{opponent_hint}". Reply now.'


def _extract_json(text: str) -> str:
    """Pull the JSON object out of a model reply (tolerates ``` fences / prose)."""
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if 0 <= start < end else text
