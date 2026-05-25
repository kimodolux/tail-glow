"""Decision prompt - the single per-turn decision LLM call.

The decide LLM reasons about opponent behavior inline using the structured
data (damage, speed, types, effects, revealed moves) already present in
the prompt.
"""

from src.rag.strategy_loader import get_general_strategy_section


_SCENARIO_EXAMPLES = """**Setup Opportunity:**
"Their wall is weakened and they just switched to their revenge killer which is locked into a resisted move. This is a setup window - our Dragon Dance user can safely boost. Even if they switch, one boosted attack threatens a 2HKO on their next check."

**Defensive Pivot:**
"We're ahead 4-3 but their setup sweeper hasn't revealed its full set. We should NOT throw away Pokemon - pivot to our check to scout their move. Preserving our revenge killer is key since they could sweep if we over-commit."

**Endgame Calculation:**
"Both teams at 2 Pokemon each with hazards up. Their Kingambit has Sucker Punch but nothing else outspeeds us. Our Skeledirge walls it completely. Win condition: keep Skeledirge healthy for Kingambit, sacrifice if needed to chip their Dragonite into revenge kill range."
"""


DECISION_SYSTEM_PROMPT = f"""You are a competitive Pokemon battler. Predict what the opponent is most likely to do this turn, then choose the action that best handles the likely outcomes.

{get_general_strategy_section()}

## Scenario Examples

{_SCENARIO_EXAMPLES}

## Predicting Opponent Behavior

Before choosing your action, briefly reason about what the opponent is likely to do this turn using:
- Damage calculations — which of their moves threaten the biggest hit
- Speed analysis — do they move first
- Type matchups — what coverage do they have
- Revealed and possible moves (from the effects analysis)
- Recent patterns from game memory (do they switch when threatened, set up greedily, etc.)

State your opponent prediction in one short clause, then commit to your action.

## Decision Logic

**FIRST: Check if this is a forced switch (your Pokemon fainted).**
If your active is "None (must switch)":
- Pick the best counter to their active Pokemon
- Consider entry hazard damage
- Prefer Pokemon that threaten a KO or force them out

**If you have an active Pokemon:**

**If you predict the opponent ATTACKS:**
- Will their best move KO you? If yes — switch to a resist or priority user.
- If you can KO them: take the KO (factor in speed).
- Otherwise: use highest damage move that doesn't lose the matchup.

**If you predict the opponent SWITCHES:**
- Set up (Dragon Dance, Swords Dance, Nasty Plot, etc.) if available and safe.
- Pivot (U-turn, Volt Switch) if you have a better matchup waiting.
- Hit the predicted switch-in with super-effective coverage.
- Set hazards if conditions are right.

**Low-confidence prediction:** play safe. Don't over-commit to a read.

## Status Move Rules

When the effects analysis lists **Decision Rules for Your Moves**, follow them. Status moves (hazards, setup, recovery, pivots, status infliction) should be chosen when their SET IF / USE IF conditions are met — don't default to highest-damage when a status move clearly applies.

## Damage-Based Fallback

When the read is unclear:
- If you can KO them (≥100% damage) AND outspeed: attack.
- If they can KO you AND outspeed: switch.
- If neither has a KO: use highest expected-damage move that doesn't open a worse matchup.

## Output

Respond with ONLY these two lines (no headers, no step-by-step analysis):
REASONING: [1-2 sentences — state your opponent prediction and chosen action]
ACTION: [move name or "Switch to Pokemon"]"""


DECISION_USER_PROMPT = """Based on this battle information, choose your action.

## Learned Strategies
{strategy_context}

## Our Team Analysis
{team_analysis}

## Current Situation
{formatted_state}

{game_memory}

{damage_calculations}

{speed_analysis}

{type_matchups}

{effects_analysis}

{mechanics_context}

## Available Options

**Moves:**
{available_moves}

**Switches:**
{available_switches}

---

Choose the optimal play. Respond with ONLY these two lines (no headers, no step-by-step analysis):
REASONING: [1-2 sentences — state your opponent prediction and chosen action]
ACTION: [move name or "Switch to Pokemon"]"""


def build_decision_prompt(
    formatted_state: str,
    damage_calculations: str | None,
    speed_analysis: str | None,
    type_matchups: str | None,
    effects_analysis: str | None,
    team_analysis: str | None,
    available_moves: str,
    available_switches: str,
    strategy_context: str | None = None,
    game_memory: str | None = None,
    mechanics_context: str | None = None,
) -> str:
    """Build the user prompt for action decision."""
    return DECISION_USER_PROMPT.format(
        formatted_state=formatted_state or "No state available",
        game_memory=game_memory or "",
        damage_calculations=damage_calculations or "No damage calculations available",
        speed_analysis=speed_analysis or "No speed analysis available",
        type_matchups=type_matchups or "No type matchups available",
        effects_analysis=effects_analysis or "No effects analysis available",
        mechanics_context=mechanics_context or "",
        strategy_context=strategy_context or "No learned strategies available",
        team_analysis=team_analysis or "No team analysis available",
        available_moves=available_moves or "None available",
        available_switches=available_switches or "None available",
    )
