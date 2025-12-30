"""Type matchups node - calculates type effectiveness using poke-env."""

import logging

from poke_env.battle import Pokemon, Move

from ..state import AgentState

logger = logging.getLogger(__name__)


def get_type_matchups_node(state: AgentState) -> dict:
    """
    Calculate type effectiveness for the current matchup.
    Returns only the fields this node modifies to avoid concurrent write issues.
    """
    battle = state.get("battle_object")
    if not battle or not battle.active_pokemon or not battle.opponent_active_pokemon:
        logger.warning("No active Pokemon in state, skipping type matchups")
        return {"type_matchups": None}

    try:
        our_pokemon = battle.active_pokemon
        their_pokemon = battle.opponent_active_pokemon

        matchup_text = _calculate_type_matchups(
            our_pokemon,
            their_pokemon,
            battle.available_moves,
        )

        logger.info("Type matchups calculated successfully")
        return {"type_matchups": matchup_text}

    except Exception as e:
        logger.error(f"Type matchup calculation failed: {e}", exc_info=True)
        return {"type_matchups": None}


def _calculate_type_matchups(
    our_pokemon: Pokemon,
    their_pokemon: Pokemon,
    available_moves: list[Move],
) -> str:
    """Calculate and format type matchups."""
    lines = ["## Type Matchups"]
    lines.append("")

    # Our moves vs their types
    lines.append("**Your Moves → Them:**")
    for move in available_moves:
        if move.base_power and move.base_power > 0:  # Only attacking moves
            effectiveness = their_pokemon.damage_multiplier(move)
            eff_str = _format_effectiveness(effectiveness)
            move_name = move.id.replace("-", " ").title()
            move_type = move.type.name if move.type else "???"
            lines.append(f"- {move_name} ({move_type}): {eff_str}")

    # Their STAB types vs us
    lines.append("")
    lines.append("**Their STAB → You:**")
    their_types = [t for t in their_pokemon.types if t]
    for pokemon_type in their_types:
        effectiveness = our_pokemon.damage_multiplier(pokemon_type)
        eff_str = _format_effectiveness(effectiveness)
        type_name = pokemon_type.name if pokemon_type else "???"
        lines.append(f"- {type_name}: {eff_str}")

    # Highlight dangerous matchups
    lines.append("")
    warnings = []

    # Check for 4x weaknesses
    for pokemon_type in their_types:
        effectiveness = our_pokemon.damage_multiplier(pokemon_type)
        if effectiveness >= 4:
            type_name = pokemon_type.name if pokemon_type else "???"
            warnings.append(f"4x weak to {type_name} STAB!")

    # Check for immunities we can exploit
    for move in available_moves:
        if move.base_power and move.base_power > 0:
            effectiveness = their_pokemon.damage_multiplier(move)
            if effectiveness == 0:
                move_name = move.id.replace("-", " ").title()
                warnings.append(f"{move_name} is immune (0x damage)")

    if warnings:
        lines.append("**Warnings:**")
        for warning in warnings:
            lines.append(f"- {warning}")

    # Check for tera considerations if tera type known
    if their_pokemon.tera_type and their_pokemon.terastallized:
        lines.append("")
        lines.append(f"**Note:** Opponent has terastallized to {their_pokemon.tera_type.name}")

    return "\n".join(lines)


def _format_effectiveness(multiplier: float) -> str:
    """Format effectiveness multiplier as human-readable string."""
    if multiplier == 0:
        return "**IMMUNE (0x)**"
    elif multiplier == 0.25:
        return "not very effective (0.25x)"
    elif multiplier == 0.5:
        return "not very effective (0.5x)"
    elif multiplier == 1:
        return "neutral (1x)"
    elif multiplier == 2:
        return "**SUPER EFFECTIVE (2x)**"
    elif multiplier == 4:
        return "**SUPER EFFECTIVE (4x)**"
    else:
        return f"{multiplier}x"
