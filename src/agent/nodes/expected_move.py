"""Expected opponent move node - LLM prediction.

Predicts what the opponent will do this turn based on damage calcs and game state.
"""

import logging
import re
from typing import Any, Optional

from poke_env.battle import Battle

from src.agent.state import AgentState
from src.agent.prompts.expected_move import (
    EXPECTED_MOVE_SYSTEM_PROMPT,
    build_expected_move_prompt,
)
from src.llm import get_llm_provider

logger = logging.getLogger(__name__)


def expected_move_node(state: AgentState) -> dict[str, Any]:
    """Predict the opponent's most likely action this turn.

    Uses damage calculations, speed data, and game context to predict
    whether the opponent will attack (and with what move) or switch.

    Args:
        state: Current agent state

    Returns:
        Dict with expected_opponent_action containing predictions and summary
    """
    battle: Optional[Battle] = state.get("battle_object")
    if not battle or not battle.opponent_active_pokemon:
        return {"expected_opponent_action": None}

    try:
        # Gather context for prediction
        context = _build_prediction_context(state)

        # Call LLM for prediction
        llm = get_llm_provider()
        user_prompt = build_expected_move_prompt(**context)
        username = state.get("username")

        response = llm.generate(
            EXPECTED_MOVE_SYSTEM_PROMPT,
            user_prompt,
            user=username,
        )

        # Parse the response
        predictions = _parse_predictions(response)
        summary = _extract_summary(response)

        result = {
            "predictions": predictions,
            "summary": summary,
            "raw_response": response,
        }

        logger.info(f"Expected move prediction: {summary}")
        return {"expected_opponent_action": result}

    except Exception as e:
        logger.error(f"Expected move prediction failed: {e}", exc_info=True)
        return {"expected_opponent_action": None}


def _build_prediction_context(state: AgentState) -> dict[str, Any]:
    """Build the context dict for the prediction prompt."""
    battle: Battle = state["battle_object"]
    opponent_sets = state.get("opponent_sets", {})
    damage_calc_raw = state.get("damage_calc_raw", {})
    speed_calc_raw = state.get("speed_calc_raw", {})

    their_pokemon = battle.opponent_active_pokemon
    our_pokemon = battle.active_pokemon

    # Their known moves
    if their_pokemon.moves:
        known_moves = ", ".join(
            m.replace("-", " ").title() for m in their_pokemon.moves.keys()
        )
    else:
        known_moves = "None revealed"

    # Their possible moves from randbats
    species_key = their_pokemon.species.lower().replace(" ", "").replace("-", "")
    if species_key in opponent_sets:
        possible = opponent_sets[species_key].get("possible_moves", [])
        # Filter out already known moves
        known_set = set(their_pokemon.moves.keys()) if their_pokemon.moves else set()
        unknown = [m for m in possible if m not in known_set][:6]  # Limit to 6
        possible_moves = ", ".join(m.replace("-", " ").title() for m in unknown)
    else:
        possible_moves = "Unknown"

    # Their damage vs us
    their_vs_us = damage_calc_raw.get("their_vs_us")
    if their_vs_us and their_vs_us.results:
        damage_lines = []
        for r in sorted(their_vs_us.results, key=lambda x: -x.max_percent)[:5]:
            est = " (estimated)" if r.is_estimated else ""
            ko = f" - {r.ko_chance} KO" if r.ko_chance else ""
            damage_lines.append(
                f"- {r.move.replace('-', ' ').title()}: {r.min_percent:.0f}-{r.max_percent:.0f}%{ko}{est}"
            )
        their_damage_vs_us = "\n".join(damage_lines)
    else:
        their_damage_vs_us = "No damage calculations available"

    # Speed info
    if speed_calc_raw:
        we_outspeed = speed_calc_raw.get("we_outspeed", False)
        our_speed = speed_calc_raw.get("our_speed", "?")
        their_speed = speed_calc_raw.get("their_speed", "?")
        speed_info = f"{'You outspeed' if we_outspeed else 'They outspeed'} ({our_speed} vs {their_speed})"
    else:
        speed_info = "Speed comparison unknown"

    # Their bench
    bench_pokemon = []
    for p in battle.opponent_team.values():
        if not p.active and not p.fainted:
            hp_str = f"{p.current_hp_fraction * 100:.0f}%" if p.current_hp_fraction else "?"
            types = "/".join(t.name for t in p.types if t)
            bench_pokemon.append(f"- {p.species} ({types}) - {hp_str} HP")

    their_bench = "\n".join(bench_pokemon) if bench_pokemon else "No bench Pokemon revealed"

    # Battle state summary
    battle_state = _format_battle_state(battle)

    return {
        "battle_state": battle_state,
        "their_pokemon": their_pokemon.species,
        "their_hp": their_pokemon.current_hp_fraction * 100,
        "their_known_moves": known_moves,
        "their_possible_moves": possible_moves,
        "our_pokemon": our_pokemon.species,
        "our_hp": our_pokemon.current_hp_fraction * 100,
        "their_damage_vs_us": their_damage_vs_us,
        "speed_info": speed_info,
        "their_bench": their_bench,
    }


