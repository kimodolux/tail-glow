"""Format battle log from poke-env observations for LLM consumption."""

import logging
from typing import Optional

from poke_env.battle import Battle

logger = logging.getLogger(__name__)


def format_battle_log(
    battle: Battle,
    turn_reasoning: dict[int, str],
    n_turns: int = 5,
) -> str:
    """Format recent battle history for LLM consumption.

    Uses poke-env's built-in battle.observations for events,
    combines with our stored reasoning for each turn.

    Args:
        battle: The poke-env Battle object
        turn_reasoning: Dict mapping turn number to our AI's reasoning
        n_turns: Number of recent turns to include

    Returns:
        Formatted battle log string for LLM prompt
    """
    if not battle.observations:
        return "No battle history yet (Turn 1)."

    # Get the last n turns (excluding current turn which hasn't happened yet)
    available_turns = sorted(battle.observations.keys())
    # Filter to turns before the current turn
    past_turns = [t for t in available_turns if t < battle.turn]
    recent_turns = past_turns[-n_turns:] if past_turns else []

    if not recent_turns:
        return "No battle history yet (Turn 1)."

    lines = ["## Recent Battle History"]

    for turn in recent_turns:
        obs = battle.observations[turn]
        turn_lines = _format_turn(turn, obs, turn_reasoning.get(turn), battle)
        lines.extend(turn_lines)
        lines.append("")  # Blank line between turns

    return "\n".join(lines)


def _format_turn(
    turn: int,
    obs,
    reasoning: Optional[str],
    battle: Battle,
) -> list[str]:
    """Format a single turn's events.

    Args:
        turn: Turn number
        obs: Observation object for this turn
        reasoning: Our AI's reasoning for this turn (if available)
        battle: The battle object for context

    Returns:
        List of formatted lines for this turn
    """
    lines = []

    # Get Pokemon names for the matchup header
    our_pokemon = "Unknown"
    their_pokemon = "Unknown"

    if obs.active_pokemon:
        our_pokemon = _format_pokemon_name(obs.active_pokemon.species)
        if obs.active_pokemon.status:
            our_pokemon += f" [{obs.active_pokemon.status.name.upper()}]"

    if obs.opponent_active_pokemon:
        their_pokemon = _format_pokemon_name(obs.opponent_active_pokemon.species)
        if obs.opponent_active_pokemon.status:
            their_pokemon += f" [{obs.opponent_active_pokemon.status.name.upper()}]"

    lines.append(f"**Turn {turn}** ({our_pokemon} vs {their_pokemon})")

    # Parse events to find what happened
    our_action, their_action, damage_info = _parse_events(obs.events, battle)

    if our_action:
        action_str = f"- We {our_action}"
        if damage_info.get("dealt"):
            action_str += f" (dealt ~{damage_info['dealt']}%)"
        lines.append(action_str)

    if their_action:
        action_str = f"- They {their_action}"
        if damage_info.get("received"):
            action_str += f" (we took ~{damage_info['received']}%)"
        lines.append(action_str)

    if reasoning:
        lines.append(f'- Our reasoning: "{reasoning}"')

    return lines


def _parse_events(
    events: list[list[str]],
    battle: Battle,
) -> tuple[Optional[str], Optional[str], dict]:
    """Parse raw Showdown protocol events to extract actions.

    Args:
        events: List of raw event messages (each is a list of strings)
        battle: Battle object for determining which player is us

    Returns:
        (our_action, their_action, damage_info)
    """
    our_action = None
    their_action = None
    damage_info = {"dealt": None, "received": None}

    # Determine our player identifier (p1 or p2)
    our_player = "p1" if battle.player_role == "p1" else "p2"
    their_player = "p2" if our_player == "p1" else "p1"

    for event in events:
        if len(event) < 2:
            continue

        # Events have empty string prefix: ['', 'move', 'p1a: Pokemon', 'MoveName', ...]
        event_type = event[1] if len(event) > 1 else event[0]

        if event_type == "move":
            # Format: ['', 'move', 'p1a: Pokemon', 'MoveName', ...]
            if len(event) >= 4:
                actor = event[2]
                move_name = event[3]
                if actor.startswith(our_player):
                    our_action = f"used: {_format_move_name(move_name)}"
                elif actor.startswith(their_player):
                    their_action = f"used: {_format_move_name(move_name)}"

        elif event_type in ("switch", "drag"):
            # Format: ['', 'switch', 'p1a: Pokemon', 'PokemonName', '100/100']
            if len(event) >= 4:
                actor = event[2]
                species = event[3].split(",")[0]  # Remove level/gender info
                if actor.startswith(our_player):
                    our_action = f"switched to: {_format_pokemon_name(species)}"
                elif actor.startswith(their_player):
                    their_action = f"switched to: {_format_pokemon_name(species)}"

        elif event_type == "-damage":
            # Format: ['', '-damage', 'p1a: Pokemon', '50/100', ...]
            if len(event) >= 4:
                target = event[2]
                hp_str = event[3]
                damage_pct = _parse_damage(hp_str)
                if damage_pct is not None:
                    if target.startswith(our_player):
                        damage_info["received"] = damage_pct
                    elif target.startswith(their_player):
                        damage_info["dealt"] = damage_pct

    return our_action, their_action, damage_info


def _parse_damage(hp_str: str) -> Optional[int]:
    """Parse HP string to get approximate damage percentage.

    Args:
        hp_str: HP string like "50/100" or "0 fnt"

    Returns:
        Estimated damage percentage, or None if can't parse
    """
    try:
        if "fnt" in hp_str:
            return 100  # Fainted = took remaining HP
        if "/" in hp_str:
            # Format: "current/max" or just percentage
            parts = hp_str.split("/")
            if len(parts) == 2:
                current = int(parts[0].split()[0])  # Handle "50/100 par" format
                max_hp = int(parts[1].split()[0])
                # This is current HP, not damage - we'd need previous HP to calc damage
                # For now, just return None as we can't easily calculate delta
                return None
        return None
    except (ValueError, IndexError):
        return None


def _format_pokemon_name(species: str) -> str:
    """Format Pokemon species name for display."""
    return species.replace("-", " ").title()


def _format_move_name(move: str) -> str:
    """Format move name for display."""
    return move.replace("-", " ").title()
