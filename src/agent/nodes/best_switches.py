"""Best switch options node - deterministic switch ranking.

Ranks available switches based on survivability against expected opponent move
and ability to win the resulting matchup.
"""

import logging
from typing import Any, Optional

from poke_env.battle import Battle, Pokemon, SideCondition

from src.agent.state import AgentState
from src.damage_calc.calculator import MatchupResult

logger = logging.getLogger(__name__)


def best_switches_node(state: AgentState) -> dict[str, Any]:
    """Rank available switches based on survivability and matchup outcomes.

    Considers:
    - Damage taken from expected opponent move
    - Entry hazard damage (Stealth Rock, Spikes)
    - Whether the switch-in can beat the opponent (from matchup_results)

    Args:
        state: Current agent state

    Returns:
        Dict with best_switches containing ranked switches and summary
    """
    battle: Optional[Battle] = state.get("battle_object")
    if not battle:
        return {"best_switches": None}

    available_switches = battle.available_switches
    if not available_switches:
        return {"best_switches": {
            "switches": [],
            "summary": "No switches available.",
        }}

    try:
        expected_action = state.get("expected_opponent_action", {})
        matchup_results = state.get("matchup_results", {})
        damage_calc_raw = state.get("damage_calc_raw", {})

        # Get expected move damage
        expected_move = _get_expected_move(expected_action)

        # Rank switches
        ranked_switches = _rank_switches(
            battle=battle,
            switches=available_switches,
            expected_move=expected_move,
            matchup_results=matchup_results,
            damage_calc_raw=damage_calc_raw,
        )

        # Build summary
        summary = _build_summary(ranked_switches)

        result = {
            "switches": ranked_switches,
            "summary": summary,
        }

        return {"best_switches": result}

    except Exception as e:
        logger.error(f"Best switches calculation failed: {e}", exc_info=True)
        return {"best_switches": None}


def _get_expected_move(expected_action: Optional[dict]) -> Optional[str]:
    """Extract the most likely move from expected opponent action."""
    if not expected_action:
        return None

    predictions = expected_action.get("predictions", [])
    if not predictions:
        return None

    # Get highest probability move (not switch)
    for pred in predictions:
        if pred.get("action_type") == "move":
            return pred.get("action")

    return None


def _rank_switches(
    battle: Battle,
    switches: list[Pokemon],
    expected_move: Optional[str],
    matchup_results: dict,
    damage_calc_raw: dict[str, Any],
) -> list[dict[str, Any]]:
    """Rank available switches by effectiveness."""
    their_pokemon = battle.opponent_active_pokemon
    their_vs_bench: list[MatchupResult] = damage_calc_raw.get("their_vs_bench", [])

    switch_scores = []

    for pokemon in switches:
        score_data = _calculate_switch_score(
            pokemon=pokemon,
            battle=battle,
            their_pokemon=their_pokemon,
            expected_move=expected_move,
            matchup_results=matchup_results,
            their_vs_bench=their_vs_bench,
        )
        switch_scores.append(score_data)

    # Sort by score descending
    switch_scores.sort(key=lambda x: x["score"], reverse=True)

    # Build ranked result
    ranked = []
    for i, data in enumerate(switch_scores, 1):
        ranked.append({
            "pokemon": data["pokemon"],
            "rank": i,
            "damage_on_switch": data["damage_on_switch"],
            "survives": data["survives"],
            "matchup_result": data["matchup_result"],
            "reasoning": data["reasoning"],
            "score": data["score"],
        })

    return ranked


