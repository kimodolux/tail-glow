"""Game-end analysis node - Analyzes completed battles for learnings.

Called after a battle ends to extract matchup knowledge and mistakes
that should be stored for future reference.
"""

import logging
from typing import Optional

from poke_env.battle import Battle

from ..prompts.game_analysis import (
    GAME_ANALYSIS_SYSTEM_PROMPT,
    build_game_analysis_prompt,
    parse_game_analysis_response,
)
from src.llm import get_llm_provider
from src.rag.models import (
    GameSummary,
    MatchupLearning,
    MistakeLearning,
    SetContext,
)
from src.rag import get_strategy_store

logger = logging.getLogger(__name__)


async def analyze_game_end(
    battle: Battle,
    battle_context: dict,
    username: str,
) -> Optional[GameSummary]:
    """Analyze a completed battle and extract learnings.

    This is called from _battle_finished_callback in the client.

    Args:
        battle: The completed poke-env Battle object
        battle_context: Stored context including team_analysis, turn_reasoning, etc.
        username: Player username for tracing

    Returns:
        GameSummary with extracted learnings, or None on failure
    """
    try:
        # Build complete battle history
        battle_history = _build_full_battle_history(battle, battle_context)

        # Get accumulated mistakes from during the game
        accumulated_mistakes = battle_context.get("accumulated_mistakes", [])

        # Build prompt
        user_prompt = build_game_analysis_prompt(
            won=battle.won,
            team_analysis=battle_context.get("team_analysis"),
            battle_history=battle_history,
            accumulated_mistakes=accumulated_mistakes,
        )

        # Call LLM
        llm = get_llm_provider()

        response = llm.generate(
            GAME_ANALYSIS_SYSTEM_PROMPT,
            user_prompt,
            user=username,
            generation_name="game_analysis",
        )

        # Parse response
        parsed = parse_game_analysis_response(response)

        # Create GameSummary
        summary = _create_game_summary(
            parsed=parsed,
            battle=battle,
            accumulated_mistakes=accumulated_mistakes,
        )

        # Store learnings in RAG
        if summary:
            await _store_learnings(summary)
            logger.info(
                f"Game analysis complete: {len(summary.matchups_learned)} matchups, "
                f"{len(summary.mistakes_made)} mistakes. Key lesson: {summary.key_lesson}"
            )

        return summary

    except Exception as e:
        logger.error(f"Game analysis failed: {e}", exc_info=True)
        return None


def _build_full_battle_history(battle: Battle, battle_context: dict) -> str:
    """Build complete battle history from observations.

    Args:
        battle: The battle object
        battle_context: Context including turn reasoning

    Returns:
        Formatted battle history string
    """
    lines = ["## Complete Battle History"]

    turn_reasoning = battle_context.get("turn_reasoning", {})

    for turn in sorted(battle.observations.keys()):
        obs = battle.observations[turn]

        # Format turn header
        our_pokemon = "Unknown"
        their_pokemon = "Unknown"

        if obs.active_pokemon:
            our_pokemon = obs.active_pokemon.species
        if obs.opponent_active_pokemon:
            their_pokemon = obs.opponent_active_pokemon.species

        lines.append(f"\n### Turn {turn}: {our_pokemon} vs {their_pokemon}")

        # Parse events
        our_player = "p1" if battle.player_role == "p1" else "p2"
        their_player = "p2" if our_player == "p1" else "p1"

        for event in obs.events:
            if len(event) < 2:
                continue

            event_type = event[0]

            if event_type == "move":
                if len(event) >= 3:
                    actor = event[1]
                    move = event[2]
                    who = "We" if actor.startswith(our_player) else "They"
                    lines.append(f"- {who} used {move}")

            elif event_type in ("switch", "drag"):
                if len(event) >= 3:
                    actor = event[1]
                    species = event[2].split(",")[0]
                    who = "We" if actor.startswith(our_player) else "They"
                    lines.append(f"- {who} switched to {species}")

            elif event_type == "faint":
                actor = event[1]
                who = "Our" if actor.startswith(our_player) else "Their"
                lines.append(f"- {who} Pokemon fainted")

            elif event_type == "-boost":
                if len(event) >= 4:
                    actor = event[1]
                    stat = event[2]
                    amount = event[3]
                    who = "We" if actor.startswith(our_player) else "They"
                    lines.append(f"- {who} boosted {stat} +{amount}")

        # Add our reasoning
        reasoning = turn_reasoning.get(turn)
        if reasoning:
            lines.append(f"- Our reasoning: \"{reasoning}\"")

    # Final state
    lines.append(f"\n### Result: {'WON' if battle.won else 'LOST'}")
    lines.append(f"- Pokemon remaining: Us {len([p for p in battle.team.values() if not p.fainted])}, "
                 f"Them {len([p for p in battle.opponent_team.values() if not p.fainted])}")

    return "\n".join(lines)


