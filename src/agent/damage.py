"""Deterministic damage calculations for the battle agent.

Wraps poke-env's gen9 damage calculator (``poke_env.calc.calculate_damage``)
to produce, for the current turn:

- how much damage each of our available moves does to the opponent's active
  Pokemon, and
- how much damage the opponent's active Pokemon does to our active Pokemon and
  to each of our available switches.

Results are expressed as a percentage of the defender's max HP, with a KO
annotation relative to the defender's *current* HP.

Opponent stats come entirely from the mechanical belief (see ``belief.py``,
populated by the ``resolve_opponent`` node): damage is computed across that
mon's live hypotheses and reported as an aggregate band. This module does not
estimate opponent stats itself. Our own Pokemon carry their true stats from the
battle request, so they are used as-is.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from poke_env.battle import Battle, Move, Pokemon
from poke_env.calc import calculate_damage

from .belief import BattleBelief, Hypothesis, _apply_hypothesis

logger = logging.getLogger(__name__)


@dataclass
class DamageResult:
    """Damage of one move against one defender."""

    move_name: str
    min_pct: float  # min damage as % of defender max HP
    max_pct: float  # max damage as % of defender max HP
    ko_label: Optional[str]  # "guaranteed KO", "possible KO", or None


def _is_opponent(mon: Pokemon, battle: Battle) -> bool:
    return mon in battle.opponent_team.values()


def _identifier(mon: Pokemon, battle: Battle) -> str:
    """Build the Showdown identifier (``p1: Name`` / ``p2: Name``) for a mon."""
    role = battle.opponent_role if _is_opponent(mon, battle) else battle.player_role
    return mon.identifier(role)


def _opponent_hypotheses(
    opp_mon: Pokemon, belief: Optional[BattleBelief]
) -> list[Hypothesis]:
    """Live hypotheses for an opponent mon from the belief (empty if none)."""
    if belief is not None:
        mon_belief = belief.mons.get(opp_mon.species)
        if mon_belief is not None:
            return mon_belief.alive()
    return []


def _calc(
    attacker: Pokemon,
    defender: Pokemon,
    move: Move,
    battle: Battle,
    belief: Optional[BattleBelief],
) -> Optional[DamageResult]:
    """Damage of one move, aggregated over the opponent's live hypotheses.

    Exactly one of attacker/defender is the opponent's active Pokemon; we vary
    its (stats, ability, item) over the belief's hypotheses, run the calc under
    each, and report the overall band (worst-to-best across hypotheses and
    rolls) plus a KO annotation.
    """
    attacker_id = _identifier(attacker, battle)
    defender_id = _identifier(defender, battle)
    opp_mon = attacker if _is_opponent(attacker, battle) else defender
    defender_is_opp = defender is opp_mon

    min_pct: Optional[float] = None
    max_pct: Optional[float] = None
    all_ko = True  # guaranteed KO only if every hypothesis KOs on its min roll
    any_ko = False

    for h in _opponent_hypotheses(opp_mon, belief):
        try:
            with _apply_hypothesis(opp_mon, h):
                lo, hi = calculate_damage(attacker_id, defender_id, move, battle)
        except Exception as e:  # calc has many edge cases; never break the turn
            logger.debug(f"Damage calc failed for {move.id}: {e}")
            continue

        def_max_hp = h.stats["hp"] if defender_is_opp else defender.max_hp
        if not def_max_hp:
            continue
        cur_hp = def_max_hp * defender.current_hp_fraction

        lo_pct, hi_pct = 100 * lo / def_max_hp, 100 * hi / def_max_hp
        min_pct = lo_pct if min_pct is None else min(min_pct, lo_pct)
        max_pct = hi_pct if max_pct is None else max(max_pct, hi_pct)
        all_ko = all_ko and (cur_hp > 0 and lo >= cur_hp)
        any_ko = any_ko or (cur_hp > 0 and hi >= cur_hp)

    if min_pct is None:
        return None

    ko_label = "guaranteed KO" if all_ko else "possible KO" if any_ko else None
    return DamageResult(
        move_name=move.id, min_pct=min_pct, max_pct=max_pct, ko_label=ko_label
    )


def _format_result(result: DamageResult) -> str:
    """Render a single DamageResult as a readable line."""
    name = result.move_name.replace("-", " ").title()
    if result.max_pct <= 0:
        return f"- {name}: no damage"
    line = f"- {name}: {result.min_pct:.0f}% - {result.max_pct:.0f}%"
    if result.ko_label:
        line += f" ({result.ko_label})"
    return line


def compute_damage_report(
    battle: Battle, belief: Optional[BattleBelief] = None
) -> str:
    """Build the deterministic damage report for the current turn.

    Returns markdown text summarising outgoing (our moves) and incoming
    (opponent's known moves) damage, suitable for inclusion in the LLM prompt.
    Opponent stats come from the belief's live hypotheses.
    """
    ours = battle.active_pokemon
    opp = battle.opponent_active_pokemon

    if not ours or not opp or battle.player_role is None or battle.opponent_role is None:
        return "## Damage Calculations\nUnavailable (missing active Pokemon)."

    lines = ["## Damage Calculations (deterministic)"]
    lines.append("Ranges are % of max HP across the opponent's likely sets.")
    lines.append("")

    # Outgoing: our available moves vs the opponent's active Pokemon.
    opp_species = opp.species.replace("-", " ").title()
    lines.append(
        f"### Your moves vs {opp_species} (~{opp.current_hp_fraction * 100:.0f}% HP)"
    )
    if battle.available_moves:
        for move in battle.available_moves:
            result = _calc(ours, opp, move, battle, belief)
            if result is not None:
                lines.append(_format_result(result))
    else:
        lines.append("- No moves available")
    lines.append("")

    # Incoming: opponent's known moves vs our active Pokemon and our switches.
    lines.append("### Incoming damage (opponent's revealed moves)")
    opp_moves = list(opp.moves.values())
    if not opp_moves:
        lines.append("- No opponent moves revealed yet")
    else:
        defenders = [ours] + list(battle.available_switches)
        for defender in defenders:
            def_species = defender.species.replace("-", " ").title()
            role = "active" if defender is ours else "switch"
            lines.append(
                f"vs your {role} {def_species} "
                f"({defender.current_hp_fraction * 100:.0f}% HP):"
            )
            for move in opp_moves:
                result = _calc(opp, defender, move, battle, belief)
                if result is not None:
                    lines.append(_format_result(result))
    lines.append("")

    return "\n".join(lines)
