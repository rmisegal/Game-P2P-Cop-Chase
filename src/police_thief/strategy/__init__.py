# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Strategy seam — the student's mission: REPLACE the decision policy.

Students extend the shipped brains and override either hook:
  * `_pick_move(moves, state, belief)` — the deterministic heuristic (fallback
    policy) that picks a legal move; and/or
  * `prompt_builder` — the text prompt sent to the LLM.
Or they write a full policy by subclassing `ThiefBrain` / `PoliceBrain`.

This package re-exports the base classes to extend (`BrainBase`, `ThiefBrain`,
`PoliceBrain`, `Decision`) and provides `resolve_brain`, the factory
`PeerRuntime` uses to pick the brain class. It honours an OPTIONAL config
selector (`strategy.thief_class` / `strategy.police_class`, a dotted
``"package.module:ClassName"``) and otherwise falls back to the shipped
heuristic brains — so with no selector the behaviour is byte-identical to the
default simulator. See `docs/STRATEGY.md` for the full guide + a worked example.
"""

import importlib
import random

from police_thief.constants import Role
from police_thief.domain.brains import BrainBase, Decision, PoliceBrain, ThiefBrain

__all__ = [
    "BrainBase", "Decision", "PoliceBrain", "ThiefBrain",
    "load_brain_cls", "resolve_brain", "resolve_brain_cls",
]

_DEFAULTS: dict[Role, type[BrainBase]] = {Role.THIEF: ThiefBrain, Role.POLICE: PoliceBrain}
_SELECTOR_KEY: dict[Role, str] = {
    Role.THIEF: "strategy.thief_class",
    Role.POLICE: "strategy.police_class",
}


def load_brain_cls(dotted: str) -> type[BrainBase]:
    """Import a brain class from a ``"package.module:ClassName"`` selector.

    Raises ValueError on a malformed selector or a missing attribute, and
    TypeError when the target is not a `BrainBase` subclass.
    """
    module_path, sep, class_name = dotted.partition(":")
    if not sep or not module_path or not class_name:
        raise ValueError(
            f"strategy selector must be 'package.module:ClassName', got {dotted!r}"
        )
    module = importlib.import_module(module_path)
    try:
        brain_cls = getattr(module, class_name)
    except AttributeError as exc:
        raise ValueError(f"{class_name!r} not found in module {module_path!r}") from exc
    if not (isinstance(brain_cls, type) and issubclass(brain_cls, BrainBase)):
        raise TypeError(f"{dotted!r} does not name a BrainBase subclass")
    return brain_cls


def resolve_brain_cls(config, role: Role) -> type[BrainBase]:
    """Return the brain class for `role`: the config selector if set, else the
    shipped default (`ThiefBrain` / `PoliceBrain`)."""
    selector = config.get(_SELECTOR_KEY[role]) if config is not None else None
    if selector:
        return load_brain_cls(str(selector))
    return _DEFAULTS[role]


def resolve_brain(config, role: Role, llm, rng: random.Random | None = None) -> BrainBase:
    """Instantiate the resolved brain for `role`.

    With no `[strategy]` selector this is exactly the shipped heuristic brain,
    preserving the default simulator's behaviour."""
    return resolve_brain_cls(config, role)(llm, rng=rng)
