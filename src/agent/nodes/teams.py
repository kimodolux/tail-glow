"""Teams state update node for battle graph."""

import logging

from ..state import AgentState
from src.battle import TeamsState
from src.data import get_randbats_data

logger = logging.getLogger(__name__)


def update_teams_state_node(state: AgentState) -> dict:
    """
    Update the teams state with current battle information.

    Creates TeamsState on first turn, then updates it each turn with:
    - New Pokemon seen (calculates and caches their stats)
    - Revealed moves, abilities, items
    - Current HP, status, boosts

    Returns only the fields this node modifies.
    """
    battle = state.get("battle_object")
    if not battle:
        logger.warning("No battle object in state, skipping teams state update")
        return {}

    try:
        # Get or create TeamsState
        teams_state = state.get("teams_state")

        if teams_state is None:
            # First turn - create new TeamsState
            logger.info("Creating new TeamsState for battle")
            teams_state = TeamsState(gen=9, randbats_data=get_randbats_data())

        # Update from current battle state
        teams_state.update_from_battle(battle)

        # Log what we know
        our_count = len(teams_state.our_team)
        their_count = len(teams_state.their_team)
        logger.info(f"TeamsState updated: {our_count} our Pokemon, {their_count} opponent Pokemon tracked")

        # Log revealed info for opponent
        for species, poke_state in teams_state.their_team.items():
            revealed_moves = len(poke_state.revealed_moves)
            total_possible = len(poke_state.possible_moves)
            ability_str = poke_state.revealed_ability or "unknown"
            item_str = poke_state.revealed_item or "unknown"
            logger.debug(
                f"  {species}: {revealed_moves}/{total_possible} moves revealed, "
                f"ability={ability_str}, item={item_str}"
            )

        return {"teams_state": teams_state}

    except Exception as e:
        logger.error(f"Teams state update failed: {e}", exc_info=True)
        return {}
