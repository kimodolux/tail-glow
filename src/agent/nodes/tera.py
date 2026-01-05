"""Terastallization node - passthrough for future implementation.

Tracks Tera availability and will provide recommendations in the future.
"""

import logging
from typing import Any, Optional

from poke_env.battle import Battle

from src.agent.state import AgentState

logger = logging.getLogger(__name__)


def tera_node(state: AgentState) -> dict[str, Any]:
    """Track Terastallization availability (passthrough node).

    Currently only tracks whether Tera is available for each side.
    Future implementation will provide recommendations for when to Tera.

    Args:
        state: Current agent state

    Returns:
        Dict with tera_analysis containing availability info
    """
    battle: Optional[Battle] = state.get("battle_object")

    if not battle:
        return {"tera_analysis": None}

    try:
        # Check if we can Tera
        our_tera_available = _check_our_tera(battle)

        # Check if opponent has Tera'd (we can't know if they have it available)
        opponent_has_terad = _check_opponent_terad(battle)

        result = {
            "our_tera_available": our_tera_available,
            "opponent_tera_available": not opponent_has_terad,  # Assume available if not used
            "opponent_has_terad": opponent_has_terad,
            "our_tera_type": _get_our_tera_type(battle),
            "recommendation": None,  # Future: will provide Tera recommendations
            "summary": _build_summary(our_tera_available, opponent_has_terad),
        }

        return {"tera_analysis": result}

    except Exception as e:
        logger.error(f"Tera analysis failed: {e}", exc_info=True)
        return {"tera_analysis": None}


def _check_our_tera(battle: Battle) -> bool:
    """Check if we can still Terastallize."""
    # poke-env tracks this via can_tera
    if hasattr(battle, 'can_tera') and battle.can_tera is not None:
        return battle.can_tera

    # Fallback: check if any of our Pokemon have terastallized
    for pokemon in battle.team.values():
        if hasattr(pokemon, 'terastallized') and pokemon.terastallized:
            return False

    return True


def _check_opponent_terad(battle: Battle) -> bool:
    """Check if opponent has already Terastallized."""
    for pokemon in battle.opponent_team.values():
        if hasattr(pokemon, 'terastallized') and pokemon.terastallized:
            return True
    return False


def _get_our_tera_type(battle: Battle) -> Optional[str]:
    """Get our active Pokemon's Tera type if known."""
    if not battle.active_pokemon:
        return None

    pokemon = battle.active_pokemon
    if hasattr(pokemon, 'tera_type') and pokemon.tera_type:
        return str(pokemon.tera_type).replace("PokemonType.", "")

    return None


def _build_summary(our_tera_available: bool, opponent_has_terad: bool) -> str:
    """Build a summary of Tera status."""
    parts = []

    if our_tera_available:
        parts.append("Tera available")
    else:
        parts.append("Tera used")

    if opponent_has_terad:
        parts.append("opponent has Tera'd")
    else:
        parts.append("opponent Tera unknown")

    return "; ".join(parts) + ". (Analysis not yet implemented)"


def format_tera_analysis(tera_analysis: Optional[dict[str, Any]]) -> str:
    """Format Tera analysis for the decision node.

    Args:
        tera_analysis: The tera_analysis dict from state

    Returns:
        Formatted string for LLM consumption
    """
    if not tera_analysis:
        return ""

    lines = ["## Terastallization"]
    lines.append("")

    our_tera = tera_analysis.get("our_tera_available", False)
    opponent_terad = tera_analysis.get("opponent_has_terad", False)
    our_type = tera_analysis.get("our_tera_type")

    if our_tera:
        type_str = f" (Tera {our_type})" if our_type else ""
        lines.append(f"**Your Tera:** Available{type_str}")
    else:
        lines.append("**Your Tera:** Already used")

    if opponent_terad:
        lines.append("**Opponent:** Has Terastallized")
    else:
        lines.append("**Opponent:** Tera available (assumed)")

    summary = tera_analysis.get("summary", "")
    if summary:
        lines.append("")
        lines.append(f"*{summary}*")

    return "\n".join(lines)
