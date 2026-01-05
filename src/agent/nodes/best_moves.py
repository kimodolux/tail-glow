"""Best move options node - deterministic move ranking.

Ranks available moves based on damage, KO potential, accuracy, and switch coverage.
"""

import logging
from typing import Any, Optional

from poke_env.battle import Battle, Move

from src.agent.state import AgentState
from src.damage_calc.calculator import MatchupResult, DamageResult

logger = logging.getLogger(__name__)


def best_moves_node(state: AgentState) -> dict[str, Any]:
    """Rank available moves based on damage and strategic value.

    Considers:
    - Damage to active opponent (KO potential)
    - Damage to potential switch-ins
    - Move accuracy
    - Choice lock status

    Args:
        state: Current agent state

    Returns:
        Dict with best_moves containing ranked moves and summary
    """
    battle: Optional[Battle] = state.get("battle_object")
    if not battle or not battle.active_pokemon:
        return {"best_moves": None}

    try:
        damage_calc_raw = state.get("damage_calc_raw", {})
        opponent_sets = state.get("opponent_sets", {})

        # Check if choice locked
        choice_locked, locked_move = _check_choice_lock(battle)

        if choice_locked and locked_move:
            result = _build_choice_locked_result(locked_move, damage_calc_raw, battle)
            return {"best_moves": result}

        # Rank all available moves
        ranked_moves = _rank_moves(battle, damage_calc_raw, opponent_sets)

        # Build summary
        summary = _build_summary(ranked_moves, battle)

        result = {
            "moves": ranked_moves,
            "choice_locked": False,
            "locked_move": None,
            "summary": summary,
        }

        return {"best_moves": result}

    except Exception as e:
        logger.error(f"Best moves calculation failed: {e}", exc_info=True)
        return {"best_moves": None}


def _check_choice_lock(battle: Battle) -> tuple[bool, Optional[str]]:
    """Check if we're locked into a move by Choice item."""
    pokemon = battle.active_pokemon

    # Check if we have a choice item
    if pokemon.item:
        item_lower = pokemon.item.lower().replace(" ", "")
        is_choice = item_lower in ["choiceband", "choicescarf", "choicespecs"]
    else:
        is_choice = False

    # Check if we've already used a move (would be locked)
    # In poke-env, if we're choice locked, available_moves will only have one move
    if is_choice and len(battle.available_moves) == 1:
        return True, battle.available_moves[0].id

    # Also check must_recharge or similar effects
    if battle.force_switch or len(battle.available_moves) == 0:
        return False, None

    return False, None


def _build_choice_locked_result(
    locked_move: str,
    damage_calc_raw: dict[str, Any],
    battle: Battle,
) -> dict[str, Any]:
    """Build result when choice locked into a single move."""
    # Get damage info for the locked move
    our_vs_active = damage_calc_raw.get("our_vs_active")
    damage_info = "Unknown damage"
    ko_info = ""

    if our_vs_active and our_vs_active.results:
        for result in our_vs_active.results:
            if result.move == locked_move:
                damage_info = f"{result.min_percent:.0f}-{result.max_percent:.0f}%"
                if result.ko_chance:
                    ko_info = f" ({result.ko_chance} KO)"
                break

    move_display = locked_move.replace("-", " ").title()
    summary = f"Choice locked into {move_display}: {damage_info}{ko_info}"

    return {
        "moves": [{
            "move": locked_move,
            "rank": 1,
            "damage_to_active": damage_info + ko_info,
            "damage_to_switches": "N/A (locked)",
            "accuracy": 100,  # Will be corrected if we have move data
            "reasoning": "Choice locked - only option available",
        }],
        "choice_locked": True,
        "locked_move": locked_move,
        "summary": summary,
    }


def _rank_moves(
    battle: Battle,
    damage_calc_raw: dict[str, Any],
    opponent_sets: dict[str, Any],
) -> list[dict[str, Any]]:
    """Rank available moves by effectiveness."""
    our_vs_active: Optional[MatchupResult] = damage_calc_raw.get("our_vs_active")
    our_vs_bench: list[MatchupResult] = damage_calc_raw.get("our_vs_bench", [])

    # Build move data
    move_scores = []

    for move in battle.available_moves:
        score_data = _calculate_move_score(
            move=move,
            our_vs_active=our_vs_active,
            our_vs_bench=our_vs_bench,
            opponent_active=battle.opponent_active_pokemon,
        )
        move_scores.append(score_data)

    # Sort by score descending
    move_scores.sort(key=lambda x: x["score"], reverse=True)

    # Build ranked result
    ranked = []
    for i, data in enumerate(move_scores, 1):
        ranked.append({
            "move": data["move"],
            "rank": i,
            "damage_to_active": data["damage_to_active"],
            "damage_to_switches": data["damage_to_switches"],
            "accuracy": data["accuracy"],
            "reasoning": data["reasoning"],
            "score": data["score"],  # Internal score for debugging
        })

    return ranked


