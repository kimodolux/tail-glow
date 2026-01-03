"""Team analysis node - LLM Call #1 (Turn 1 only).

Analyzes the team to identify roles, strengths, and weaknesses.
"""

import logging

from ..state import AgentState
from ..prompts import TEAM_ANALYSIS_SYSTEM_PROMPT, build_team_analysis_prompt
from src.llm import get_llm_provider

logger = logging.getLogger(__name__)


def analyze_team_node(state: AgentState) -> AgentState:
    """
    Analyze the team composition to identify roles and synergy.
    Called only on turn 1. Results persist for the entire battle.
    """
    battle = state.get("battle_object")
    if not battle:
        logger.warning("No battle object in state, skipping team analysis")
        state["team_analysis"] = None
        return state

    try:
        # Build team info string
        team_info = _format_team_for_analysis(battle)

        # Call LLM for analysis
        llm = get_llm_provider()
        user_prompt = build_team_analysis_prompt(team_info)
        username = state.get("username")

        response = llm.generate(TEAM_ANALYSIS_SYSTEM_PROMPT, user_prompt, user=username)

        state["team_analysis"] = response.strip()
        logger.info("Team analysis completed successfully")

    except Exception as e:
        logger.error(f"Team analysis failed: {e}", exc_info=True)
        state["team_analysis"] = None
        state["error"] = f"Team analysis error: {e}"

    return state


def _format_team_for_analysis(battle) -> str:
    """Format our team information for LLM analysis.

    Args:
        battle: The battle object

    Returns:
        Formatted string describing each team member
    """
    lines = []

    for pokemon_id, pokemon in battle.team.items():
        # Basic info
        species = pokemon.species
        types = "/".join(t.name for t in pokemon.types if t)

        # Moves
        if pokemon.moves:
            moves = ", ".join(
                m.replace("-", " ").title()
                for m in pokemon.moves.keys()
            )
        else:
            moves = "Unknown"

        # Ability and item
        ability = pokemon.ability if pokemon.ability else "Unknown"
        item = pokemon.item if pokemon.item else "Unknown"

        # Stats (if known)
        if pokemon.stats:
            stats_str = f"HP: {pokemon.stats.get('hp', '?')}, " \
                       f"Atk: {pokemon.stats.get('atk', '?')}, " \
                       f"Def: {pokemon.stats.get('def', '?')}, " \
                       f"SpA: {pokemon.stats.get('spa', '?')}, " \
                       f"SpD: {pokemon.stats.get('spd', '?')}, " \
                       f"Spe: {pokemon.stats.get('spe', '?')}"
        else:
            stats_str = "Unknown"

        lines.append(f"**{species}** ({types})")
        lines.append(f"  - Moves: {moves}")
        lines.append(f"  - Ability: {ability}")
        lines.append(f"  - Item: {item}")
        lines.append(f"  - Stats: {stats_str}")
        lines.append("")

    return "\n".join(lines)
