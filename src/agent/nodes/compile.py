"""Compile context node - LLM Call #2 (Every turn).

Synthesizes all parallel node outputs into a focused battle analysis.
"""

import logging

from ..state import AgentState
from ..prompts import COMPILE_SYSTEM_PROMPT, build_compile_prompt
from src.llm import get_llm_provider

logger = logging.getLogger(__name__)


def compile_context_node(state: AgentState) -> AgentState:
    """
    Synthesize all parallel node outputs into a focused analysis.
    This prevents the decision LLM from being overwhelmed with raw data.
    """
    battle = state.get("battle_object")
    if not battle:
        logger.warning("No battle object in state, skipping compile")
        state["compiled_analysis"] = None
        return state

    try:
        # Gather all parallel node outputs
        formatted_state = state.get("formatted_state", "Unknown battle state")
        damage_calculations = state.get("damage_calculations")
        speed_analysis = state.get("speed_analysis")
        type_matchups = state.get("type_matchups")
        effects_analysis = state.get("effects_analysis")
        strategy_context = state.get("strategy_context")
        team_analysis = state.get("team_analysis")

        # Build the compile prompt with all context
        user_prompt = build_compile_prompt(
            formatted_state=formatted_state,
            damage_calculations=damage_calculations,
            speed_analysis=speed_analysis,
            type_matchups=type_matchups,
            effects_analysis=effects_analysis,
            strategy_context=strategy_context,
            team_analysis=team_analysis,
        )

        # Call LLM to synthesize
        llm = get_llm_provider()
        username = state.get("username")
        response = llm.generate(COMPILE_SYSTEM_PROMPT, user_prompt, user=username)

        state["compiled_analysis"] = response.strip()
        logger.info("Context compilation completed successfully")

    except Exception as e:
        logger.error(f"Context compilation failed: {e}", exc_info=True)
        # Fallback: create a basic analysis from available data
        state["compiled_analysis"] = _create_fallback_analysis(state)
        state["error"] = f"Compile error: {e}"

    return state


def _create_fallback_analysis(state: AgentState) -> str:
    """Create a basic fallback analysis if LLM compilation fails."""
    lines = ["## Battle Summary (Fallback)"]

    battle = state.get("battle_object")
    if battle and battle.active_pokemon and battle.opponent_active_pokemon:
        our_pokemon = battle.active_pokemon.species
        their_pokemon = battle.opponent_active_pokemon.species
        lines.append(f"Current matchup: {our_pokemon} vs {their_pokemon}")

    if state.get("speed_analysis"):
        lines.append("")
        lines.append("Speed info available - check who moves first.")

    if state.get("type_matchups"):
        lines.append("")
        lines.append("Type matchup info available.")

    if state.get("damage_calculations"):
        lines.append("")
        lines.append("Damage calculations available.")

    lines.append("")
    lines.append("Make the best decision based on available information.")

    return "\n".join(lines)
