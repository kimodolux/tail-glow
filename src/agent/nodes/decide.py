"""Decision node - LLM Call #3 (Every turn).

Makes the final move/switch decision based on all gathered battle information
and the strategy analysis from the previous node.
"""

import logging

from ..state import AgentState
from ..prompts import DECISION_SYSTEM_PROMPT, build_decision_prompt
from src.llm import get_llm_provider

logger = logging.getLogger(__name__)


def decide_action_node(state: AgentState) -> AgentState:
    """
    Call LLM to decide action based on all gathered battle information.
    This is LLM Call #3 - uses parallel node outputs and strategy analysis.
    """
    battle = state.get("battle_object")

    # Gather all node outputs
    formatted_state = state.get("formatted_state", "Unknown battle state")
    damage_calculations = state.get("damage_calculations")
    speed_analysis = state.get("speed_analysis")
    type_matchups = state.get("type_matchups")
    effects_analysis = state.get("effects_analysis")
    strategy_analysis = state.get("strategy_analysis")
    team_analysis = state.get("team_analysis")

    # Get opponent prediction
    opponent_prediction = state.get("opponent_prediction")
    opponent_prediction_str = _format_opponent_prediction(opponent_prediction)

    # Get game memory and format for prompt
    game_memory = state.get("game_memory")
    game_memory_str = game_memory.format_for_prompt() if game_memory else None

    # Format available options
    available_moves = _format_available_moves(battle)
    available_switches = _format_available_switches(battle)

    # Build decision prompt with all context
    user_prompt = build_decision_prompt(
        formatted_state=formatted_state,
        damage_calculations=damage_calculations,
        speed_analysis=speed_analysis,
        type_matchups=type_matchups,
        effects_analysis=effects_analysis,
        strategy_analysis=strategy_analysis,
        team_analysis=team_analysis,
        available_moves=available_moves,
        available_switches=available_switches,
        game_memory=game_memory_str,
        opponent_prediction=opponent_prediction_str,
    )

    try:
        llm = get_llm_provider()
        username = state.get("username")
        trace_id = state.get("trace_id")
        turn = state.get("turn")
        battle_tag = state.get("battle_tag")
        response = llm.generate(
            DECISION_SYSTEM_PROMPT,
            user_prompt,
            user=username,
            trace_id=trace_id,
            generation_name="decide_action",
            turn=turn,
            battle_tag=battle_tag,
        )
        state["llm_response"] = response
        logger.debug(f"Decision response: {response}")
    except Exception as e:
        logger.error(f"Decision LLM error: {e}")
        state["error"] = f"Decision error: {e}"
        # Fallback to first available move
        state["llm_response"] = _create_fallback_response(battle)

    return state


def _format_available_moves(battle) -> str:
    """Format available moves for the decision prompt."""
    if not battle or not battle.available_moves:
        return "None available"

    lines = []
    for move in battle.available_moves:
        move_name = move.id.replace("-", " ").title()
        move_type = move.type.name if move.type else "???"
        base_power = move.base_power if move.base_power else "—"
        accuracy = _format_accuracy(move.accuracy)

        # Include priority if non-zero
        priority_str = f" [Priority +{move.priority}]" if move.priority > 0 else ""
        priority_str = f" [Priority {move.priority}]" if move.priority < 0 else priority_str

        lines.append(f"- {move_name} ({move_type}, {base_power} BP, {accuracy} acc){priority_str}")

    return "\n".join(lines) if lines else "None available"


def _format_accuracy(accuracy) -> str:
    """Format poke-env move accuracy for prompts."""
    if accuracy is True:
        return "—"
    if not accuracy:
        return "—"

    try:
        accuracy_value = float(accuracy)
    except (TypeError, ValueError):
        return str(accuracy)

    if accuracy_value <= 1:
        accuracy_value *= 100

    return f"{accuracy_value:.0f}%"


def _format_available_switches(battle) -> str:
    """Format available switches for the decision prompt."""
    if not battle or not battle.available_switches:
        return "None available"

    lines = []
    for pokemon in battle.available_switches:
        species = pokemon.species
        types = "/".join(t.name for t in pokemon.types if t)
        hp_pct = f"{pokemon.current_hp_fraction * 100:.0f}%" if pokemon.current_hp_fraction else "???"
        status = f" [{pokemon.status.name}]" if pokemon.status else ""

        lines.append(f"- {species} ({types}, {hp_pct} HP){status}")

    return "\n".join(lines) if lines else "None available"


def _create_fallback_response(battle) -> str:
    """Create a fallback response when LLM fails."""
    if battle and battle.available_moves:
        first_move = battle.available_moves[0].id.replace("-", " ").title()
        return f"REASONING: LLM error fallback.\nACTION: {first_move}"
    elif battle and battle.available_switches:
        first_switch = battle.available_switches[0].species
        return f"REASONING: LLM error fallback.\nACTION: Switch to {first_switch}"
    else:
        return "REASONING: No options available.\nACTION: Struggle"


def _format_opponent_prediction(prediction: dict | None) -> str | None:
    """Format opponent prediction for the decision prompt."""
    if not prediction:
        return None

    lines = ["## Opponent Prediction"]

    top = prediction.get("top_prediction", {})
    if top.get("action"):
        prob = top.get("probability", 0) * 100
        reasoning = top.get("reasoning", "")
        lines.append(f"**Most likely:** {top['action']} ({prob:.0f}%)")
        if reasoning:
            lines.append(f"  Reasoning: {reasoning}")
        lines.append("")

    # Show move predictions
    moves = prediction.get("moves", {})
    if moves:
        lines.append("**Move probabilities:**")
        # Sort by probability descending
        sorted_moves = sorted(moves.items(), key=lambda x: x[1].get("probability", 0), reverse=True)
        for move, data in sorted_moves:
            prob = data.get("probability", 0) * 100
            reasoning = data.get("reasoning", "")
            lines.append(f"- {move}: {prob:.0f}%{f' - {reasoning}' if reasoning else ''}")
        lines.append("")

    # Show switch predictions
    switches = prediction.get("switches", {})
    if switches:
        lines.append("**Switch probabilities:**")
        sorted_switches = sorted(switches.items(), key=lambda x: x[1].get("probability", 0), reverse=True)
        for pokemon, data in sorted_switches:
            prob = data.get("probability", 0) * 100
            reasoning = data.get("reasoning", "")
            lines.append(f"- {pokemon}: {prob:.0f}%{f' - {reasoning}' if reasoning else ''}")

    return "\n".join(lines)
