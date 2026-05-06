"""Parse battle events from poke-env observations into structured data."""

import logging
from dataclasses import dataclass, field
from typing import Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ParsedTurnEvent:
    """Structured representation of what happened in a single turn."""

    turn: int

    # Our action
    our_action: str  # "move:Earthquake" or "switch:Garchomp"
    our_pokemon: str  # Who was active

    # Opponent action
    opponent_action: str  # "move:Ice Beam" or "switch:Weavile" or "unknown"
    opponent_pokemon: str  # Who was active

    # Outcomes
    damage_dealt: Optional[int] = None  # % damage we dealt
    damage_taken: Optional[int] = None  # % damage we took
    our_ko: Optional[str] = None  # Pokemon we KO'd (if any)
    their_ko: Optional[str] = None  # Pokemon they KO'd (if any)

    # State changes
    status_inflicted: Optional[str] = None
    status_received: Optional[str] = None
    boosts_gained: dict[str, int] = field(default_factory=dict)
    boosts_opponent: dict[str, int] = field(default_factory=dict)


def parse_turn_observation(obs: Any, battle: Any, turn: int) -> Optional[ParsedTurnEvent]:
    """
    Parse a poke-env observation into a structured TurnEvent.

    Args:
        obs: Observation object for the turn (battle.observations[turn])
        battle: Battle object for context (player role, etc.)
        turn: Turn number

    Returns:
        ParsedTurnEvent with structured data, or None if parsing fails
    """
    if obs is None:
        return None

    our_player = "p1" if battle.player_role == "p1" else "p2"
    their_player = "p2" if our_player == "p1" else "p1"
    logger.debug(f"Player roles: our={our_player}, their={their_player}, battle.player_role={battle.player_role}")

    # Get active Pokemon names
    our_pokemon = "unknown"
    opponent_pokemon = "unknown"

    if obs.active_pokemon:
        our_pokemon = obs.active_pokemon.species

    if obs.opponent_active_pokemon:
        opponent_pokemon = obs.opponent_active_pokemon.species

    # Parse events
    our_actions = []
    their_actions = []
    our_fainted = None
    their_fainted = None
    boosts_gained = {}
    boosts_opponent = {}
    status_inflicted = None
    status_received = None

    # Check if observation has events attribute
    events = getattr(obs, 'events', None)
    if events is None:
        logger.warning(f"Observation has no 'events' attribute, type={type(obs)}")
        # Return with unknown actions
        return ParsedTurnEvent(
            turn=turn,
            our_action="unknown",
            our_pokemon=our_pokemon,
            opponent_action="unknown",
            opponent_pokemon=opponent_pokemon,
        )

    logger.debug(f"Parsing {len(events)} events for turn {turn}")

    for event in events:
        if len(event) < 2:
            continue

        # Events have empty string prefix, so actual type is at index 1
        # Format: ['', 'move', 'p1a: Pokemon', 'MoveName', ...]
        event_type = event[1] if len(event) > 1 else event[0]

        # Move events
        if event_type == "move":
            if len(event) >= 4:
                actor = event[2]
                move_name = event[3]
                if actor.startswith(our_player):
                    our_actions.append(f"move:{move_name}")
                elif actor.startswith(their_player):
                    their_actions.append(f"move:{move_name}")

        # Switch events
        elif event_type in ("switch", "drag"):
            if len(event) >= 4:
                actor = event[2]
                species = event[3].split(",")[0]
                if actor.startswith(our_player):
                    our_actions.append(f"switch:{species}")
                elif actor.startswith(their_player):
                    their_actions.append(f"switch:{species}")

        # Faint events: ['', 'faint', 'p1a: Pokemon']
        elif event_type == "faint":
            if len(event) >= 3:
                actor = event[2]
                if actor.startswith(our_player):
                    their_fainted = our_pokemon  # We got KO'd
                elif actor.startswith(their_player):
                    our_fainted = opponent_pokemon  # We KO'd them

        # Boost events: ['', '-boost', 'p1a: Pokemon', 'atk', '2']
        elif event_type == "-boost":
            if len(event) >= 5:
                actor = event[2]
                stat = event[3]
                try:
                    amount = int(event[4])
                except ValueError:
                    amount = 1
                if actor.startswith(our_player):
                    boosts_gained[stat] = boosts_gained.get(stat, 0) + amount
                elif actor.startswith(their_player):
                    boosts_opponent[stat] = boosts_opponent.get(stat, 0) + amount

        # Unboost events: ['', '-unboost', 'p1a: Pokemon', 'atk', '2']
        elif event_type == "-unboost":
            if len(event) >= 5:
                actor = event[2]
                stat = event[3]
                try:
                    amount = int(event[4])
                except ValueError:
                    amount = 1
                if actor.startswith(our_player):
                    boosts_gained[stat] = boosts_gained.get(stat, 0) - amount
                elif actor.startswith(their_player):
                    boosts_opponent[stat] = boosts_opponent.get(stat, 0) - amount

        # Status events: ['', '-status', 'p1a: Pokemon', 'brn']
        elif event_type == "-status":
            if len(event) >= 4:
                actor = event[2]
                status = event[3]
                if actor.startswith(our_player):
                    status_received = status
                elif actor.startswith(their_player):
                    status_inflicted = status

    # Calculate damage from HP changes
    damage_dealt = None
    damage_taken = None

    # Get HP at end of turn
    if obs.opponent_active_pokemon and not our_fainted:
        # We can estimate damage dealt based on current HP
        # Note: This is approximate - actual damage tracking would need start/end HP
        pass

    # Build action strings
    our_action = our_actions[0] if our_actions else "unknown"
    opponent_action = their_actions[0] if their_actions else "unknown"

    logger.debug(f"Parsed turn {turn}: our={our_action}, opp={opponent_action}")

    return ParsedTurnEvent(
        turn=turn,
        our_action=our_action,
        our_pokemon=our_pokemon,
        opponent_action=opponent_action,
        opponent_pokemon=opponent_pokemon,
        damage_dealt=damage_dealt,
        damage_taken=damage_taken,
        our_ko=our_fainted,  # Pokemon we KO'd
        their_ko=their_fainted,  # Pokemon we lost
        status_inflicted=status_inflicted,
        status_received=status_received,
        boosts_gained=boosts_gained,
        boosts_opponent=boosts_opponent,
    )


