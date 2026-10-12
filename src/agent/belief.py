"""Mechanical belief tracking for opponent Pokemon.

We never guess opponent stats with an LLM. Instead we maintain, per opponent
Pokemon, a **weighted set of hypotheses** - each a fully specified mechanical
set (stat block + ability + item + move pool + tera options) - and narrow it
with evidence:

- **locks**: facts revealed by the battle (moves seen, ability/item/tera
  revealed) hard-eliminate inconsistent hypotheses;
- **damage rolls**: observed damage is checked against each hypothesis's
  computed damage range and inconsistent hypotheses are down-weighted.

The design is format-agnostic on purpose (see ``PriorProvider``). Randbats has a
tiny, enumerable hypothesis space with exact stats; a future OU provider would
emit a longer, usage-weighted candidate list from the same contract, and the
rest of the engine and its consumers would not change.

Three invariants keep OU a drop-in later:
1. hypotheses are always a *weighted* list (never a boolean survivor set);
2. evidence updates are *multiplicative on weights* (hard elimination is just
   the ``weight *= 0`` special case);
3. consumers read the weighted set (via :func:`normalized` / ``alive``),
   never a single "resolved" stat block.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol

from poke_env.battle import Battle, Move, Pokemon, PokemonType
from poke_env.calc import calculate_damage
from poke_env.data import GenData, to_id_str
from poke_env.stats import compute_raw_stats

from .randbats import load_randbats

logger = logging.getLogger(__name__)

STATS = ("hp", "atk", "def", "spa", "spd", "spe")

# Neutral nature, 85 EVs / 31 IVs in every stat. Randbats supplies partial
# overrides (e.g. ``{"atk": 0}``); the neutral fallback uses the bare defaults.
_NEUTRAL_NATURE = "hardy"
_DEFAULT_EV = 85
_DEFAULT_IV = 31

# A hypothesis whose computed damage range does not contain an observed roll is
# very likely wrong - but conditions may have shifted since the observation
# (boosts, weather), so we down-weight hard rather than zeroing. Locks, which
# are certain, use a true 0.
_ROLL_MISMATCH_PENALTY = 0.02


@dataclass
class Hypothesis:
    """One fully specified mechanical set the opponent Pokemon might be."""

    label: str  # human-readable, e.g. the randbats role name
    weight: float
    stats: dict[str, int]
    ability: Optional[str]
    item: Optional[str]
    move_pool: frozenset[str]  # move ids this set can carry
    tera_types: tuple[PokemonType, ...]


@dataclass
class MonBelief:
    """Belief over a single opponent Pokemon (keyed by species)."""

    species: str
    hypotheses: list[Hypothesis]

    def alive(self) -> list[Hypothesis]:
        """Hypotheses with non-negligible weight."""
        return [h for h in self.hypotheses if h.weight > 1e-9]


@dataclass
class BattleBelief:
    """Belief for a whole battle; persists across turns, keyed by battle tag."""

    format_id: Optional[str]
    mons: dict[str, MonBelief] = field(default_factory=dict)
    # Turns whose damage observations have already been folded in, so re-running
    # the node each turn does not re-apply (and re-penalise) old evidence.
    processed_turns: set[int] = field(default_factory=set)


# --------------------------------------------------------------------------- #
# Prior providers (the format-specific seam)
# --------------------------------------------------------------------------- #


class PriorProvider(Protocol):
    """Generates the initial weighted hypothesis set for a species."""

    def hypotheses(self, species: str, level: int, data: GenData) -> list[Hypothesis]:
        ...


def _merge_spread(base: dict, *overrides: dict, default: int) -> list[int]:
    """Build a full 6-stat list from a default plus partial overrides."""
    spread = {s: default for s in STATS}
    for override in (base, *overrides):
        spread.update(override or {})
    return [spread[s] for s in STATS]


def neutral_hypothesis(
    species: str,
    level: int,
    data: GenData,
    ability: Optional[str] = None,
    item: Optional[str] = None,
) -> Hypothesis:
    """A single neutral-spread hypothesis for when no set data is available."""
    raw = compute_raw_stats(
        species, [_DEFAULT_EV] * 6, [_DEFAULT_IV] * 6, level, _NEUTRAL_NATURE, data
    )
    return Hypothesis(
        label="neutral",
        weight=1.0,
        stats=dict(zip(STATS, raw)),
        ability=ability,
        item=item,
        move_pool=frozenset(),  # empty pool = unknown, never used to eliminate
        tera_types=(),
    )


class RandbatsPriorProvider:
    """Enumerates the finite, exact hypothesis set from randbats data.

    Stats are determined by (species, level, role EV/IV overrides); ability and
    item vary over the role's small pools. All hypotheses start equally likely.
    """

    def __init__(self, format_id: str = "gen9randombattle"):
        self.format_id = format_id

    def hypotheses(self, species: str, level: int, data: GenData) -> list[Hypothesis]:
        entry = load_randbats(self.format_id).get(species)
        if not entry:
            return []

        species_evs = entry.get("evs", {})
        species_ivs = entry.get("ivs", {})
        out: list[Hypothesis] = []

        for role_name, role in entry.get("roles", {}).items():
            evs = _merge_spread(species_evs, role.get("evs", {}), default=_DEFAULT_EV)
            ivs = _merge_spread(species_ivs, role.get("ivs", {}), default=_DEFAULT_IV)
            raw = compute_raw_stats(species, evs, ivs, level, _NEUTRAL_NATURE, data)
            stats = dict(zip(STATS, raw))

            abilities = role.get("abilities") or entry.get("abilities") or [None]
            items = role.get("items") or entry.get("items") or [None]
            move_pool = frozenset(to_id_str(m) for m in role.get("moves", []))
            tera = tuple(
                PokemonType.from_name(t) for t in role.get("teraTypes", [])
            )

            for ability in abilities:
                for item in items:
                    out.append(
                        Hypothesis(
                            label=role_name,
                            weight=1.0,
                            stats=stats,
                            ability=to_id_str(ability) if ability else None,
                            item=to_id_str(item) if item else None,
                            move_pool=move_pool,
                            tera_types=tera,
                        )
                    )
        return out


def get_provider(format_id: Optional[str]) -> Optional[PriorProvider]:
    """Pick a prior provider for the battle format, or None (neutral fallback)."""
    if format_id and "randombattle" in format_id and format_id.startswith("gen9"):
        return RandbatsPriorProvider(format_id)
    return None


# --------------------------------------------------------------------------- #
# Belief updates
# --------------------------------------------------------------------------- #


@dataclass
class DamageObservation:
    """An observed hit by the opponent on one of our Pokemon (exact HP)."""

    turn: int
    attacker_id: str  # Showdown identifier, e.g. "p2a: Garchomp"
    defender_id: str
    move_id: str
    damage: int  # absolute HP lost


def _parse_hp(hp_field: str) -> Optional[tuple[int, int]]:
    """Parse a Showdown HP field like ``"123/180"`` or ``"0 fnt"``."""
    token = hp_field.split()[0] if hp_field else ""
    if token in ("0", ""):
        return (0, 0) if token == "0" else None
    if "/" not in token:
        return None
    try:
        cur, mx = token.split("/")
        return int(cur), int(mx)
    except ValueError:
        return None


def extract_damage_observations(battle: Battle) -> list[DamageObservation]:
    """Reconstruct opponent-move hits on our Pokemon from the battle event log.

    Only our own Pokemon are used as defenders: their HP is reported in absolute
    points, so the damage is exact (opponent HP is percentage-only and useless
    for inversion). Damage from items/abilities/hazards (``[from] ...``) is
    skipped - we only want move damage attributable to an attacker.
    """
    player_role = battle.player_role
    opponent_role = battle.opponent_role
    if not player_role or not opponent_role:
        return []

    observations: list[DamageObservation] = []
    hp: dict[str, int] = {}  # ident (with position) -> current absolute HP

    def norm(ident: str) -> str:
        # "p1a: Dragonite" -> "p1: Dragonite" (position-stripped, matches calc)
        return ident[:2] + ident[3:] if len(ident) > 3 and ident[3] != " " else ident

    for turn in sorted(battle.observations.keys()):
        pending_move: Optional[tuple[str, str]] = None  # (attacker_ident, move_id)
        for event in battle.observations[turn].events:
            if len(event) < 3 or not event[1]:
                continue
            tag = event[1]

            if tag in ("switch", "drag") and len(event) >= 5:
                # |switch|IDENT|DETAILS|HP  -> HP is at index 4
                parsed = _parse_hp(event[4])
                if parsed:
                    hp[norm(event[2])] = parsed[0]
            elif tag == "move" and len(event) >= 4:
                pending_move = (norm(event[2]), to_id_str(event[3]))
            elif tag in ("-heal", "-sethp") and len(event) >= 4:
                parsed = _parse_hp(event[3])
                if parsed:
                    hp[norm(event[2])] = parsed[0]
            elif tag == "-damage" and len(event) >= 4:
                ident = norm(event[2])
                parsed = _parse_hp(event[3])
                is_move_damage = len(event) == 4  # no "[from] ..." suffix
                before = hp.get(ident)
                if parsed is not None:
                    after = parsed[0]
                    if (
                        is_move_damage
                        and pending_move is not None
                        and ident.startswith(player_role)
                        and pending_move[0].startswith(opponent_role)
                        and before is not None
                        and before - after > 0
                    ):
                        observations.append(
                            DamageObservation(
                                turn=turn,
                                attacker_id=pending_move[0],
                                defender_id=ident,
                                move_id=pending_move[1],
                                damage=before - after,
                            )
                        )
                    hp[ident] = after

    return observations


def init_mon(
    species: str, level: int, data: GenData, provider: PriorProvider
) -> MonBelief:
    """Create a fresh belief for a species from a provider's prior."""
    return MonBelief(species=species, hypotheses=provider.hypotheses(species, level, data))


