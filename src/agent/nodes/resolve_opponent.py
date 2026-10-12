"""Resolve-opponent node - mechanical belief tracking over opponent sets.

Runs between ``format_state`` and ``damage_calc``. Maintains a persistent,
per-battle :class:`BattleBelief` (weighted hypotheses per opponent Pokemon) and
narrows it each turn from revealed facts (locks) and observed damage rolls. This
belief is the *single source* of opponent stats for ``damage_calc``.

For randbats we enumerate the real set hypotheses; for any other format (or an
unknown species) we fall back to a single neutral-spread hypothesis, so the
belief always yields opponent stats. Stats are never produced by an LLM - this
node is fully deterministic.
"""

import logging

from ..state import AgentState
from ..belief import (
    BattleBelief,
    MonBelief,
    apply_locks,
    apply_observation,
    extract_damage_observations,
    get_provider,
    neutral_hypothesis,
    summarize,
)

logger = logging.getLogger(__name__)


def resolve_opponent_node(state: AgentState) -> AgentState:
    """Update the opponent belief from this turn's reveals and damage rolls."""
    battle = state.get("battle_object")
    belief: BattleBelief = state.get("opponent_belief")
    if not battle or belief is None:
        state["opponent_summary"] = None
        return state

    try:
        _update_belief(battle, belief)
        active = battle.opponent_active_pokemon
        if active is not None and active.species in belief.mons:
            state["opponent_summary"] = summarize(belief.mons[active.species])
        else:
            state["opponent_summary"] = None
    except Exception as e:
        logger.error(f"resolve_opponent error: {e}")
        state["opponent_summary"] = None

    return state


def _update_belief(battle, belief: BattleBelief) -> None:
    """Initialise, lock, and roll-narrow the belief for every seen opponent mon."""
    data = battle._data
    provider = get_provider(belief.format_id)

    # 1. Ensure a belief exists for each revealed opponent Pokemon, then apply
    #    locks from everything currently known about it.
    for mon in battle.opponent_team.values():
        species = mon.species
        item = mon.item if mon.item not in (None, data.UNKNOWN_ITEM) else None

        if species not in belief.mons:
            hyps = provider.hypotheses(species, mon.level, data) if provider else []
            if not hyps:  # no set data (non-randbats / unknown species)
                hyps = [neutral_hypothesis(species, mon.level, data, mon.ability, item)]
            belief.mons[species] = MonBelief(species=species, hypotheses=hyps)

        tera = mon.tera_type if mon.is_terastallized else None
        apply_locks(belief.mons[species], set(mon.moves.keys()), mon.ability, item, tera)

    # 2. Fold in damage observations from turns not yet processed.
    for obs in extract_damage_observations(battle):
        if obs.turn in belief.processed_turns:
            continue
        attacker = battle.get_pokemon(obs.attacker_id)
        if attacker.species in belief.mons:
            apply_observation(belief.mons[attacker.species], obs, battle)

    belief.processed_turns.update(battle.observations.keys())
