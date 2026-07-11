# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""League scoring: turn a sub-game outcome into per-group points, and aggregate a
whole series into a final result with the book's tie rule (Appendix F).

Pure functions only — no I/O — so they are trivially testable and reused by the
result-JSON emitter.
"""

from police_thief.constants import Role

# Result strings produced by the runtime; anything not capture/survival scores 0/0.
CAPTURE = "capture"
SURVIVAL = "survival"


def score_subgame(result: str, roles: dict[str, str], scoring: dict) -> dict[str, int]:
    """Points each group earns in one sub-game.

    `roles` maps group_id -> role played this sub-game ("police"/"thief").
    Capture: cop-group gets `capture_cop`, thief-group `capture_thief`.
    Survival: cop-group gets `survival_cop`, thief-group `survival_thief`.
    Any other outcome (timeout / tamper_forfeit / stopped) is a technical loss: 0/0.
    """
    out = dict.fromkeys(roles, 0)
    if result == CAPTURE:
        for group, role in roles.items():
            out[group] = scoring["capture_cop"] if role == Role.POLICE else scoring["capture_thief"]
    elif result == SURVIVAL:
        for group, role in roles.items():
            out[group] = scoring["survival_cop"] if role == Role.POLICE else scoring["survival_thief"]
    return out


def aggregate(subgame_scores: list[dict[str, int]], tie_score: int) -> dict:
    """Sum sub-game scores into a series result.

    Returns total_score per group, sub_games_won per group, count of tied sub-games,
    the winner_group (None on a series tie), and series_tie. On a two-group series
    tie the book's tie rule grants each group `tie_score`.
    """
    groups = sorted({group for scores in subgame_scores for group in scores})
    total = {group: sum(scores.get(group, 0) for scores in subgame_scores) for group in groups}

    sub_games_won = dict.fromkeys(groups, 0)
    ties = 0
    for scores in subgame_scores:
        if not scores:
            continue
        top = max(scores.values())
        winners = [group for group, value in scores.items() if value == top]
        if len(winners) == 1:
            sub_games_won[winners[0]] += 1
        else:
            ties += 1

    if len(groups) == 2 and total[groups[0]] == total[groups[1]]:
        for group in groups:
            total[group] += tie_score
        return {
            "total_score": total,
            "sub_games_won": sub_games_won,
            "ties": ties,
            "winner_group": None,
            "series_tie": True,
        }

    winner = max(total, key=total.get) if total else None
    return {
        "total_score": total,
        "sub_games_won": sub_games_won,
        "ties": ties,
        "winner_group": winner,
        "series_tie": False,
    }
