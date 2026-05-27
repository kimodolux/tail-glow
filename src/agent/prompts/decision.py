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

**Switch Trap (stay-in is correct):**
"Their Iron Valiant outspeeds and Moonblasts our Garchomp for ~70%. Switch options: Skeledirge takes 55% from Psychic + 12% SR = 67%; Heatran takes 60% from Close Combat + 25% SR = 85%; Toxapex takes 45% Psychic + 12% SR = 57%. Every switch-in eats half its HP and gets KO'd next turn — this is a switch trap. Stay in with Garchomp: Earthquake threatens the OHKO back and forces them out or trades evenly."
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

**Otherwise, classify the matchup from the damage + speed data. You're in one of four states:**

**State A — We KO + we outspeed:**
- Attack. Pick the highest-accuracy KO move (see `% acc` in Available Moves).
- Base power doesn't matter once a KO is secured. Only pick a less accurate move if it brings a side effect you need (priority, guaranteed flinch, removing a Ground immunity, etc.).

**State B — We KO + they outspeed:**
- If we survive their hit: attack and trade.
- If we don't survive: evaluate Switch Cost (below). Sacking is acceptable if our active has no further utility.

**State C — They KO + they outspeed (the danger state):**
- Evaluate Switch Cost (below).
- If no switch is safe → consider Tera to flip the matchup, or sack to preserve a win condition. Do NOT switch into a trap.

**State D — Neither side has a KO:**
- If opponent likely switches: set up (Dragon Dance, Swords Dance, Nasty Plot), pivot (U-turn, Volt Switch), hit the predicted switch-in with super-effective coverage, or set hazards.
- Otherwise: highest expected-damage move that doesn't open a worse matchup.

**Low-confidence prediction:** play safe. Don't over-commit to a read.

## Switch Cost

Before recommending a switch, evaluate each candidate switch-in:

```
TOTAL COST = their best move into switch-in (from `their_vs_bench`)
           + Stealth Rock chip (6% / 12% / 25% by Rock weakness)
           + Spikes chip (12% / 25% per layer)
```

A switch is SAFE only if ALL hold:
- TOTAL COST < 50%, AND
- Switch-in is not 2HKO'd on the following turn, AND
- Switch-in threatens back (forces them out, sets up, or scores a KO).

If no switch-in is safe → you're in a switch trap. Stay in and trade, Tera to change the matchup, or sack — whichever preserves the most future value.

## Status Move Rules

When the effects analysis lists **Decision Rules for Your Moves**, follow them. Status moves (hazards, setup, recovery, pivots, status infliction) should be chosen when their SET IF / USE IF conditions are met — don't default to highest-damage when a status move clearly applies.

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
