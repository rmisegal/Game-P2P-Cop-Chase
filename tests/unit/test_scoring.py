"""Tests for league scoring + the book's tie rule (pure functions)."""

from police_thief.domain.scoring import aggregate, score_subgame

SCORING = {
    "capture_cop": 20,
    "capture_thief": 5,
    "survival_cop": 5,
    "survival_thief": 10,
    "tie_score": 2,
}


class TestScoreSubgame:
    def test_capture_awards_cop_and_thief(self):
        roles = {"g1": "police", "g2": "thief"}
        assert score_subgame("capture", roles, SCORING) == {"g1": 20, "g2": 5}

    def test_survival_awards_thief_more(self):
        roles = {"g1": "police", "g2": "thief"}
        assert score_subgame("survival", roles, SCORING) == {"g1": 5, "g2": 10}

    def test_roles_swapped(self):
        roles = {"g1": "thief", "g2": "police"}
        assert score_subgame("capture", roles, SCORING) == {"g1": 5, "g2": 20}

    def test_technical_loss_is_zero_zero(self):
        roles = {"g1": "police", "g2": "thief"}
        assert score_subgame("timeout", roles, SCORING) == {"g1": 0, "g2": 0}
        assert score_subgame("tamper_forfeit", roles, SCORING) == {"g1": 0, "g2": 0}


class TestAggregate:
    def test_single_subgame_winner(self):
        result = aggregate([{"g1": 20, "g2": 5}], tie_score=2)
        assert result["total_score"] == {"g1": 20, "g2": 5}
        assert result["winner_group"] == "g1"
        assert result["sub_games_won"] == {"g1": 1, "g2": 0}
        assert result["series_tie"] is False

    def test_series_sum_and_winner(self):
        result = aggregate(
            [{"g1": 20, "g2": 5}, {"g1": 5, "g2": 10}, {"g1": 20, "g2": 5}], tie_score=2
        )
        assert result["total_score"] == {"g1": 45, "g2": 20}
        assert result["winner_group"] == "g1"
        assert result["sub_games_won"] == {"g1": 2, "g2": 1}

    def test_series_tie_applies_tie_score(self):
        # g1: 20+5=25 ; g2: 5+20=25  -> tie -> each gets +tie_score
        result = aggregate([{"g1": 20, "g2": 5}, {"g1": 5, "g2": 20}], tie_score=2)
        assert result["series_tie"] is True
        assert result["winner_group"] is None
        assert result["total_score"] == {"g1": 27, "g2": 27}

    def test_tied_subgame_counted_as_tie(self):
        result = aggregate([{"g1": 0, "g2": 0}, {"g1": 20, "g2": 5}], tie_score=2)
        assert result["ties"] == 1
        assert result["sub_games_won"] == {"g1": 1, "g2": 0}
