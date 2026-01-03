"""Effects lookup node - retrieves item, ability, and move effect descriptions."""

import logging
from typing import Optional

from poke_env.battle import Battle, Move

from ..state import AgentState
from src.data.effects import get_item_effect, get_ability_effect, get_move_effect

logger = logging.getLogger(__name__)


def get_effects_node(state: AgentState) -> dict:
    """
    Look up relevant item, ability, and move effects for the current matchup.
    Combines poke-env Move properties with curated effect descriptions.
    Returns only the fields this node modifies to avoid concurrent write issues.
    """
    battle = state.get("battle_object")
    if not battle or not battle.active_pokemon or not battle.opponent_active_pokemon:
        logger.warning("No active Pokemon in state, skipping effects lookup")
        return {"effects_analysis": None}

    try:
        our_pokemon = battle.active_pokemon
        their_pokemon = battle.opponent_active_pokemon
        opponent_sets = state.get("opponent_sets", {})

        effects_text = _compile_effects(
            our_pokemon,
            their_pokemon,
            battle.available_moves,
            opponent_sets,
        )

        logger.info("Effects analysis compiled successfully")
        return {"effects_analysis": effects_text}

    except Exception as e:
        logger.error(f"Effects lookup failed: {e}", exc_info=True)
        return {"effects_analysis": None}


def _compile_effects(
    our_pokemon,
    their_pokemon,
    available_moves: list[Move],
    opponent_sets: dict,
) -> str:
    """Compile all relevant effects into a formatted string."""
    lines = ["## Relevant Effects"]
    lines.append("")

    # Our Pokemon's effects
    lines.append(f"**Your {our_pokemon.species}:**")
    our_effects = []

    # Our ability
    if our_pokemon.ability:
        ability_effect = get_ability_effect(our_pokemon.ability)
        if ability_effect:
            our_effects.append(f"- Ability ({our_pokemon.ability}): {ability_effect}")
        else:
            logger.warning(f"Missing ability effect: {our_pokemon.ability}")

    # Our item
    if our_pokemon.item:
        item_effect = get_item_effect(our_pokemon.item)
        if item_effect:
            our_effects.append(f"- Item ({our_pokemon.item}): {item_effect}")
        else:
            logger.warning(f"Missing item effect: {our_pokemon.item}")

    if our_effects:
        lines.extend(our_effects)
    else:
        lines.append("- No special effects noted")

    # Notable move effects for our available moves
    move_effects = []
    for move in available_moves:
        effect = _get_move_effect_summary(move)
        if effect:
            move_effects.append(f"- {move.id.replace('-', ' ').title()}: {effect}")

    if move_effects:
        lines.append("")
        lines.append("**Your Move Effects:**")
        lines.extend(move_effects)

    # Opponent's effects
    lines.append("")
    lines.append(f"**Opponent's {their_pokemon.species}:**")
    their_effects = []

    # Known ability
    if their_pokemon.ability:
        ability_effect = get_ability_effect(their_pokemon.ability)
        if ability_effect:
            their_effects.append(f"- Ability ({their_pokemon.ability}): {ability_effect}")
        else:
            logger.warning(f"Missing ability effect: {their_pokemon.ability}")
    else:
        # Show possible abilities from randbats data
        species_data = opponent_sets.get(their_pokemon.species, {})
        possible_abilities = species_data.get("possible_abilities", [])
        if possible_abilities:
            notable_abilities = []
            for ability in possible_abilities[:3]:  # Limit to top 3
                effect = get_ability_effect(ability)
                if effect:
                    notable_abilities.append(f"{ability}: {effect}")
                else:
                    logger.warning(f"Missing ability effect: {ability}")
            if notable_abilities:
                their_effects.append("- Possible abilities: " + "; ".join(notable_abilities))

    # Known item
    if their_pokemon.item and their_pokemon.item not in ['', 'unknown']:
        item_effect = get_item_effect(their_pokemon.item)
        if item_effect:
            their_effects.append(f"- Item ({their_pokemon.item}): {item_effect}")
        else:
            logger.warning(f"Missing item effect: {their_pokemon.item}")
    else:
        # Show possible items from randbats data
        species_data = opponent_sets.get(their_pokemon.species, {})
        possible_items = species_data.get("possible_items", [])
        if possible_items:
            notable_items = []
            for item in possible_items[:4]:  # Limit to top 4
                effect = get_item_effect(item)
                if effect:
                    notable_items.append(f"{item}")
                else:
                    logger.warning(f"Missing item effect: {item}")
            if notable_items:
                their_effects.append(f"- Possible items: {', '.join(notable_items)}")

    if their_effects:
        lines.extend(their_effects)
    else:
        lines.append("- No special effects noted")

    # Key move effects opponent might have
    species_data = opponent_sets.get(their_pokemon.species, {})
    possible_moves = species_data.get("possible_moves", [])
    revealed_moves = set(species_data.get("revealed_moves", []))

    notable_opponent_moves = []
    for move_id in possible_moves:
        move_effect = get_move_effect(move_id)
        if move_effect:
            is_revealed = move_id in revealed_moves
            marker = "" if is_revealed else " (possible)"
            notable_opponent_moves.append(f"{move_id.replace('-', ' ').title()}{marker}: {move_effect}")

    if notable_opponent_moves:
        lines.append("")
        lines.append("**Key Opponent Moves:**")
        for effect in notable_opponent_moves[:5]:  # Limit output
            lines.append(f"- {effect}")

    return "\n".join(lines)


def _get_move_effect_summary(move: Move) -> Optional[str]:
    """Get a summary of notable move effects from poke-env properties + curated data."""
    effects = []

    # Check curated effect first
    curated = get_move_effect(move.id)
    if curated:
        return curated

    # Build from poke-env properties
    if move.status:
        effects.append(f"inflicts {move.status.name}")

    if move.drain:
        effects.append(f"drains {int(move.drain * 100)}% of damage")

    if move.recoil:
        effects.append(f"{int(move.recoil * 100)}% recoil")

    if move.heal:
        effects.append(f"heals {int(move.heal * 100)}% HP")

    if move.force_switch:
        effects.append("forces switch")

    if move.priority != 0:
        effects.append(f"priority {'+' if move.priority > 0 else ''}{move.priority}")

    if move.breaks_protect:
        effects.append("breaks Protect")

    if move.weather:
        effects.append(f"sets {move.weather.name}")

    if move.terrain:
        effects.append(f"sets {move.terrain.name}")

    if effects:
        # Log that we're using poke-env fallback (curated entry missing)
        logger.debug(f"Using poke-env fallback for move: {move.id}")
        return "; ".join(effects)

    # No effect info available from either source
    # Only log for moves that might have notable effects (not basic damage moves)
    if move.base_power == 0 or move.category.name == "STATUS":
        logger.warning(f"Missing move effect: {move.id}")

    return None
