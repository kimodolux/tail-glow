"""Battle memory node - tracks battle history and updates strategy.

Runs after parse_decision to record what happened and analyze the battle progress.
"""

import logging
from typing import Any, Optional

from poke_env.battle import Battle, Pokemon

from src.agent.state import AgentState
from src.agent.prompts.battle_memory import (
    BATTLE_MEMORY_SYSTEM_PROMPT,
    build_battle_memory_prompt,
)
from src.llm import get_llm_provider

logger = logging.getLogger(__name__)


def battle_memory_node(state: AgentState) -> dict[str, Any]:
    """Update battle memory with this turn's events and analysis.

    Tracks:
    - Turn-by-turn log of actions
    - Fainted Pokemon on each side
    - Revealed opponent information (moves, items, abilities)
    - Strategic analysis of battle progress

    Args:
        state: Current agent state after parse_decision

    Returns:
        Dict with battle_log, battle_analysis, and revealed_sets
    """
    battle: Optional[Battle] = state.get("battle_object")
    if not battle:
        return {}

    try:
        # Update battle log
        turn_log = _build_turn_log(state)
        previous_log = state.get("battle_log", "")
        battle_log = _append_to_log(previous_log, turn_log, battle.turn)

        # Update revealed sets tracking
        revealed_sets = _update_revealed_sets(
            battle=battle,
            previous_revealed=state.get("revealed_sets", {}),
            opponent_sets=state.get("opponent_sets", {}),
        )

        # Run LLM analysis
        battle_analysis = _run_analysis(
            state=state,
            battle=battle,
            battle_log=battle_log,
            turn_log=turn_log,
            revealed_sets=revealed_sets,
        )

        return {
            "battle_log": battle_log,
            "battle_analysis": battle_analysis,
            "revealed_sets": revealed_sets,
        }

    except Exception as e:
        logger.error(f"Battle memory update failed: {e}", exc_info=True)
        return {}


def _build_turn_log(state: AgentState) -> str:
    """Build a log entry for this turn's action."""
    action_type = state.get("action_type")
    action_target = state.get("action_target")
    battle: Battle = state.get("battle_object")

    if not action_type or not action_target:
        return "No action recorded"

    our_pokemon = battle.active_pokemon.species if battle.active_pokemon else "Unknown"
    their_pokemon = battle.opponent_active_pokemon.species if battle.opponent_active_pokemon else "Unknown"

    if action_type == "move":
        move_name = action_target.replace("-", " ").title()
        return f"{our_pokemon} used {move_name} vs {their_pokemon}"
    else:
        return f"Switched to {action_target} (opponent: {their_pokemon})"


def _append_to_log(previous_log: str, turn_log: str, turn: int) -> str:
    """Append turn log to battle history."""
    entry = f"Turn {turn}: {turn_log}"

    if previous_log:
        return f"{previous_log}\n{entry}"
    return entry


