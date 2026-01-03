"""Fetch opponent sets node - retrieves randbats data for opponent Pokemon."""

import logging
from typing import Any

from ..state import AgentState

logger = logging.getLogger(__name__)


def fetch_opponent_sets_node(state: AgentState) -> dict:
    """
    Fetch randbats data for all seen opponent Pokemon.
    Stores possible moves, items, abilities, and tera types in state.
    Returns only the fields this node modifies to avoid concurrent write issues.
    """
    battle = state.get("battle_object")
    if not battle:
        logger.warning("No battle object in state, skipping fetch_sets")
        return {"opponent_sets": {}}

    try:
        from src.data import get_randbats_data

        randbats_data = get_randbats_data()
        if not randbats_data:
            logger.warning("No randbats data available")
            return {"opponent_sets": {}}

        opponent_sets: dict[str, Any] = {}

        # Fetch data for all seen opponent Pokemon
        for pokemon_id, pokemon in battle.opponent_team.items():
            species = pokemon.species

            set_data = {
                "species": species,
                "possible_moves": randbats_data.get_possible_moves(species),
                "possible_items": randbats_data.get_possible_items(species),
                "possible_abilities": randbats_data.get_possible_abilities(species),
                "evs": randbats_data.get_evs(species),
                "ivs": randbats_data.get_ivs(species),
                "level": randbats_data.get_level(species),
                # Track what we've actually seen
                "revealed_moves": list(pokemon.moves.keys()) if pokemon.moves else [],
                "revealed_item": pokemon.item if pokemon.item else None,
                "revealed_ability": pokemon.ability if pokemon.ability else None,
            }

            opponent_sets[species] = set_data

            logger.debug(
                f"Fetched sets for {species}: "
                f"{len(set_data['possible_moves'])} moves, "
                f"{len(set_data['possible_items'])} items"
            )

        logger.info(f"Fetched opponent sets for {len(opponent_sets)} Pokemon")
        return {"opponent_sets": opponent_sets}

    except Exception as e:
        logger.error(f"Failed to fetch opponent sets: {e}", exc_info=True)
        return {"opponent_sets": {}}
