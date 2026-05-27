"""Fetch opponent sets node - retrieves stat-spread data for opponent Pokemon."""

import logging
from typing import Any

from ..state import AgentState

logger = logging.getLogger(__name__)


def fetch_opponent_sets_node(state: AgentState) -> dict:
    """
    Fetch spread/move/item/ability data for all seen opponent Pokemon via
    the meta-aware StatsResolver. In random battles this returns the same
    randbats-derived data as before; in OU/customgame it uses curated
    Smogon-common spreads.

    Returns only the fields this node modifies to avoid concurrent write issues.
    """
    battle = state.get("battle_object")
    if not battle:
        logger.warning("No battle object in state, skipping fetch_sets")
        return {"opponent_sets": {}}

    try:
        from src.config import Config
        from src.data import get_randbats_data
        from src.stats import make_resolver

        teams_state = state.get("teams_state")
        resolver = (
            teams_state.stats_resolver
            if teams_state is not None
            else make_resolver(Config.BATTLE_FORMAT, get_randbats_data())
        )

        opponent_sets: dict[str, Any] = {}

        for _pokemon_id, pokemon in battle.opponent_team.items():
            species = pokemon.species
            spread = resolver.get_spread(pokemon, is_opponent=True)

            opponent_sets[species] = {
                "species": species,
                "possible_moves": set(spread.possible_moves),
                "possible_items": list(spread.possible_items),
                "possible_abilities": list(spread.possible_abilities),
                "evs": dict(spread.evs),
                "ivs": dict(spread.ivs),
                "nature": spread.nature,
                "level": spread.level,
                # Track what we've actually seen
                "revealed_moves": list(pokemon.moves.keys()) if pokemon.moves else [],
                "revealed_item": pokemon.item if pokemon.item else None,
                "revealed_ability": pokemon.ability if pokemon.ability else None,
            }

            logger.debug(
                "Fetched sets for %s: %d possible_moves, %d possible_items",
                species,
                len(opponent_sets[species]["possible_moves"]),
                len(opponent_sets[species]["possible_items"]),
            )

        logger.info(f"Fetched opponent sets for {len(opponent_sets)} Pokemon")
        return {"opponent_sets": opponent_sets}

    except Exception as e:
        logger.error(f"Failed to fetch opponent sets: {e}", exc_info=True)
        return {"opponent_sets": {}}
