# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Prompt builders for the agent brains: each prompt exposes ONLY the peer's
own view (its true state, its belief heatmap, the opponent's last NL hint).
"""

REPLY_CONTRACT = (
    'Reply with STRICT JSON only, no prose: {"message": "<free natural-language hint that '
    'MUST contain a location cue, phrased with {setting} landmarks; you may lie>", '
    '"move": {"type": "MOVE|BARRIER|HOLD", "dir": "{dirs}"}, '
    '"verdict": "truth|lie", '
    '"reasoning": "<one short sentence: why you chose this move and this hint>"}. '
    '"verdict" states whether YOUR message is honest.'
)


def _dirs(state) -> str:
    """The direction tokens legal under the agreed move set."""
    return "|".join(d.value for d in state.board.moves)


def _moves_desc(state) -> str:
    if state.board.diagonal:
        return "8-direction king moves"
    return "4-direction orthogonal moves (N/S/E/W) plus STAY (HOLD)"


def _contract(state, setting: str) -> str:
    return REPLY_CONTRACT.replace("{setting}", setting).replace("{dirs}", _dirs(state))


def _common(state, belief, opponent_hint, setting) -> str:
    likely = belief.most_likely()
    return (
        f"The chase is imagined in {setting}.\n"
        f"Board: {state.board.size}x{state.board.size}, {_moves_desc(state)}.\n"
        f"My TRUE position: {state.position} (secret - never reveal it plainly).\n"
        f"Known barriers (impassable): {sorted(state.barriers)}.\n"
        f"My belief: opponent most likely at {likely}.\n"
        f"Opponent's last message: \"{opponent_hint}\"\n"
    )


def _compact(role: str, state, belief, opponent_hint, setting) -> str:
    """Minimal prompt for tight step deadlines: state + contract, no strategy prose."""
    return (
        f"{role} agent, cop-thief chase, {state.board.size}x{state.board.size} {_moves_desc(state)}. "
        f"Me: {state.position} (secret). Barriers: {sorted(state.barriers)}. "
        f"Opponent likely at {belief.most_likely()}. "
        f'They said: "{opponent_hint[:80]}". Answer FAST.\n'
        + _contract(state, setting)
    )


def thief_prompt(state, belief, opponent_hint, setting, barriers_max, short=False) -> str:
    if short:
        return _compact("THIEF", state, belief, opponent_hint, setting)
    return (
        "You are the THIEF agent in a distributed cop-and-thief pursuit game.\n"
        + _common(state, belief, opponent_hint, setting)
        + "Survive without being caught to win; being caught loses. Evade the cop: move away "
          "from its likely position, prefer unvisited cells, and craft a deceptive or honest "
          "hint as strategy dictates. You cannot place barriers.\n"
        + _contract(state, setting)
    )


def police_prompt(state, belief, opponent_hint, setting, barriers_max, short=False) -> str:
    if short:
        return _compact("POLICE", state, belief, opponent_hint, setting)
    return (
        "You are the POLICE agent in a distributed cop-and-thief pursuit game.\n"
        + _common(state, belief, opponent_hint, setting)
        + f"I placed {state.my_barriers}/{barriers_max} barriers; BARRIER places a wall on an "
          "adjacent cell INSTEAD of moving. Detect whether the thief's message is a lie by "
          "comparing it against the smell evidence (my belief heatmap already integrates it), "
          "close the distance, and cut escape routes with barriers.\n"
        + _contract(state, setting)
    )