def _create_game_summary(
    parsed: dict,
    battle: Battle,
    accumulated_mistakes: list,
) -> GameSummary:
    """Create GameSummary from parsed analysis.

    Args:
        parsed: Parsed analysis response
        battle: Battle object
        accumulated_mistakes: Mistakes detected during game

    Returns:
        GameSummary object
    """
    # Determine format
    battle_format = battle.format if hasattr(battle, 'format') else "gen9randombattle"

    # Convert matchups
    matchup_learnings = []
    for m in parsed.get("matchups", []):
        set_context = SetContext(
            format=battle_format,
            role=m.get("our_role", "unknown"),
        )

        learning = MatchupLearning(
            pokemon=m.get("pokemon", "unknown"),
            our_role=m.get("our_role", "unknown"),
            our_set_context=set_context,
            opponent=m.get("opponent", "unknown"),
            opponent_role=m.get("opponent_role", "unknown"),
            outcome=m.get("outcome"),
            conditions=m.get("conditions", ""),
            lesson=m.get("lesson", ""),
            battle_id=battle.battle_tag,
        )
        matchup_learnings.append(learning)

    # Convert mistakes from parsed response
    mistake_learnings = []
    for m in parsed.get("mistakes", []):
        learning = MistakeLearning(
            mistake_type=m.get("mistake_type"),
            our_pokemon="unknown",  # Would need more context to determine
            our_role="unknown",
            opponent="unknown",
            opponent_role="unknown",
            context="",
            what_happened=m.get("what_happened", ""),
            better_play=m.get("better_play", ""),
            battle_id=battle.battle_tag,
            turn=m.get("turn", 0),
            format=battle_format,
        )
        mistake_learnings.append(learning)

    # Add accumulated mistakes from during the game
    mistake_learnings.extend(accumulated_mistakes)

    # Get turning points
    turning_points = []
    if parsed.get("turning_point"):
        tp = parsed["turning_point"]
        turning_points.append(f"Turn {tp.get('turn', '?')}: {tp.get('description', '')}")

    # Get summary info
    summary = parsed.get("summary", {})

    return GameSummary(
        battle_id=battle.battle_tag,
        won=battle.won,
        format=battle_format,
        matchups_learned=matchup_learnings,
        mistakes_made=mistake_learnings,
        turning_points=turning_points,
        win_condition_achieved=summary.get("reason") if battle.won else None,
        loss_reason=summary.get("reason") if not battle.won else None,
        key_lesson=summary.get("key_lesson", ""),
    )


async def _store_learnings(summary: GameSummary):
    """Store extracted learnings in ChromaDB.

    Args:
        summary: GameSummary with learnings to store
    """
    try:
        store = get_strategy_store()

        # Store matchup learnings
        for matchup in summary.matchups_learned:
            store.add_matchup_learning(matchup)

        # Store mistake learnings
        for mistake in summary.mistakes_made:
            store.add_mistake_learning(mistake)

        logger.debug(
            f"Stored {len(summary.matchups_learned)} matchups and "
            f"{len(summary.mistakes_made)} mistakes"
        )

    except Exception as e:
        logger.error(f"Failed to store learnings: {e}")
