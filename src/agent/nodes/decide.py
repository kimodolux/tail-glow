"""Decision node - LLM Call (Every turn).

Makes the final move/switch decision based on pre-analyzed summaries.
"""

import logging
from typing import Any

from src.agent.state import AgentState
from src.agent.prompts import DECISION_SYSTEM_PROMPT, build_decision_prompt
from src.llm import get_llm_provider

logger = logging.getLogger(__name__)


def decide_action_node(state: AgentState) -> dict[str, Any]:
    """Call LLM to decide action based on pre-analyzed battle information.

    Uses summaries from:
    - expected_opponent_action
    - best_moves
    - best_switches
    - speed_analysis
    - battle_analysis
    - battle_strategy
    """
    battle = state.get("battle_object")

    # Get pre-analyzed summaries
    formatted_state = state.get("formatted_state", "Unknown battle state")

    # Speed summary
    speed_summary = _extract_speed_summary(state)

    # Expected opponent action
    expected_action = state.get("expected_opponent_action", {})
    expected_opponent_summary = expected_action.get("summary", "Unable to predict") if expected_action else "Unable to predict"

    # Best moves
    best_moves = state.get("best_moves", {})
    best_moves_summary = best_moves.get("summary", "No analysis") if best_moves else "No analysis"
    best_moves_list = _format_moves_list(best_moves)

    # Best switches
    best_switches = state.get("best_switches", {})
    best_switches_summary = best_switches.get("summary", "No analysis") if best_switches else "No analysis"
    best_switches_list = _format_switches_list(best_switches)

    # Battle context and strategy
    battle_context = state.get("battle_analysis", "")
    battle_strategy = state.get("battle_strategy", "")

    # Format available options
    available_moves = _format_available_moves(battle)
    available_switches = _format_available_switches(battle)

    # Build decision prompt with summaries
    user_prompt = build_decision_prompt(
        formatted_state=formatted_state,
        speed_summary=speed_summary,
        expected_opponent_summary=expected_opponent_summary,
        best_moves_summary=best_moves_summary,
        best_moves_list=best_moves_list,
        best_switches_summary=best_switches_summary,
        best_switches_list=best_switches_list,
        battle_context=battle_context,
        battle_strategy=battle_strategy,
        available_moves=available_moves,
        available_switches=available_switches,
    )

    try:
        llm = get_llm_provider()
        username = state.get("username")
        response = llm.generate(DECISION_SYSTEM_PROMPT, user_prompt, user=username)
        logger.debug(f"Decision response: {response}")
        return {"llm_response": response}
    except Exception as e:
        logger.error(f"Decision LLM error: {e}")
        fallback = _create_fallback_response(battle)
        return {"llm_response": fallback, "error": f"Decision error: {e}"}


def _extract_speed_summary(state: AgentState) -> str:
    """Extract a simple speed summary from speed analysis."""
    speed_raw = state.get("speed_calc_raw", {})
    speed_analysis = state.get("speed_analysis", "")

    if speed_raw:
        we_outspeed = speed_raw.get("we_outspeed", False)
        our_speed = speed_raw.get("our_speed", "?")
        their_speed = speed_raw.get("their_speed", "?")

        if we_outspeed:
            return f"You outspeed ({our_speed} vs {their_speed}). You move first."
        else:
            return f"They outspeed ({their_speed} vs {our_speed}). They move first."

    # Fallback to formatted analysis
    if speed_analysis:
        # Extract the verdict line
        if "YOU OUTSPEED" in speed_analysis:
            return "You outspeed. You move first."
        elif "THEY OUTSPEED" in speed_analysis:
            return "They outspeed. They move first."

    return "Speed comparison unknown."


def _format_moves_list(best_moves: dict) -> str:
    """Format the ranked moves list."""
    if not best_moves:
        return ""

    moves = best_moves.get("moves", [])
    if not moves:
        return ""

    lines = ["**Ranked:**"]
    for move_data in moves[:4]:
        move_name = move_data["move"].replace("-", " ").title()
        rank = move_data.get("rank", "?")
        damage = move_data.get("damage_to_active", "?")
        reasoning = move_data.get("reasoning", "")

        lines.append(f"{rank}. {move_name}: {damage}")
        if reasoning:
            lines.append(f"   ({reasoning})")

    return "\n".join(lines)


def _format_switches_list(best_switches: dict) -> str:
    """Format the ranked switches list."""
    if not best_switches:
        return ""

    switches = best_switches.get("switches", [])
    if not switches:
        return ""

    lines = ["**Ranked:**"]
    for switch_data in switches[:4]:
        name = switch_data["pokemon"].replace("-", " ").title()
        rank = switch_data.get("rank", "?")
        survives = switch_data.get("survives", False)
        matchup = switch_data.get("matchup_result", "?")

        survive_str = "survives" if survives else "DIES"
        lines.append(f"{rank}. {name} ({survive_str}): {matchup}")

    return "\n".join(lines)


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