def apply_locks(
    belief: MonBelief,
    revealed_moves: set[str],
    ability: Optional[str],
    item: Optional[str],
    tera: Optional[PokemonType],
) -> None:
    """Hard-eliminate hypotheses contradicted by revealed facts (weight -> 0).

    A hypothesis with an empty ``move_pool`` (the neutral fallback) has an
    unknown pool and is never eliminated by revealed moves.
    """
    for h in belief.hypotheses:
        if revealed_moves and h.move_pool and not revealed_moves <= h.move_pool:
            h.weight = 0.0
        elif ability and h.ability and h.ability != ability:
            h.weight = 0.0
        elif item and h.item and h.item != item:
            h.weight = 0.0
        elif tera and h.tera_types and tera not in h.tera_types:
            h.weight = 0.0


def apply_observation(
    belief: MonBelief, obs: DamageObservation, battle: Battle
) -> None:
    """Down-weight hypotheses whose damage range can't produce the observed hit.

    Runs the deterministic calc under each hypothesis (its stats/ability/item
    applied to the attacker) and compares the observed damage to the roll range.
    """
    attacker = battle.get_pokemon(obs.attacker_id)
    move = Move(obs.move_id, gen=battle.gen)

    for h in belief.alive():
        try:
            with _apply_hypothesis(attacker, h):
                lo, hi = calculate_damage(
                    obs.attacker_id, obs.defender_id, move, battle
                )
        except Exception as e:  # calc edge cases must not break tracking
            logger.debug(f"roll-inversion calc failed for {obs.move_id}: {e}")
            continue
        # A small tolerance absorbs integer rounding at the range edges.
        if not (lo - 1 <= obs.damage <= hi + 1):
            h.weight *= _ROLL_MISMATCH_PENALTY


