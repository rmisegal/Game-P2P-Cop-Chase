"""prompt_discussion capture: the trash-talk provider yields the hint + reasoning,
and it is sealed (audit-covered) into the step payload with state + intent (WS6)."""

from police_thief.constants import Direction, MoveType, Role
from police_thief.domain.brains import Decision
from police_thief.domain.crypto import audit_records
from police_thief.domain.own_state import OwnGameState
from police_thief.peer.sealing import sealed_step_record
from police_thief.strategy.trash_talk import LlmTrashTalk, TrashTalk


def _state():
    st = OwnGameState(Role.THIEF, (3, 3), 7, move_set=["N", "S", "E", "W", "STAY"])
    st.apply_move(MoveType.MOVE, Direction.N)
    return st


class TestReasoningCapture:
    def test_llm_trash_talk_yields_reasoning_and_prompt(self):
        reply = '{"message": "near soho", "verdict": "lie", "reasoning": "bluff north"}'
        hint, verdict, reasoning, prompt = LlmTrashTalk(lambda p, d=None: reply).say(
            Role.THIEF, None, None, "London", "hi")
        assert hint == "near soho"
        assert verdict == "lie"
        assert reasoning == "bluff north"
        assert prompt  # captured for the sealed log

    def test_template_reasoning_and_prompt_are_empty(self):
        hint, verdict, reasoning, prompt = TrashTalk().say(
            Role.THIEF, None, None, "London", "hi")
        assert hint and reasoning == "" and prompt == ""


class TestSealedPromptDiscussion:
    def test_payload_has_state_intent_and_prompt_discussion(self):
        decision = Decision(
            MoveType.MOVE, Direction.N, "near the harbor", "lie",
            prompt_text="THIEF prompt text", reasoning="head north to bluff",
        )
        rec = sealed_step_record(_state(), decision, {"model": "m", "total": 12}, 12)
        payload = rec["payload"]
        assert payload["intent"] == "lie"
        assert payload["state"].startswith("grid=7x7;self=")
        pd = payload["prompt_discussion"]
        assert pd["llm_prompt"] == "THIEF prompt text"
        assert pd["llm_reasoning"] == "head north to bluff"
        assert pd["bluff_classification"] == "lie"

    def test_sealed_record_passes_audit(self):
        decision = Decision(MoveType.HOLD, None, "somewhere", "truth",
                            prompt_text="P", reasoning="R")
        rec = sealed_step_record(_state(), decision, {"model": "m", "total": 0}, 0)
        result = audit_records([rec])
        assert result["passed"] is True
        assert result["failed_steps"] == []
