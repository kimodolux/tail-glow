"""Predict opponent node - LLM call to predict what opponent will do.

This runs AFTER strategy analysis, using empathetic reasoning:
"If I were controlling their team, what would I do?"

Uses strategic context, damage calculations, speed analysis, type matchups,
and effects to make informed predictions about opponent behavior.

Outputs a probability distribution over all possible opponent actions.
"""

import logging
import re
from typing import Optional

from ..state import AgentState
from ..prompts.prediction import build_prediction_prompt, PREDICTION_SYSTEM_PROMPT
from src.llm import get_llm_provider

logger = logging.getLogger(__name__)


def predict_opponent_node(state: AgentState) -> dict:
    """
    Predict opponent's action using empathetic reasoning.

    Uses opponent's perspective: "If I were them, what would I do?"
    Runs AFTER strategy analysis to use strategic context along with
    damage/speed/type data for informed predictions.

    Returns:
        State update with opponent_prediction and turn_predictions
    """
    battle = state.get("battle_object")
    if not battle:
        logger.warning("No battle object available for prediction")
        return {}

    formatted_state = state.get("formatted_state", "")
    teams_state = state.get("teams_state")

    # Get parallel node outputs for informed prediction
    damage_calculations = state.get("damage_calculations")
    speed_analysis = state.get("speed_analysis")
    type_matchups = state.get("type_matchups")
    effects_analysis = state.get("effects_analysis")

    # Get strategic context (now available since strategy runs before prediction)
    strategy_analysis = state.get("strategy_analysis")

    # Format opponent's options (moves and switches)
    opponent_options = _format_opponent_options(battle, teams_state)

    if not opponent_options:
        logger.debug("No opponent options to predict")
        return {}

    # Build prompt with analysis context
    user_prompt = build_prediction_prompt(
        formatted_state=formatted_state,
        opponent_options=opponent_options,
        damage_calculations=damage_calculations,
        speed_analysis=speed_analysis,
        type_matchups=type_matchups,
        effects_analysis=effects_analysis,
        strategy_analysis=strategy_analysis,
    )

    # LLM call
    try:
        llm = get_llm_provider()
        username = state.get("username")
        trace_id = state.get("trace_id")
        turn = state.get("turn")
        battle_tag = state.get("battle_tag")

        response = llm.generate(
            PREDICTION_SYSTEM_PROMPT,
            user_prompt,
            user=username,
            trace_id=trace_id,
            generation_name="predict_opponent",
            turn=turn,
            battle_tag=battle_tag,
        )
        logger.debug(f"Prediction response: {response}")
    except Exception as e:
        logger.error(f"Prediction LLM error: {e}")
        return {}

    # Parse response into structured prediction
    prediction = _parse_prediction_response(response)

    if not prediction:
        logger.warning("Failed to parse prediction response")
        return {}

    # Store for accuracy tracking
    turn = battle.turn if battle else 0
    turn_predictions = state.get("turn_predictions") or {}
    turn_predictions[turn] = prediction

    logger.info(
        f"Turn {turn} prediction: {prediction.get('top_prediction', {}).get('action', 'unknown')} "
        f"({prediction.get('top_prediction', {}).get('probability', 0)*100:.0f}%)"
    )

    return {
        "opponent_prediction": prediction,
        "turn_predictions": turn_predictions,
    }