def _calculate_switch_score(
    pokemon: Pokemon,
    battle: Battle,
    their_pokemon: Optional[Pokemon],
    expected_move: Optional[str],
    matchup_results: dict,
    their_vs_bench: list[MatchupResult],
) -> dict[str, Any]:
    """Calculate score and data for a single switch option."""
    species = pokemon.species
    current_hp = pokemon.current_hp_fraction * 100

    # Calculate entry hazard damage
    hazard_damage = _calculate_hazard_damage(pokemon, battle)

    # Calculate damage from expected move
    move_damage = 0.0
    move_damage_str = "Unknown"

    if their_pokemon and their_vs_bench:
        for matchup in their_vs_bench:
            if matchup.defender == species:
                # Find damage from expected move or highest damage move
                if expected_move:
                    for result in matchup.results:
                        if result.move == expected_move.lower().replace(" ", ""):
                            move_damage = (result.min_percent + result.max_percent) / 2
                            move_damage_str = f"{result.min_percent:.0f}-{result.max_percent:.0f}%"
                            break

                # Fallback to highest damage if expected move not found
                if move_damage == 0 and matchup.results:
                    worst = max(matchup.results, key=lambda r: r.max_percent)
                    move_damage = (worst.min_percent + worst.max_percent) / 2
                    move_damage_str = f"{worst.min_percent:.0f}-{worst.max_percent:.0f}% (worst case)"
                break

    # Total damage on switch-in
    total_damage = hazard_damage + move_damage
    survives = (current_hp - total_damage) > 0
    hp_after = max(0, current_hp - total_damage)

    # Build damage string
    if hazard_damage > 0:
        damage_on_switch = f"{hazard_damage:.0f}% hazards + {move_damage_str} attack = {total_damage:.0f}% total"
    else:
        damage_on_switch = f"{move_damage_str} from attack"

    # Check matchup result
    matchup_key = (species, their_pokemon.species) if their_pokemon else None
    matchup_data = matchup_results.get(matchup_key, {}) if matchup_key else {}

    if matchup_data:
        outcome = matchup_data.get("outcome", "unknown")
        if outcome == "win":
            matchup_result = f"Wins with {matchup_data.get('our_remaining_hp_percent', '?')}% HP"
        elif outcome == "lose":
            matchup_result = f"Loses (they have {matchup_data.get('their_remaining_hp_percent', '?')}% left)"
        else:
            matchup_result = "Draw/Trade"
    else:
        matchup_result = "Matchup unknown"

    # Calculate score
    score = 0.0

    if survives:
        score += 100  # Base score for surviving

        # Bonus for HP remaining after switch
        score += hp_after

        # Bonus for winning matchup
        if matchup_data.get("outcome") == "win":
            score += 50
            # Extra bonus for HP remaining
            score += matchup_data.get("our_remaining_hp_percent", 0) / 2
        elif matchup_data.get("outcome") == "draw":
            score += 25
    else:
        score = -100  # Heavily penalize if doesn't survive

    # Generate reasoning
    reasoning = _generate_switch_reasoning(
        pokemon=pokemon,
        survives=survives,
        hp_after=hp_after,
        hazard_damage=hazard_damage,
        matchup_outcome=matchup_data.get("outcome"),
    )

    return {
        "pokemon": species,
        "damage_on_switch": damage_on_switch,
        "survives": survives,
        "matchup_result": matchup_result,
        "reasoning": reasoning,
        "score": score,
    }


def _calculate_hazard_damage(pokemon: Pokemon, battle: Battle) -> float:
    """Calculate entry hazard damage for a Pokemon."""
    damage = 0.0
    side_conditions = battle.side_conditions

    if not side_conditions:
        return 0.0

    pokemon_types = [t.name.lower() for t in pokemon.types if t]

    # Stealth Rock - based on type effectiveness to Rock
    if SideCondition.STEALTH_ROCK in side_conditions:
        rock_effectiveness = _get_rock_effectiveness(pokemon_types)
        sr_damage = 12.5 * rock_effectiveness  # Base 12.5%, modified by effectiveness
        damage += sr_damage

    # Spikes - 3 layers max
    spikes_layers = side_conditions.get(SideCondition.SPIKES, 0)
    if spikes_layers > 0 and "flying" not in pokemon_types:
        # Check for Levitate or similar
        if pokemon.ability and "levitate" in pokemon.ability.lower():
            pass  # Immune
        else:
            spikes_damage = {1: 12.5, 2: 16.67, 3: 25.0}.get(spikes_layers, 0)
            damage += spikes_damage

    # Toxic Spikes - not direct damage but worth noting
    # Sticky Web - speed drop, not damage

    return damage


