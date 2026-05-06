"""Decision prompt - LLM Call #4 (Every turn).

Makes the final move or switch decision using the trusted opponent prediction.
Now runs AFTER prediction, allowing simpler decision logic.
"""

DECISION_SYSTEM_PROMPT = """You are a competitive Pokemon battler. Use the opponent prediction and damage calculations to choose your action.

## Decision Logic

**FIRST: Check if this is a forced switch (your Pokemon fainted).**
If your active is "None (must switch)":
- Pick the best counter to their active Pokemon
- Consider entry hazard damage
- Prefer Pokemon that threaten a KO or force them out

**If you have an active Pokemon, use the prediction:**

### High Confidence Prediction (70%+)
React directly to their predicted action:

**If they're predicted to ATTACK:**
- Check damage calculations: Will their attack KO you?
- If yes: Switch to something that resists
- If no: Can you KO them? Use KO move. Otherwise, use highest damage.

**If they're predicted to SWITCH:**
- Set up (Dragon Dance, Swords Dance, etc.) if available
- Or use strong attack to hit the switch-in
- Or set hazards if available

### Medium/Low Confidence (<70%)
Play safe - don't over-commit:
- Use highest damage move
- Avoid risky plays that lose to multiple outcomes

## Damage-Based Decisions
When uncertain, fall back to damage math:
- If you can KO them (≥100% damage) AND outspeed: Attack
- If they can KO you AND outspeed: Switch
- If neither has KO: Use highest damage move

## Output
REASONING: [1-2 sentences referencing the prediction and why]
ACTION: [move name or "Switch to Pokemon"]"""


DECISION_USER_PROMPT = """Based on this battle information, choose your action.

## Current Situation
{formatted_state}

{game_memory}

{opponent_prediction}

## Current Strategy Analysis
{strategy_analysis}

{damage_calculations}

{speed_analysis}

{type_matchups}

{effects_analysis}

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


def build_decision_prompt(
    formatted_state: str,
    damage_calculations: str | None,
    speed_analysis: str | None,
    type_matchups: str | None,
    effects_analysis: str | None,
    strategy_analysis: str | None,
    team_analysis: str | None,
    available_moves: str,
    available_switches: str,
    game_memory: str | None = None,
    opponent_prediction: str | None = None,
) -> str:
    """Build the user prompt for action decision.

    Args:
        formatted_state: Current battle state
        damage_calculations: Formatted damage calc results
        speed_analysis: Formatted speed analysis
        type_matchups: Formatted type matchup info
        effects_analysis: Formatted effects info
        strategy_analysis: LLM analysis of battle progress
        team_analysis: Team role analysis from turn 1
        available_moves: List of available moves
        available_switches: List of available switches
        game_memory: Formatted game memory (turn history, opponent patterns)
        opponent_prediction: Predicted opponent action with probabilities

    Returns:
        Formatted user prompt
    """
    return DECISION_USER_PROMPT.format(
        formatted_state=formatted_state or "No state available",
        game_memory=game_memory or "",
        opponent_prediction=opponent_prediction or "",
        damage_calculations=damage_calculations or "No damage calculations available",
        speed_analysis=speed_analysis or "No speed analysis available",
        type_matchups=type_matchups or "No type matchups available",
        effects_analysis=effects_analysis or "No effects analysis available",
        strategy_analysis=strategy_analysis or "No strategy analysis available",
        team_analysis=team_analysis or "No team analysis available",
        available_moves=available_moves or "None available",
        available_switches=available_switches or "None available",
    )