def _format_opponent_options(battle, teams_state) -> Optional[str]:
    """Format opponent's possible actions (moves and switches) for the prompt."""
    if not battle:
        return None

    lines = []

    # Active Pokemon's moves
    opponent_active = battle.opponent_active_pokemon
    if opponent_active and not opponent_active.fainted:
        species = opponent_active.species
        lines.append(f"**{species}'s Possible Moves:**")

        # Get from teams_state if available
        if teams_state:
            pokemon_state = teams_state.their_team.get(species)
            if pokemon_state:
                # Show revealed moves first
                if pokemon_state.revealed_moves:
                    for move in pokemon_state.revealed_moves:
                        move_display = move.replace("-", " ").title()
                        lines.append(f"- {move_display} (revealed)")

                # Then unrevealed possibilities (limit to avoid overwhelming)
                unrevealed = pokemon_state.unrevealed_moves()
                if unrevealed:
                    unrevealed_list = sorted(list(unrevealed))[:8]  # Limit to 8
                    for move in unrevealed_list:
                        move_display = move.replace("-", " ").title()
                        lines.append(f"- {move_display} (possible)")
                    if len(unrevealed) > 8:
                        lines.append(f"  ... and {len(unrevealed) - 8} more possible moves")
            else:
                # Fallback if no teams_state entry
                lines.append("- Unknown moves (no data)")
        else:
            lines.append("- Unknown moves (no teams_state)")

        lines.append("")

    # Bench Pokemon (switch options)
    bench = [
        p for p in battle.opponent_team.values()
        if not p.active and not p.fainted
    ]

    if bench:
        lines.append(f"**Opponent's Bench ({len(bench)} available):**")
        for pokemon in bench:
            hp_pct = pokemon.current_hp_fraction * 100
            types = "/".join(t.name for t in pokemon.types if t) if pokemon.types else "???"
            status = f" [{pokemon.status.name}]" if pokemon.status else ""
            lines.append(f"- {pokemon.species} ({types}, {hp_pct:.0f}% HP){status}")
    else:
        lines.append("**Opponent's Bench:** None available")

    return "\n".join(lines) if lines else None


def _parse_prediction_response(response: str) -> Optional[dict]:
    """Parse LLM prediction response into structured dict.

    Expected format:
        MOVES:
        - Ice Beam: 45% - Super effective STAB, likely KOs
        - Thunderbolt: 20% - Good neutral coverage
        ...

        SWITCHES:
        - Ferrothorn: 15% - Resists our STAB
        ...

    Returns:
        {
            "moves": {
                "Ice Beam": {"probability": 0.45, "reasoning": "Super effective STAB, likely KOs"},
                ...
            },
            "switches": {
                "Ferrothorn": {"probability": 0.15, "reasoning": "Resists our STAB"},
                ...
            },
            "top_prediction": {"action": "Ice Beam", "probability": 0.45, "reasoning": "..."},
        }
    """
    if not response:
        return None

    moves: dict[str, dict] = {}
    switches: dict[str, dict] = {}

    # Parse moves section
    moves_match = re.search(
        r"MOVES:\s*\n((?:- .+\n?)+)",
        response,
        re.IGNORECASE
    )
    if moves_match:
        moves_section = moves_match.group(1)
        moves = _parse_probability_lines_with_reasoning(moves_section)

    # Parse switches section
    switches_match = re.search(
        r"SWITCHES:\s*\n((?:- .+\n?)+)",
        response,
        re.IGNORECASE
    )
    if switches_match:
        switches_section = switches_match.group(1)
        switches = _parse_probability_lines_with_reasoning(switches_section)

    # Find top prediction
    all_predictions = {**moves, **switches}
    top_prediction = {"action": "unknown", "probability": 0.0, "reasoning": ""}

    if all_predictions:
        top_action = max(all_predictions, key=lambda k: all_predictions[k]["probability"])
        top_data = all_predictions[top_action]
        top_prediction = {
            "action": top_action,
            "probability": top_data["probability"],
            "reasoning": top_data["reasoning"],
        }

    return {
        "moves": moves,
        "switches": switches,
        "top_prediction": top_prediction,
    }


def _parse_probability_lines_with_reasoning(section: str) -> dict[str, dict]:
    """Parse lines like '- Ice Beam: 45% - Super effective' into dict with reasoning."""
    result = {}

    # Pattern: "- Action Name: XX% - reasoning" or "- Action Name: XX%"
    # Captures: action, probability, optional reasoning
    pattern = r"- ([^:]+):\s*(\d+)%(?:\s*-\s*(.+))?"

    for line in section.strip().split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            action = match.group(1).strip()
            prob = match.group(2)
            reasoning = match.group(3).strip() if match.group(3) else ""

            # Remove parenthetical notes like "(revealed)" or "(possible)"
            action_clean = re.sub(r"\s*\([^)]*\)\s*$", "", action).strip()

            try:
                result[action_clean] = {
                    "probability": int(prob) / 100.0,
                    "reasoning": reasoning,
                }
            except ValueError:
                continue

    return result