def format_turn_events_for_analysis(obs: Any, battle: Any) -> str:
    """
    Format turn events as human-readable string for LLM analysis.

    This is used by turn_analysis node for mistake detection.
    Extracted from original turn_analysis.py logic.

    Args:
        obs: Observation object for the turn
        battle: Battle object for context

    Returns:
        Formatted description of turn events
    """
    lines = []

    # Matchup
    our_pokemon = "Unknown"
    their_pokemon = "Unknown"

    if obs.active_pokemon:
        our_pokemon = obs.active_pokemon.species
        if obs.active_pokemon.status:
            our_pokemon += f" [{obs.active_pokemon.status.name}]"

    if obs.opponent_active_pokemon:
        their_pokemon = obs.opponent_active_pokemon.species
        if obs.opponent_active_pokemon.status:
            their_pokemon += f" [{obs.opponent_active_pokemon.status.name}]"

    lines.append(f"Matchup: {our_pokemon} vs {their_pokemon}")

    # Parse events
    our_player = "p1" if battle.player_role == "p1" else "p2"
    their_player = "p2" if our_player == "p1" else "p1"

    our_actions = []
    their_actions = []
    fainted = []
    boosts = []

    for event in obs.events:
        if len(event) < 2:
            continue

        # Events have empty string prefix: ['', 'move', 'p1a: Pokemon', 'MoveName', ...]
        event_type = event[1] if len(event) > 1 else event[0]

        if event_type == "move":
            if len(event) >= 4:
                actor = event[2]
                move_name = event[3]
                if actor.startswith(our_player):
                    our_actions.append(f"used {move_name}")
                elif actor.startswith(their_player):
                    their_actions.append(f"used {move_name}")

        elif event_type in ("switch", "drag"):
            if len(event) >= 4:
                actor = event[2]
                species = event[3].split(",")[0]
                if actor.startswith(our_player):
                    our_actions.append(f"switched to {species}")
                elif actor.startswith(their_player):
                    their_actions.append(f"switched to {species}")

        elif event_type == "faint":
            if len(event) >= 3:
                actor = event[2]
                if actor.startswith(our_player):
                    fainted.append("Our Pokemon fainted")
                elif actor.startswith(their_player):
                    fainted.append("Their Pokemon fainted")

        elif event_type == "-boost":
            if len(event) >= 5:
                actor = event[2]
                stat = event[3]
                amount = event[4]
                if actor.startswith(their_player):
                    boosts.append(f"Opponent boosted {stat} by {amount}")

    if our_actions:
        lines.append(f"Our action: {', '.join(our_actions)}")
    if their_actions:
        lines.append(f"Their action: {', '.join(their_actions)}")
    if fainted:
        lines.append(f"Faints: {', '.join(fainted)}")
    if boosts:
        lines.append(f"Boosts: {', '.join(boosts)}")

    return "\n".join(lines)


def determine_turn_outcome(obs: Any, battle: Any) -> str:
    """
    Determine the outcome of a turn.

    Extracted from original turn_analysis.py logic.

    Args:
        obs: Observation object for the turn
        battle: Battle object for context

    Returns:
        Description of the turn outcome
    """
    our_player = "p1" if battle.player_role == "p1" else "p2"
    their_player = "p2" if our_player == "p1" else "p1"

    outcomes = []

    our_fainted = False
    their_fainted = False

    for event in obs.events:
        if len(event) < 2:
            continue

        # Events have empty string prefix: ['', 'faint', 'p1a: Pokemon']
        event_type = event[1] if len(event) > 1 else event[0]

        if event_type == "faint":
            if len(event) >= 3:
                actor = event[2]
                if actor.startswith(our_player):
                    our_fainted = True
                elif actor.startswith(their_player):
                    their_fainted = True

    if our_fainted and their_fainted:
        outcomes.append("Both Pokemon fainted (trade)")
    elif our_fainted:
        outcomes.append("Our Pokemon was KO'd")
    elif their_fainted:
        outcomes.append("Their Pokemon was KO'd")

    # Check current HP if available
    if obs.active_pokemon and not our_fainted:
        hp_pct = obs.active_pokemon.current_hp_fraction * 100
        outcomes.append(f"Our Pokemon at {hp_pct:.0f}% HP")

    if obs.opponent_active_pokemon and not their_fainted:
        # Opponent HP is estimated
        hp_pct = obs.opponent_active_pokemon.current_hp_fraction * 100
        outcomes.append(f"Their Pokemon at ~{hp_pct:.0f}% HP")

    return "; ".join(outcomes) if outcomes else "Turn completed normally"