def _calculate_move_score(
    move: Move,
    our_vs_active: Optional[MatchupResult],
    our_vs_bench: list[MatchupResult],
    opponent_active,
) -> dict[str, Any]:
    """Calculate a score and data for a single move."""
    move_id = move.id
    accuracy = move.accuracy if move.accuracy else 100

    # Find damage result for this move vs active
    active_damage = None
    damage_to_active = "No data"
    ko_chance = None

    if our_vs_active and our_vs_active.results:
        for result in our_vs_active.results:
            if result.move == move_id:
                active_damage = result
                damage_to_active = f"{result.min_percent:.0f}-{result.max_percent:.0f}%"
                ko_chance = result.ko_chance
                if ko_chance:
                    damage_to_active += f" ({ko_chance} KO)"
                break

    # Calculate damage vs bench Pokemon
    bench_damages = []
    for matchup in our_vs_bench:
        for result in matchup.results:
            if result.move == move_id:
                ko_str = f" ({result.ko_chance})" if result.ko_chance else ""
                bench_damages.append(
                    f"{matchup.defender}: {result.min_percent:.0f}-{result.max_percent:.0f}%{ko_str}"
                )
                break

    damage_to_switches = "; ".join(bench_damages[:3]) if bench_damages else "No bench data"

    # Calculate score
    score = 0.0

    if active_damage:
        # Base score from damage
        avg_damage = (active_damage.min_percent + active_damage.max_percent) / 2
        score = avg_damage

        # KO bonus
        if ko_chance == "guaranteed":
            score += 200  # Strong preference for guaranteed KO
        elif ko_chance:
            # Parse percentage KO chance
            try:
                ko_pct = float(ko_chance.replace("%", ""))
                score += ko_pct  # Add KO chance as bonus
            except ValueError:
                pass

        # Accuracy penalty
        if accuracy < 100:
            score *= (accuracy / 100)

    # Generate reasoning
    reasoning = _generate_move_reasoning(
        move=move,
        active_damage=active_damage,
        ko_chance=ko_chance,
        accuracy=accuracy,
        bench_damages=bench_damages,
    )

    return {
        "move": move_id,
        "damage_to_active": damage_to_active,
        "damage_to_switches": damage_to_switches,
        "accuracy": accuracy,
        "reasoning": reasoning,
        "score": score,
    }


def _generate_move_reasoning(
    move: Move,
    active_damage: Optional[DamageResult],
    ko_chance: Optional[str],
    accuracy: int,
    bench_damages: list[str],
) -> str:
    """Generate human-readable reasoning for a move choice."""
    reasons = []
    move_name = move.id.replace("-", " ").title()

    if ko_chance == "guaranteed":
        reasons.append(f"Guaranteed KO")
    elif ko_chance:
        reasons.append(f"{ko_chance} chance to KO")
    elif active_damage:
        avg = (active_damage.min_percent + active_damage.max_percent) / 2
        if avg >= 50:
            reasons.append("High damage")
        elif avg >= 25:
            reasons.append("Moderate damage")
        else:
            reasons.append("Low damage")

    if accuracy < 100:
        reasons.append(f"{accuracy}% accuracy")

    # Note good switch coverage
    ko_switches = [d for d in bench_damages if "guaranteed" in d.lower() or "100%" in d]
    if ko_switches:
        reasons.append(f"KOs {len(ko_switches)} bench Pokemon")

    # Priority
    if move.priority > 0:
        reasons.append(f"+{move.priority} priority")
    elif move.priority < 0:
        reasons.append(f"{move.priority} priority (moves last)")

    return "; ".join(reasons) if reasons else "Standard option"


def _build_summary(ranked_moves: list[dict[str, Any]], battle: Battle) -> str:
    """Build a natural language summary of move options."""
    if not ranked_moves:
        return "No moves available."

    lines = []

    # Best move
    best = ranked_moves[0]
    best_name = best["move"].replace("-", " ").title()

    if "Guaranteed KO" in best.get("reasoning", ""):
        lines.append(f"{best_name} is a guaranteed KO.")
    elif "chance to KO" in best.get("reasoning", ""):
        lines.append(f"{best_name} has a chance to KO ({best['damage_to_active']}).")
    else:
        lines.append(f"{best_name} deals {best['damage_to_active']}.")

    # Note if there's a more accurate option that also KOs
    if len(ranked_moves) > 1:
        for move in ranked_moves[1:3]:
            if "Guaranteed KO" in move.get("reasoning", ""):
                move_name = move["move"].replace("-", " ").title()
                if move.get("accuracy", 100) > best.get("accuracy", 100):
                    lines.append(f"{move_name} also KOs with better accuracy.")

    # Coverage note
    coverage_moves = [
        m for m in ranked_moves
        if m.get("damage_to_switches") and "KO" in m.get("damage_to_switches", "")
    ]
    if coverage_moves:
        cov_name = coverage_moves[0]["move"].replace("-", " ").title()
        lines.append(f"{cov_name} has good switch coverage.")

    return " ".join(lines)


def format_best_moves(best_moves: Optional[dict[str, Any]]) -> str:
    """Format best moves for the decision node.

    Args:
        best_moves: The best_moves dict from state

    Returns:
        Formatted string for LLM consumption
    """
    if not best_moves:
        return "## Best Moves\nNo move analysis available."

    lines = ["## Best Moves"]
    lines.append("")

    # Summary first
    summary = best_moves.get("summary", "")
    if summary:
        lines.append(f"**Summary:** {summary}")
        lines.append("")

    # Choice lock warning
    if best_moves.get("choice_locked"):
        lines.append(f"**CHOICE LOCKED** into {best_moves.get('locked_move', 'unknown move')}")
        lines.append("")

    # Ranked moves
    moves = best_moves.get("moves", [])
    if moves:
        lines.append("**Ranked Options:**")
        for move_data in moves[:4]:  # Top 4
            move_name = move_data["move"].replace("-", " ").title()
            rank = move_data.get("rank", "?")
            damage = move_data.get("damage_to_active", "?")
            accuracy = move_data.get("accuracy", 100)
            reasoning = move_data.get("reasoning", "")

            acc_note = f" [{accuracy}% acc]" if accuracy < 100 else ""
            lines.append(f"{rank}. **{move_name}**{acc_note}: {damage}")
            if reasoning:
                lines.append(f"   {reasoning}")

    return "\n".join(lines)
