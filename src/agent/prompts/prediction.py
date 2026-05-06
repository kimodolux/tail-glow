"""Prediction prompt - LLM call to predict opponent behavior.

This runs AFTER parallel analysis nodes, using empathetic reasoning:
"If I were controlling their team, what would I do?"

Uses damage calculations, speed analysis, type matchups, and effects
to make informed predictions about opponent behavior.

Outputs a probability distribution over all possible opponent actions.
"""

PREDICTION_SYSTEM_PROMPT = """You are predicting what the opponent will do in this Pokemon battle.

Think from THEIR perspective - if you were controlling their team, what would you do?

Use the damage calculations and analysis provided to reason about:
1. Can they KO your active Pokemon this turn? Check THEIR damage vs YOUR Pokemon.
2. Are they threatened? Check YOUR damage vs THEIR Pokemon - if you can KO, they may switch.
3. Who is faster? Check speed analysis - this affects whether they can safely attack.
4. Do they have a setup opportunity? If they're not threatened, they might boost.

**OUTPUT FORMAT**: For EACH option, assign a probability (0-100%) AND a brief reason.
Probabilities must sum to 100%.

MOVES:
- [Move1]: [X]% - [reason based on damage/speed/matchup]
- [Move2]: [Y]% - [reason]
...

SWITCHES:
- [Pokemon1]: [A]% - [reason why they would/wouldn't switch]
- [Pokemon2]: [B]% - [reason]
...

**IMPORTANT**: List ALL options provided with a probability and reason. Do not skip any."""


def build_prediction_prompt(
    formatted_state: str,
    opponent_options: str,
    damage_calculations: str | None = None,
    speed_analysis: str | None = None,
    type_matchups: str | None = None,
    effects_analysis: str | None = None,
    strategy_analysis: str | None = None,
) -> str:
    """Build the user prompt for opponent prediction.

    Args:
        formatted_state: Current battle state (matchup, HP, etc.)
        opponent_options: Formatted list of opponent's moves and switches
        damage_calculations: Damage calc results (our moves vs them, their moves vs us)
        speed_analysis: Speed comparison and priority info
        type_matchups: Type effectiveness analysis
        effects_analysis: Relevant item/ability/move effects
        strategy_analysis: Strategic context (battle progress, momentum, win conditions)

    Returns:
        Formatted user prompt
    """
    sections = [
        f"## Current Battle State\n{formatted_state}",
        f"## Opponent's Options\n{opponent_options}",
    ]

    # Add strategic context first (informs prediction reasoning)
    if strategy_analysis:
        sections.append(f"## Strategic Context\n{strategy_analysis}")

    # Add analysis context for informed prediction
    if damage_calculations:
        sections.append(f"## Damage Analysis\n{damage_calculations}")

    if speed_analysis:
        sections.append(f"## Speed Analysis\n{speed_analysis}")

    if type_matchups:
        sections.append(f"## Type Matchups\n{type_matchups}")

    if effects_analysis:
        sections.append(f"## Effects\n{effects_analysis}")

    sections.append(
        "---\n"
        "Put yourself in the opponent's position. Using the strategic context and analysis above, what would YOU do?\n"
        "Assign a probability AND brief reasoning to each option. Probabilities must sum to 100%."
    )

    return "\n\n".join(sections)
