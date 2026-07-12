"""Trash-talk providers: template default (free), LLM opt-in, factory resolution."""

import random
import time

from police_thief.constants import Role
from police_thief.strategy.talk_providers import resolve_trash_talk
from police_thief.strategy.trash_talk import LlmTrashTalk, TrashTalk


class Cfg:
    def __init__(self, mapping):
        self._m = mapping

    def get(self, key, default=None):
        return self._m.get(key, default)


class TestTemplate:
    def test_template_produces_hint_and_verdict_no_tokens(self):
        hint, verdict, reasoning, prompt = TrashTalk(random.Random(1)).say(
            Role.THIEF, None, None, "New York", "hi")
        assert hint                       # a canned banter line
        assert verdict in ("truth", "lie")
        assert reasoning == "" and prompt == ""   # zero tokens, no LLM prompt
        assert TrashTalk().uses_llm is False

    def test_template_hint_respects_word_cap(self):
        # A tiny cap must truncate even the shipped canned lines.
        for seed in range(30):
            hint, *_ = TrashTalk(random.Random(seed), max_words=3).say(
                Role.THIEF, None, None, "New York", "hi")
            assert len(hint.split()) <= 3

    def test_unknown_setting_uses_default_landmarks(self):
        hint, *_ = TrashTalk(random.Random(2)).say(Role.POLICE, None, None, "Atlantis", "hi")
        assert hint


class TestLlmProvider:
    def test_parses_llm_reply(self):
        reply = '{"message": "by the bridge", "verdict": "truth", "reasoning": "honest"}'
        hint, verdict, reasoning, prompt = LlmTrashTalk(lambda p, d=None, s="": reply).say(
            Role.THIEF, None, None, "London", "hi")
        assert hint == "by the bridge" and verdict == "truth" and reasoning == "honest"
        assert prompt

    def test_bad_reply_falls_back_to_template(self):
        hint, _v, reasoning, prompt = LlmTrashTalk(lambda p, d=None, s="": "garbage").say(
            Role.THIEF, None, None, "London", "hi")
        assert hint and reasoning == "" and prompt  # template hint, prompt still logged

    def test_system_prompt_carries_the_setting_and_word_limit(self):
        captured = {}

        def ask(prompt, deadline=None, system=""):
            captured["system"], captured["user"] = system, prompt
            return '{"message": "near Big Ben", "verdict": "truth"}'

        LlmTrashTalk(ask, max_words=15).say(Role.THIEF, None, None, "London", "hi")
        assert "London" in captured["system"]      # location is in the SYSTEM prompt
        assert "15" in captured["system"]           # negotiated word cap is stated
        assert "London" not in captured["user"]     # not the user turn

    def test_llm_hint_is_capped_to_max_words(self):
        long_reply = '{"message": "' + " ".join(["word"] * 40) + '", "verdict": "truth"}'
        hint, *_ = LlmTrashTalk(lambda p, d=None, s="": long_reply, max_words=5).say(
            Role.THIEF, None, None, "London", "hi")
        assert len(hint.split()) == 5   # hard cap enforced before the wire

    def test_every_n_steps_skips_the_llm(self):
        calls = []

        def ask(prompt, deadline=None, system=""):
            calls.append(1)
            return '{"message": "x", "verdict": "truth"}'

        talk = LlmTrashTalk(ask, every_n_steps=3)
        talk.say(Role.THIEF, None, None, "London", "hi")  # turn 1 -> template
        talk.say(Role.THIEF, None, None, "London", "hi")  # turn 2 -> template
        assert calls == []
        talk.say(Role.THIEF, None, None, "London", "hi")  # turn 3 -> LLM
        assert calls == [1]

    def test_deadline_miss_falls_back_to_template(self):
        def slow(prompt, deadline=None):
            time.sleep(0.5)
            return '{"message": "late", "verdict": "truth"}'

        hint, *_ = LlmTrashTalk(slow).say(Role.THIEF, None, None, "London", "hi", deadline=0.05)
        assert hint  # returned a template line within the deadline


class TestFactory:
    def test_default_is_template(self):
        assert type(resolve_trash_talk(Cfg({}), random.Random(0))) is TrashTalk

    def test_unknown_provider_is_template(self):
        talk = resolve_trash_talk(Cfg({"trash_talk.provider": "nope"}), random.Random(0))
        assert type(talk) is TrashTalk

    def test_none_config_is_template(self):
        assert type(resolve_trash_talk(None, random.Random(0))) is TrashTalk

    def test_claude_cli_reuses_the_peer_llm(self):
        class Llm:
            def send(self, prompt):
                return '{"message": "cli line", "verdict": "truth"}'

        talk = resolve_trash_talk(
            Cfg({"trash_talk.provider": "claude_cli"}), random.Random(0), Llm())
        assert isinstance(talk, LlmTrashTalk)
        hint, *_ = talk.say(Role.THIEF, None, None, "London", "hi")
        assert hint == "cli line"

    def test_claude_cli_without_llm_is_template(self):
        talk = resolve_trash_talk(
            Cfg({"trash_talk.provider": "claude_cli"}), random.Random(0), None)
        assert type(talk) is TrashTalk