def _format_battle_state(battle: Battle) -> str:
    """Format basic battle state for context."""
    lines = []
    lines.append(f"Turn: {battle.turn}")

    # Field conditions
    if battle.fields:
        fields = ", ".join(str(f).replace("Field.", "") for f in battle.fields)
        lines.append(f"Field: {fields}")

    # Side conditions
    if battle.side_conditions:
        our_side = ", ".join(str(c).replace("SideCondition.", "") for c in battle.side_conditions)
        lines.append(f"Your side: {our_side}")

    if battle.opponent_side_conditions:
        their_side = ", ".join(str(c).replace("SideCondition.", "") for c in battle.opponent_side_conditions)
        lines.append(f"Their side: {their_side}")

    # Weather
    if battle.weather:
        weather = ", ".join(str(w).replace("Weather.", "") for w in battle.weather)
        lines.append(f"Weather: {weather}")

    return "\n".join(lines) if lines else "No special conditions"


def _parse_predictions(response: str) -> list[dict[str, Any]]:
    """Parse prediction entries from LLM response."""
    predictions = []

    # Pattern to match prediction lines like:
    # 1. **Earthquake** (60%) - 45% damage to you - They can KO and will
    pattern = r'\d+\.\s*\*\*([^*]+)\*\*\s*\((\d+)%?\)\s*-\s*([^-]+)\s*-\s*(.+)'

    for match in re.finditer(pattern, response):
        action = match.group(1).strip()
        probability = int(match.group(2)) / 100
        damage_info = match.group(3).strip()
        reasoning = match.group(4).strip()

        # Determine action type
        action_lower = action.lower()
        if "switch" in action_lower:
            action_type = "switch"
            # Extract Pokemon name from "Switch to X" or "Switch X"
            switch_match = re.search(r'switch(?:\s+to)?\s+(\w+)', action_lower)
            action_target = switch_match.group(1).title() if switch_match else action
        else:
            action_type = "move"
            action_target = action

        predictions.append({
            "action_type": action_type,
            "action": action_target,
            "probability": probability,
            "damage_to_us": damage_info,
            "reasoning": reasoning,
        })

    # Sort by probability descending
    predictions.sort(key=lambda x: x["probability"], reverse=True)

    return predictions[:5]  # Top 5 predictions


def _extract_summary(response: str) -> str:
    """Extract the summary section from the response."""
    # Look for ## Summary section
    summary_match = re.search(r'##\s*Summary\s*\n(.+?)(?:\n##|\Z)', response, re.DOTALL)
    if summary_match:
        return summary_match.group(1).strip()

    # Fallback: use last paragraph
    paragraphs = response.strip().split('\n\n')
    if paragraphs:
        return paragraphs[-1].strip()[:200]

    return "Unable to determine expected opponent action"


def format_expected_action(expected: Optional[dict[str, Any]]) -> str:
    """Format expected opponent action for the decision node.

    Args:
        expected: The expected_opponent_action dict from state

    Returns:
        Formatted string for LLM consumption
    """
    if not expected:
        return "## Expected Opponent Action\nUnable to predict opponent's action."

    lines = ["## Expected Opponent Action"]
    lines.append("")

    predictions = expected.get("predictions", [])
    if predictions:
        for i, pred in enumerate(predictions[:3], 1):
            action = pred.get("action", "Unknown")
            prob = pred.get("probability", 0) * 100
            damage = pred.get("damage_to_us", "")
            reasoning = pred.get("reasoning", "")

            lines.append(f"{i}. **{action}** ({prob:.0f}%) - {damage}")
            if reasoning:
                lines.append(f"   {reasoning}")

    summary = expected.get("summary", "")
    if summary:
        lines.append("")
        lines.append(f"**Summary:** {summary}")

    return "\n".join(lines)