class _apply_hypothesis:
    """Temporarily apply a hypothesis's stats/ability/item to a Pokemon."""

    def __init__(self, mon: Pokemon, h: Hypothesis):
        self.mon = mon
        self.h = h

    def __enter__(self):
        self._stats = dict(self.mon.stats)
        self._ability = self.mon._ability
        self._item = self.mon._item
        self.mon.stats = dict(self.h.stats)
        if self.h.ability is not None:
            self.mon._ability = self.h.ability
        if self.h.item is not None:
            self.mon._item = self.h.item
        return self

    def __exit__(self, *exc):
        self.mon.stats = self._stats
        self.mon._ability = self._ability
        self.mon._item = self._item
        return False


# --------------------------------------------------------------------------- #
# Consumer-facing reduction
# --------------------------------------------------------------------------- #


def normalized(belief: MonBelief) -> list[tuple[Hypothesis, float]]:
    """Alive hypotheses paired with weights normalised to sum to 1."""
    alive = belief.alive()
    total = sum(h.weight for h in alive)
    if total <= 0:
        return []
    return [(h, h.weight / total) for h in alive]


def summarize(belief: MonBelief) -> str:
    """A short human-readable summary of the current belief (for the prompt)."""
    dist = normalized(belief)
    if not dist:
        return f"{belief.species}: unknown set (no data)"
    parts = []
    for h, w in sorted(dist, key=lambda x: -x[1])[:4]:
        item = h.item or "?"
        parts.append(f"{h.label} [{item}/{h.ability or '?'}] {w * 100:.0f}%")
    return f"{belief.species}: " + "; ".join(parts)