def _update_revealed_sets(
    battle: Battle,
    previous_revealed: dict[str, dict[str, Any]],
    opponent_sets: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Update tracking of revealed opponent information."""
    revealed = dict(previous_revealed)  # Copy previous

    for pokemon in battle.opponent_team.values():
        species = pokemon.species
        if species not in revealed:
            revealed[species] = {
                "revealed_moves": [],
                "revealed_item": None,
                "deduced_item": None,
                "revealed_ability": None,
                "fainted": False,
            }

        entry = revealed[species]

        # Update revealed moves
        if pokemon.moves:
            for move_id in pokemon.moves.keys():
                if move_id not in entry["revealed_moves"]:
                    entry["revealed_moves"].append(move_id)

        # Update revealed item
        if pokemon.item and pokemon.item not in ["", "unknown"]:
            entry["revealed_item"] = pokemon.item

        # Update revealed ability
        if pokemon.ability:
            entry["revealed_ability"] = pokemon.ability

        # Update fainted status
        if pokemon.fainted:
            entry["fainted"] = True

        # Deduce items based on behavior
        if not entry["revealed_item"] and not entry["deduced_item"]:
            deduced = _deduce_item(pokemon, opponent_sets)
            if deduced:
                entry["deduced_item"] = deduced

    return revealed


def _deduce_item(pokemon: Pokemon, opponent_sets: dict[str, Any]) -> Optional[str]:
    """Try to deduce opponent's item based on observed behavior."""
    # This would need battle history to properly implement
    # For now, just check if we can narrow down based on randbats data

    species_key = pokemon.species.lower().replace(" ", "").replace("-", "")
    if species_key not in opponent_sets:
        return None

    possible_items = opponent_sets[species_key].get("possible_items", [])

    # If only one possible item, we know what it is
    if len(possible_items) == 1:
        return possible_items[0]

    # Could add more deduction logic here:
    # - No Leftovers recovery after a turn -> not Leftovers
    # - Speed tier indicates Choice Scarf
    # - Damage output indicates Choice Band/Specs
    # - etc.

    return None


def _run_analysis(
    state: AgentState,
    battle: Battle,
    battle_log: str,
    turn_log: str,
    revealed_sets: dict[str, dict[str, Any]],
) -> Optional[str]:
    """Run LLM analysis of battle progress."""
    # Skip analysis on turn 1 (nothing to analyze yet)
    if battle.turn <= 1:
        return None

    try:
        # Gather context
        battle_strategy = state.get("battle_strategy", "")
        previous_analysis = state.get("battle_analysis", "")

        # Get fainted Pokemon
        our_fainted = [p.species for p in battle.team.values() if p.fainted]
        their_fainted = [p.species for p in battle.opponent_team.values() if p.fainted]

        # Format revealed sets
        revealed_str = _format_revealed_sets(revealed_sets)

        # Current state summary
        current_state = _format_current_state(battle)

        # Build prompt
        prompt = build_battle_memory_prompt(
            battle_strategy=battle_strategy,
            previous_analysis=previous_analysis,
            battle_log=battle_log,
            turn_events=turn_log,
            our_fainted=", ".join(our_fainted) if our_fainted else "None",
            their_fainted=", ".join(their_fainted) if their_fainted else "None",
            revealed_sets=revealed_str,
            current_state=current_state,
            turn_number=battle.turn,
        )

        # Call LLM
        llm = get_llm_provider()
        username = state.get("username")

        response = llm.generate(
            BATTLE_MEMORY_SYSTEM_PROMPT,
            prompt,
            user=username,
        )

        return response.strip()

    except Exception as e:
        logger.error(f"Battle analysis failed: {e}", exc_info=True)
        return previous_analysis  # Keep previous if failed


def _format_revealed_sets(revealed_sets: dict[str, dict[str, Any]]) -> str:
    """Format revealed sets for the prompt."""
    if not revealed_sets:
        return "No information revealed yet"

    lines = []
    for species, info in revealed_sets.items():
        parts = [f"**{species}**"]

        moves = info.get("revealed_moves", [])
        if moves:
            move_str = ", ".join(m.replace("-", " ").title() for m in moves)
            parts.append(f"Moves: {move_str}")

        item = info.get("revealed_item") or info.get("deduced_item")
        if item:
            deduced = " (deduced)" if info.get("deduced_item") and not info.get("revealed_item") else ""
            parts.append(f"Item: {item}{deduced}")

        ability = info.get("revealed_ability")
        if ability:
            parts.append(f"Ability: {ability}")

        if info.get("fainted"):
            parts.append("(FAINTED)")

        lines.append(" | ".join(parts))

    return "\n".join(lines)


def _format_current_state(battle: Battle) -> str:
    """Format current game state summary."""
    lines = []

    # Our team status
    lines.append("**Your Team:**")
    for pokemon in battle.team.values():
        hp = f"{pokemon.current_hp_fraction * 100:.0f}%" if not pokemon.fainted else "Fainted"
        status = f" ({pokemon.status.name})" if pokemon.status else ""
        active = " (active)" if pokemon.active else ""
        lines.append(f"- {pokemon.species}: {hp}{status}{active}")

    # Their team status
    lines.append("")
    lines.append("**Opponent's Team:**")
    for pokemon in battle.opponent_team.values():
        hp = f"{pokemon.current_hp_fraction * 100:.0f}%" if not pokemon.fainted else "Fainted"
        status = f" ({pokemon.status.name})" if pokemon.status else ""
        active = " (active)" if pokemon.active else ""
        lines.append(f"- {pokemon.species}: {hp}{status}{active}")

    return "\n".join(lines)


def format_battle_memory(
    battle_log: Optional[str],
    battle_analysis: Optional[str],
) -> str:
    """Format battle memory for the decision node.

    Args:
        battle_log: Turn-by-turn history
        battle_analysis: Strategic analysis

    Returns:
        Formatted string for LLM consumption
    """
    lines = ["## Battle Context"]
    lines.append("")

    if battle_analysis:
        lines.append("### Strategic Analysis")
        lines.append(battle_analysis)
        lines.append("")

    if battle_log:
        lines.append("### Recent History")
        # Show last 5 turns
        log_lines = battle_log.strip().split("\n")
        recent = log_lines[-5:] if len(log_lines) > 5 else log_lines
        for line in recent:
            lines.append(f"- {line}")

    return "\n".join(lines) if len(lines) > 2 else ""
