"""Tests for the strategy seam (Phase 7): the injectable brain factory.

(a) No selector => resolve_brain returns the shipped ThiefBrain/PoliceBrain and
    default fallback behaviour is unchanged.
(b) A selector pointing at a custom subclass (defined here, referenced by dotted
    path) => resolve_brain returns it AND PeerRuntime uses it.
(c) A custom `_pick_move` override changes the chosen fallback move.
"""

from police_thief.constants import Role
from police_thief.domain.belief import BeliefGrid
from police_thief.domain.brains import BrainBase, Decision, PoliceBrain, ThiefBrain
from police_thief.domain.own_state import OwnGameState
from police_thief.peer.runtime import PeerRuntime
from police_thief.strategy import load_brain_cls, resolve_brain, resolve_brain_cls

# Dotted paths below resolve under pytest's default (prepend) import mode, where
# this file is importable as the top-level module `test_strategy`.
DOTTED_THIEF = "test_strategy:SpyThiefBrain"


class GarbageLlm:
    """Always unparseable -> the brain uses its deterministic _pick_move policy."""

    def send(self, prompt):
        return "no json here"


class SpyThiefBrain(ThiefBrain):
    """A student's custom brain: CHASES (min distance) instead of fleeing, so its
    fallback move differs from the shipped ThiefBrain's (which maximises distance)."""

    def _pick_move(self, moves, state, belief):
        threat = belief.most_likely()
        return min(moves, key=lambda m: state.board.distance(m[1], threat))


class Cfg:
    """Minimal config with the .get(dotted, default) API resolve_brain needs."""

    def __init__(self, mapping):
        self._m = mapping

    def get(self, key, default=None):
        return self._m.get(key, default)


def _state_belief():
    return (OwnGameState(role=Role.THIEF, start=(5, 5), board_size=10),
            BeliefGrid(board_size=10))


class TestResolveDefaults:
    def test_no_selector_returns_shipped_brains(self):
        cfg = Cfg({})
        assert resolve_brain_cls(cfg, Role.THIEF) is ThiefBrain
        assert resolve_brain_cls(cfg, Role.POLICE) is PoliceBrain
        assert type(resolve_brain(cfg, Role.THIEF, GarbageLlm())) is ThiefBrain
        assert type(resolve_brain(cfg, Role.POLICE, GarbageLlm())) is PoliceBrain

    def test_none_config_returns_shipped_brains(self):
        assert resolve_brain_cls(None, Role.THIEF) is ThiefBrain

    def test_default_move_behaviour_unchanged(self):
        state, belief = _state_belief()
        brain = resolve_brain(Cfg({}), Role.THIEF, GarbageLlm())
        reference = ThiefBrain(GarbageLlm())._decide_move(state, belief, 20)
        assert brain._decide_move(state, belief, 20)[1] == reference[1]


class TestResolveSelector:
    def test_selector_resolves_custom_class(self):
        cfg = Cfg({"strategy.thief_class": DOTTED_THIEF})
        assert resolve_brain_cls(cfg, Role.THIEF) is SpyThiefBrain
        assert isinstance(resolve_brain(cfg, Role.THIEF, GarbageLlm()), SpyThiefBrain)
        # the other role is untouched by a thief-only selector
        assert resolve_brain_cls(cfg, Role.POLICE) is PoliceBrain

    def test_load_brain_cls_direct(self):
        assert load_brain_cls(DOTTED_THIEF) is SpyThiefBrain

    def test_bad_selector_shapes_raise(self):
        for bad in ("no_colon_here", "mod:", ":Class", ""):
            try:
                load_brain_cls(bad)
            except ValueError:
                continue
            raise AssertionError(f"{bad!r} should have raised ValueError")

    def test_non_brain_target_raises_typeerror(self):
        try:
            load_brain_cls("test_strategy:Cfg")  # a class, but not a BrainBase
        except TypeError:
            return
        raise AssertionError("non-BrainBase target should raise TypeError")

    def test_peer_runtime_uses_injected_brain(self, config_dir):
        game = config_dir / "game.toml"
        game.write_text(
            game.read_text(encoding="utf-8")
            + f'\n[strategy]\nthief_class = "{DOTTED_THIEF}"\n',
            encoding="utf-8",
        )
        from police_thief.shared.config import ConfigManager

        cfg = ConfigManager(config_dir)
        runtime = PeerRuntime(role=Role.THIEF, config=cfg, llm=GarbageLlm(), transport=None)
        assert isinstance(runtime.brain, SpyThiefBrain)
        # a police peer with the SAME config keeps the shipped brain (no police selector)
        police = PeerRuntime(role=Role.POLICE, config=cfg, llm=GarbageLlm(), transport=None)
        assert type(police.brain) is PoliceBrain


class TestCustomPickMoveChangesMove:
    def test_override_changes_move(self):
        state, belief = _state_belief()
        default_dir = ThiefBrain(GarbageLlm())._decide_move(state, belief, 20)[1]
        custom_dir = SpyThiefBrain(GarbageLlm())._decide_move(state, belief, 20)[1]
        # min-distance policy picks a different direction than the max-distance default
        assert custom_dir != default_dir

    def test_decision_is_a_dataclass_with_the_contract(self):
        state, belief = _state_belief()
        decision = SpyThiefBrain(GarbageLlm()).decide(state, belief, "hi", "New York", 20)
        assert isinstance(decision, Decision)
        assert issubclass(SpyThiefBrain, BrainBase)
