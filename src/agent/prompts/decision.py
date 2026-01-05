"""Decision prompt - LLM Call (Every turn).

Makes the final move or switch decision based on pre-analyzed summaries.
"""

DECISION_SYSTEM_PROMPT = """You are a competitive Pokemon battler. Choose your action based on the pre-analyzed battle information.

## Decision Guidelines

**FIRST: Check if this is a forced switch (your Pokemon fainted).**
If your active Pokemon is "None (must switch)" or no moves are available:
- You MUST switch - pick from the Best Switches analysis
- Prioritize switches that survive entry AND win the matchup

**If you have an active Pokemon, consider:**

1. **Expected Opponent Action**: What are they likely to do? Adjust accordingly.
2. **Best Moves**: Which move is optimal given the situation?
3. **Best Switches**: If staying in is bad, which switch is safest?
4. **Speed**: Do you move first or second?
5. **Battle Context**: What does the overall strategy say?

## Decision Logic

- If you can KO them and survive: use the KO move
- If they KO you first and you can't do anything useful: switch
- If you trade KOs: usually acceptable, use the KO move
- If neither KOs: use the highest damage move or setup/utility
- Avoid unnecessary switches - only switch when it improves your position

## Output Format

Your response must contain ONLY these two lines:
REASONING: [concise reasoning, < 280 characters]
ACTION: [exact move name or "Switch to Pokemon"]

Do NOT output analysis steps or headers. Only REASONING and ACTION."""


DECISION_USER_PROMPT = """Choose your action based on this pre-analyzed battle information.

## Current Situation
{formatted_state}

## Speed
{speed_summary}

## Expected Opponent Action
{expected_opponent_summary}

## Your Best Moves
{best_moves_summary}

{best_moves_list}

## Your Best Switches
{best_switches_summary}

{best_switches_list}

## Battle Context
{battle_context}

## Team Strategy
{battle_strategy}

## Available Options

**Moves:**
{available_moves}

**Switches:**
{available_switches}

---

Choose the optimal play. Respond with ONLY these two lines:
REASONING: [1-2 sentence explanation]
ACTION: [move name or "Switch to Pokemon"]"""


def build_decision_prompt(
    formatted_state: str,
    speed_summary: str,
    expected_opponent_summary: str,
    best_moves_summary: str,
    best_moves_list: str,
    best_switches_summary: str,
    best_switches_list: str,
    battle_context: str,
    battle_strategy: str,
    available_moves: str,
    available_switches: str,
) -> str:
    """Build the user prompt for action decision.

    Args:
        formatted_state: Current battle state
        speed_summary: Speed comparison summary
        expected_opponent_summary: What opponent is likely to do
        best_moves_summary: Summary of best move options
        best_moves_list: Ranked list of moves
        best_switches_summary: Summary of best switch options
        best_switches_list: Ranked list of switches
        battle_context: Battle memory analysis
        battle_strategy: Initial strategy from turn 1
        available_moves: List of available moves
        available_switches: List of available switches

    Returns:
        Formatted user prompt
    """
    return DECISION_USER_PROMPT.format(
        formatted_state=formatted_state or "No state available",
        speed_summary=speed_summary or "Speed unknown",
        expected_opponent_summary=expected_opponent_summary or "Unable to predict opponent action",
        best_moves_summary=best_moves_summary or "No move analysis available",
        best_moves_list=best_moves_list or "",
        best_switches_summary=best_switches_summary or "No switch analysis available",
        best_switches_list=best_switches_list or "",
        battle_context=battle_context or "No battle history",
        battle_strategy=battle_strategy or "No strategy defined",
        available_moves=available_moves or "None available",
        available_switches=available_switches or "None available",
    )


# Keep legacy function for backward compatibility
def build_decision_prompt_legacy(
    formatted_state: str,
    damage_calculations: str | None,
    speed_analysis: str | None,
    type_matchups: str | None,
    effects_analysis: str | None,
    strategy_context: str | None,
    team_analysis: str | None,
    available_moves: str,
    available_switches: str,
) -> str:
    """Legacy prompt builder - used before the refactor."""
    legacy_template = """Based on this battle information, choose your action.

## Current Situation
{formatted_state}

{damage_calculations}

{speed_analysis}

{type_matchups}

{effects_analysis}

{strategy_context}

## Our Team Analysis
{team_analysis}

## Available Options

**Moves:**
{available_moves}

**Switches:**
{available_switches}

---

Choose the optimal play. Respond with ONLY these two lines (no headers, no step-by-step analysis):
REASONING: [1-2 sentence explanation]
ACTION: [move name or "Switch to Pokemon"]"""

    return legacy_template.format(
        formatted_state=formatted_state or "No state available",
        damage_calculations=damage_calculations or "No damage calculations available",
        speed_analysis=speed_analysis or "No speed analysis available",
        type_matchups=type_matchups or "No type matchups available",
        effects_analysis=effects_analysis or "No effects analysis available",
        strategy_context=strategy_context or "No strategy notes available",
        team_analysis=team_analysis or "No team analysis available",
        available_moves=available_moves or "None available",
        available_switches=available_switches or "None available",
    )