def _get_rock_effectiveness(types: list[str]) -> float:
    """Get Rock-type effectiveness multiplier."""
    # Type chart for Rock attacking
    weak_to_rock = {"fire", "ice", "flying", "bug"}
    resists_rock = {"fighting", "ground", "steel"}

    multiplier = 1.0
    for t in types:
        t_lower = t.lower()
        if t_lower in weak_to_rock:
            multiplier *= 2.0
        elif t_lower in resists_rock:
            multiplier *= 0.5

    return multiplier


def _generate_switch_reasoning(
    pokemon: Pokemon,
    survives: bool,
    hp_after: float,
    hazard_damage: float,
    matchup_outcome: Optional[str],
) -> str:
    """Generate human-readable reasoning for a switch option."""
    reasons = []

    if not survives:
        reasons.append("Dies on switch-in")
        return "; ".join(reasons)

    if hp_after >= 70:
        reasons.append(f"Healthy after switch ({hp_after:.0f}% HP)")
    elif hp_after >= 40:
        reasons.append(f"Moderate HP after switch ({hp_after:.0f}%)")
    else:
        reasons.append(f"Low HP after switch ({hp_after:.0f}%)")

    if hazard_damage > 20:
        reasons.append("Heavy hazard damage")
    elif hazard_damage > 0:
        reasons.append("Takes hazard damage")

    if matchup_outcome == "win":
        reasons.append("Wins the 1v1")
    elif matchup_outcome == "lose":
        reasons.append("Loses the 1v1")
    elif matchup_outcome == "draw":
        reasons.append("Trades evenly")

    return "; ".join(reasons) if reasons else "Standard option"


def _build_summary(ranked_switches: list[dict[str, Any]]) -> str:
    """Build a natural language summary of switch options."""
    if not ranked_switches:
        return "No switches available."

    # Filter to surviving switches
    viable = [s for s in ranked_switches if s.get("survives", False)]

    if not viable:
        return "Warning: All switches die on entry. Consider staying in if possible."

    lines = []

    # Best switch
    best = viable[0]
    best_name = best["pokemon"].replace("-", " ").title()

    matchup = best.get("matchup_result", "")
    if "Wins" in matchup:
        lines.append(f"{best_name} is your best switch - survives entry and {matchup.lower()}.")
    else:
        lines.append(f"{best_name} survives entry ({best['damage_on_switch']}).")

    # Note other good options
    if len(viable) > 1:
        second = viable[1]
        second_name = second["pokemon"].replace("-", " ").title()
        if "Wins" in second.get("matchup_result", ""):
            lines.append(f"{second_name} also wins the matchup.")

    # Warning for bad switches
    non_viable = [s for s in ranked_switches if not s.get("survives", False)]
    if non_viable:
        dead_names = ", ".join(s["pokemon"].replace("-", " ").title() for s in non_viable[:2])
        lines.append(f"Avoid: {dead_names} (dies on switch).")

    return " ".join(lines)


def format_best_switches(best_switches: Optional[dict[str, Any]]) -> str:
    """Format best switches for the decision node.

    Args:
        best_switches: The best_switches dict from state

    Returns:
        Formatted string for LLM consumption
    """
    if not best_switches:
        return "## Best Switches\nNo switch analysis available."

    lines = ["## Best Switches"]
    lines.append("")

    # Summary first
    summary = best_switches.get("summary", "")
    if summary:
        lines.append(f"**Summary:** {summary}")
        lines.append("")

    # Ranked switches
    switches = best_switches.get("switches", [])
    if switches:
        lines.append("**Ranked Options:**")
        for switch_data in switches:
            name = switch_data["pokemon"].replace("-", " ").title()
            rank = switch_data.get("rank", "?")
            damage = switch_data.get("damage_on_switch", "?")
            survives = switch_data.get("survives", False)
            matchup = switch_data.get("matchup_result", "?")
            reasoning = switch_data.get("reasoning", "")

            survive_str = "Survives" if survives else "DIES"
            lines.append(f"{rank}. **{name}** ({survive_str})")
            lines.append(f"   Entry damage: {damage}")
            lines.append(f"   Matchup: {matchup}")
            if reasoning:
                lines.append(f"   {reasoning}")
            lines.append("")

    return "\n".join(lines)
