"""Turn analysis node - Analyzes the previous turn for mistakes.

Runs at the start of each turn (after turn 1) to detect mistakes
from the previous turn that should be learned from.
"""

import logging
from typing import Optional

from ..state import AgentState
from ..prompts.turn_analysis import (
    TURN_ANALYSIS_SYSTEM_PROMPT,
    build_turn_analysis_prompt,
    parse_mistake_response,
)
from src.llm import get_llm_provider
from src.rag.models import MistakeLearning, MistakeType, SetContext
from src.battle.event_parser import format_turn_events_for_analysis, determine_turn_outcome

logger = logging.getLogger(__name__)


def analyze_turn_node(state: AgentState) -> dict:
    """
    Analyze the previous turn for potential mistakes.

    This node runs at the START of each turn, analyzing what happened
    on the previous turn. It skips turn 1 (no previous turn to analyze).

    Returns state updates with any detected mistakes.
    """
    battle = state.get("battle_object")

    # Skip on turn 1 - no previous turn to analyze
    if battle.turn <= 1:
        return {"turn_mistakes": []}

    previous_turn = battle.turn - 1

    # Check if we have observations for the previous turn
    if previous_turn not in battle.observations:
        logger.debug(f"No observations for turn {previous_turn}")
        return {"turn_mistakes": []}

    # Get previous turn data
    obs = battle.observations[previous_turn]
    turn_reasoning = state.get("turn_reasoning", {})
    reasoning = turn_reasoning.get(previous_turn, "")

    try:
        # Build turn events description (using shared parser)
        turn_events = format_turn_events_for_analysis(obs, battle)

        # Build outcome description (using shared parser)
        outcome = determine_turn_outcome(obs, battle)

        # Get damage context if available
        damage_context = state.get("damage_calculations", "")

        # Build and call LLM
        user_prompt = build_turn_analysis_prompt(
            turn_number=previous_turn,
            turn_events=turn_events,
            our_reasoning=reasoning,
            damage_context=damage_context,
            outcome=outcome,
        )

        llm = get_llm_provider()
        username = state.get("username")
        trace_id = state.get("trace_id")
        battle_tag = state.get("battle_tag")

        response = llm.generate(
            TURN_ANALYSIS_SYSTEM_PROMPT,
            user_prompt,
            user=username,
            trace_id=trace_id,
            generation_name="turn_analysis",
            turn=battle.turn,
            battle_tag=battle_tag,
        )

        # Parse response
        mistake_data = parse_mistake_response(response)

        if mistake_data:
            # Convert to MistakeLearning object
            mistake = _create_mistake_learning(
                mistake_data=mistake_data,
                obs=obs,
                battle=battle,
                turn=previous_turn,
            )
            if mistake:
                logger.info(
                    f"Detected mistake on turn {previous_turn}: "
                    f"{mistake.mistake_type.value} - {mistake.what_happened}"
                )
                return {"turn_mistakes": [mistake]}
        else:
            logger.debug(f"No mistake detected on turn {previous_turn}")

    except Exception as e:
        logger.error(f"Turn analysis failed: {e}")

    return {"turn_mistakes": []}


def _create_mistake_learning(
    mistake_data: dict,
    obs,
    battle,
    turn: int,
) -> Optional[MistakeLearning]:
    """Create a MistakeLearning object from parsed response data.

    Args:
        mistake_data: Parsed mistake data from LLM response
        obs: Observation object for the turn
        battle: Battle object for context
        turn: Turn number

    Returns:
        MistakeLearning object, or None if data is incomplete
    """
    try:
        # Get Pokemon info
        our_pokemon = obs.active_pokemon.species if obs.active_pokemon else "unknown"
        opponent = obs.opponent_active_pokemon.species if obs.opponent_active_pokemon else "unknown"

        # Determine roles (basic heuristic - can be improved)
        our_role = _infer_role(obs.active_pokemon) if obs.active_pokemon else "unknown"
        opponent_role = _infer_role(obs.opponent_active_pokemon) if obs.opponent_active_pokemon else "unknown"

        return MistakeLearning(
            mistake_type=mistake_data.get("mistake_type", MistakeType.BAD_PREDICTION),
            our_pokemon=our_pokemon.lower(),
            our_role=our_role,
            opponent=opponent.lower(),
            opponent_role=opponent_role,
            context=mistake_data.get("context", ""),
            what_happened=mistake_data.get("what_happened", ""),
            better_play=mistake_data.get("better_play", ""),
            battle_id=battle.battle_tag,
            turn=turn,
            format=battle.format if hasattr(battle, 'format') else "gen9randombattle",
        )

    except Exception as e:
        logger.error(f"Failed to create MistakeLearning: {e}")
        return None


def _infer_role(pokemon) -> str:
    """Infer a Pokemon's role from its stats and moves.

    This is a basic heuristic. Can be improved with more sophisticated analysis.

    Args:
        pokemon: Pokemon object

    Returns:
        Role string (e.g., "physical_attacker", "special_attacker", "wall")
    """
    if pokemon is None:
        return "unknown"

    # Check stats if available
    try:
        base_stats = pokemon.base_stats

        attack = base_stats.get("atk", 0)
        sp_attack = base_stats.get("spa", 0)
        defense = base_stats.get("def", 0)
        sp_defense = base_stats.get("spd", 0)
        speed = base_stats.get("spe", 0)

        # Offensive vs Defensive
        offensive_stat = max(attack, sp_attack)
        defensive_stat = (defense + sp_defense) / 2

        if offensive_stat > defensive_stat + 30:
            # Offensive Pokemon
            if attack > sp_attack:
                if speed > 100:
                    return "physical_sweeper"
                return "physical_attacker"
            else:
                if speed > 100:
                    return "special_sweeper"
                return "special_attacker"
        elif defensive_stat > offensive_stat + 30:
            # Defensive Pokemon
            if defense > sp_defense:
                return "physical_wall"
            return "special_wall"
        else:
            # Balanced
            return "balanced"

    except (AttributeError, KeyError):
        return "unknown"
