"""prompt_discussion capture: reasoning parsed from the reply and sealed into the
step payload (audit-covered), plus intent/state fields (WS6)."""

from police_thief.constants import Direction, MoveType, Role
from police_thief.domain.brains import Decision, ThiefBrain
from police_thief.domain.crypto import audit_records
from police_thief.domain.own_state import OwnGameState
from police_thief.peer.sealing import sealed_step_record


def _state():
    st = OwnGameState(Role.THIEF, (3, 3), 7, move_set=["N", "S", "E", "W", "STAY"])
    st.apply_move(MoveType.MOVE, Direction.N)
    return st


class TestReasoningParse:
    def test_parse_extracts_reasoning(self):
        reply = (
            '{"message": "near times square", "move": {"type": "HOLD"}, '
            '"verdict": "lie", "reasoning": "bluff north to pull the cop"}'
        )
        decision = ThiefBrain(llm=None)._parse(reply, _state(), barriers_max=20)
        assert decision is not None
        assert decision.reasoning == "bluff north to pull the cop"
        assert decision.verdict == "lie"

    def test_missing_reasoning_defaults_empty(self):
        reply = '{"message": "near soho", "move": {"type": "HOLD"}, "verdict": "truth"}'
        decision = ThiefBrain(llm=None)._parse(reply, _state(), barriers_max=20)
        assert decision is not None
        assert decision.reasoning == ""


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
