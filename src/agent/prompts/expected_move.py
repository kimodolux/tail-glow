"""Expected opponent move prompt - LLM prediction.

Predicts what the opponent will do this turn based on game state.
"""

EXPECTED_MOVE_SYSTEM_PROMPT = """You are predicting the opponent's next action in a Pokemon battle. Analyze the situation and predict what they will most likely do.

Consider these factors:
1. **Damage potential**: What's their highest damage move? Can they KO you?
2. **Speed matchup**: Do they outspeed you? If not, are they at risk of being KO'd?
3. **Type matchup**: Are they at a significant disadvantage?
4. **Switching signals**:
   - You outspeed and can KO them -> likely switch
   - You wall them (low damage, you have recovery) -> likely switch
   - They are low HP -> may switch to preserve
   - Severe type disadvantage -> may switch
5. **Status moves**: If they can't threaten a KO, they may use status

Output your predictions as a ranked list with probabilities that sum to approximately 100%.
For each prediction, include the expected damage to your Pokemon if it's an attack."""


EXPECTED_MOVE_USER_PROMPT = """Predict the opponent's next action.

## Current Situation
{battle_state}

## Their Pokemon: {their_pokemon}
- HP: {their_hp}%
- Known moves: {their_known_moves}
- Possible moves: {their_possible_moves}

## Your Pokemon: {our_pokemon}
- HP: {our_hp}%

## Damage Calculations (Their Moves vs You)
{their_damage_vs_us}

## Speed
{speed_info}

## Their Bench Pokemon
{their_bench}

Predict what they will do. Consider:
- If they can KO you, they probably will attack
- If you outspeed and KO them, they may switch
- If you wall them, they may switch
- Check their bench for better matchups

Output format:
## Predictions

1. **[Move/Switch]** (X%) - [Damage if attack, e.g., "45% damage to you"] - [Reasoning]
2. **[Move/Switch]** (Y%) - [Damage if attack] - [Reasoning]
3. **[Move/Switch]** (Z%) - [Damage if attack] - [Reasoning]

## Summary
[One sentence summary of most likely action and why]"""


def build_expected_move_prompt(
    battle_state: str,
    their_pokemon: str,
    their_hp: float,
    their_known_moves: str,
    their_possible_moves: str,
    our_pokemon: str,
    our_hp: float,
    their_damage_vs_us: str,
    speed_info: str,
    their_bench: str,
) -> str:
    """Build the user prompt for expected move prediction.

    Args:
        battle_state: Current battle state summary
        their_pokemon: Opponent's active Pokemon name
        their_hp: Opponent's current HP percentage
        their_known_moves: Moves they've revealed
        their_possible_moves: Possible moves from randbats data
        our_pokemon: Our active Pokemon name
        our_hp: Our current HP percentage
        their_damage_vs_us: Damage calculations for their moves
        speed_info: Speed comparison information
        their_bench: Information about their bench Pokemon

    Returns:
        Formatted user prompt
    """
    return EXPECTED_MOVE_USER_PROMPT.format(
        battle_state=battle_state,
        their_pokemon=their_pokemon,
        their_hp=their_hp,
        their_known_moves=their_known_moves,
        their_possible_moves=their_possible_moves,
        our_pokemon=our_pokemon,
        our_hp=our_hp,
        their_damage_vs_us=their_damage_vs_us,
        speed_info=speed_info,
        their_bench=their_bench,
    )
