"""Memory update node - Updates game memory with previous turn's events.

Runs at the start of each turn (after format_state) to:
1. Parse the previous turn's events from battle observations
2. Update GameMemory with structured event data
3. Track opponent patterns and prediction accuracy
"""

import logging

from ..state import AgentState
from src.battle.game_memory import GameMemory
from src.battle.event_parser import parse_turn_observation

logger = logging.getLogger(__name__)


def update_game_memory_node(state: AgentState) -> dict:
    """
    Update game memory with previous turn's events.

    Runs after format_state, before analysis nodes.
    Parses battle observations into structured TurnEvent and updates
    opponent pattern tracking.

    Args:
        state: Current agent state

    Returns:
        State update with game_memory field
    """
    battle = state.get("battle_object")
    turn = battle.turn if battle else 0

    # Get or create game memory
    game_memory: GameMemory = state.get("game_memory") or GameMemory()

    # Skip turn 1 (no previous turn to analyze)
    if turn <= 1:
        logger.debug("Turn 1 - initializing game memory")
        return {"game_memory": game_memory}

    previous_turn = turn - 1

    # Check if we have observations for the previous turn
    if previous_turn not in battle.observations:
        logger.debug(f"No observations for turn {previous_turn}")
        return {"game_memory": game_memory}

    # Check if we've already processed this turn
    existing_turns = [e.turn for e in game_memory.turn_events]
    if previous_turn in existing_turns:
        logger.debug(f"Turn {previous_turn} already in memory")
        return {"game_memory": game_memory}

    # Parse the previous turn's events
    obs = battle.observations[previous_turn]

    # Debug: Log observation structure
    logger.info(f"Memory node: parsing turn {previous_turn} observation")
    if hasattr(obs, 'events'):
        logger.info(f"  Observation has {len(obs.events)} events")
    else:
        logger.warning(f"  Observation has no 'events' attribute, type={type(obs)}")

    turn_event = parse_turn_observation(obs, battle, previous_turn)

    if turn_event:
        game_memory.add_turn_event(turn_event)
        logger.debug(
            f"Added turn {previous_turn} to memory: "
            f"{turn_event.our_action} vs {turn_event.opponent_action}"
        )

    # Log memory stats periodically
    if turn % 5 == 0:
        stats = game_memory.get_summary_stats()
        logger.info(f"Game memory stats at turn {turn}: {stats}")

    return {"game_memory": game_memory}
