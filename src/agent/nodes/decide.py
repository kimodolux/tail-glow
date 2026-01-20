"""Decision node - LLM Call #2 (Every turn).

Makes the final move/switch decision based on all gathered battle information.
"""

import logging

from ..state import AgentState
from ..prompts import DECISION_SYSTEM_PROMPT, build_decision_prompt
from src.llm import get_llm_provider

logger = logging.getLogger(__name__)


def decide_action_node(state: AgentState) -> AgentState:
    """
    Call LLM to decide action based on all gathered battle information.
    This is LLM Call #2 - uses all parallel node outputs directly.
    """
    battle = state.get("battle_object")

    # Gather all parallel node outputs
    formatted_state = state.get("formatted_state", "Unknown battle state")
    damage_calculations = state.get("damage_calculations")
    speed_analysis = state.get("speed_analysis")
    type_matchups = state.get("type_matchups")
    effects_analysis = state.get("effects_analysis")
    strategy_context = state.get("strategy_context")
    team_analysis = state.get("team_analysis")

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
        strategy_context=strategy_context,
        team_analysis=team_analysis,
        available_moves=available_moves,
        available_switches=available_switches,
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
        accuracy = f"{move.accuracy}%" if move.accuracy else "—"

        # Include priority if non-zero
        priority_str = f" [Priority +{move.priority}]" if move.priority > 0 else ""
        priority_str = f" [Priority {move.priority}]" if move.priority < 0 else priority_str

        lines.append(f"- {move_name} ({move_type}, {base_power} BP, {accuracy} acc){priority_str}")

    return "\n".join(lines) if lines else "None available"


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
