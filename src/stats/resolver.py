"""StatsResolver protocol + concrete implementations.

A `Spread` is the resolved view of one Pokemon's stat-relevant data:
computed stats, the EVs/IVs/nature/level that produced them, and the
revealed/inferred item/ability/move pool. Consumers prefer `stats` to
recomputing from EVs.
"""

import logging
from dataclasses import dataclass, field
from typing import Protocol

from poke_env.battle import Pokemon
from poke_env.data import GenData
from poke_env.stats import compute_raw_stats

logger = logging.getLogger(__name__)

STAT_ORDER = ("hp", "atk", "def", "spa", "spd", "spe")

_DEFAULT_EVS: dict[str, int] = {s: 84 for s in STAT_ORDER}
_DEFAULT_IVS: dict[str, int] = {s: 31 for s in STAT_ORDER}


@dataclass(frozen=True)
class Spread:
    """Resolved stat info for one Pokemon.

    `stats` is always populated. `evs`/`ivs`/`nature` describe the spread
    that produced those stats (or `{}` / "unknown" when stats came directly
    from `pokemon.stats` and the underlying spread is not known).
    """

    level: int
    stats: dict[str, int]
    evs: dict[str, int] = field(default_factory=dict)
    ivs: dict[str, int] = field(default_factory=dict)
    nature: str = "hardy"
    item: str | None = None
    ability: str | None = None
    moves: tuple[str, ...] = ()
    possible_moves: frozenset[str] = frozenset()
    possible_items: tuple[str, ...] = ()
    possible_abilities: tuple[str, ...] = ()
    possible_tera_types: tuple[str, ...] = ()
    # True when stats came from server-truth (pokemon.stats), not a spread
    stats_are_exact: bool = False


class StatsResolver(Protocol):
    """Resolves a Pokemon to a stat Spread regardless of battle format."""

    def get_spread(self, pokemon: Pokemon, is_opponent: bool) -> Spread: ...


def _normalize_species(species: str) -> str:
    return species.lower().replace("-", "").replace(" ", "")


def _resolve_pokedex_id(species: str, gen_data: GenData) -> str | None:
    """Find the pokedex key for a species, trying base form if needed."""
    species_id = _normalize_species(species)
    if species_id in gen_data.pokedex:
        return species_id
    if "-" in species:
        base = _normalize_species(species.split("-")[0])
        if base in gen_data.pokedex:
            return base
    return None


def _compute_stats(
    species_id: str,
    evs: dict[str, int],
    ivs: dict[str, int],
    level: int,
    nature: str,
    gen_data: GenData,
) -> dict[str, int]:
    evs_list = [evs.get(s, 0) for s in STAT_ORDER]
    ivs_list = [ivs.get(s, 31) for s in STAT_ORDER]
    raw = compute_raw_stats(species_id, evs_list, ivs_list, level, nature, gen_data)
    return {s: raw[i] for i, s in enumerate(STAT_ORDER)}


class RandbatsResolver:
    """Wraps the existing randbats_data lookup. Identical behavior to today.

    When `randbats_data` lacks an entry, falls back to the historical
    [84 EVs, 31 IVs, hardy nature] spread so existing random battles keep
    working even when the cached JSON is stale.
    """

    def __init__(self, randbats_data, gen_data: GenData):
        self._randbats = randbats_data
        self._gen_data = gen_data

    def get_spread(self, pokemon: Pokemon, is_opponent: bool) -> Spread:
        species = pokemon.species
        species_id = _resolve_pokedex_id(species, self._gen_data)

        if self._randbats is not None:
            evs = self._randbats.get_evs(species)
            ivs = self._randbats.get_ivs(species)
            level = self._randbats.get_level(species) or pokemon.level or 100
            possible_moves = self._randbats.get_possible_moves(species)
            possible_items = tuple(self._randbats.get_possible_items(species))
            possible_abilities = tuple(self._randbats.get_possible_abilities(species))
            possible_tera_types = self._collect_tera_types(species)
        else:
            evs = dict(_DEFAULT_EVS)
            ivs = dict(_DEFAULT_IVS)
            level = pokemon.level or 100
            possible_moves = frozenset()
            possible_items = ()
            possible_abilities = ()
            possible_tera_types = ()

        if species_id is None:
            stats = dict(pokemon.stats) if pokemon.stats else {}
        else:
            stats = _compute_stats(species_id, evs, ivs, level, "hardy", self._gen_data)

        return Spread(
            level=level,
            stats=stats,
            evs=evs,
            ivs=ivs,
            nature="hardy",
            possible_moves=frozenset(possible_moves),
            possible_items=possible_items,
            possible_abilities=possible_abilities,
            possible_tera_types=possible_tera_types,
        )

    def _collect_tera_types(self, species: str) -> tuple[str, ...]:
        pokemon = self._randbats.get_pokemon(species) if self._randbats else None
        if not pokemon:
            return ()
        seen: set[str] = set()
        for role in pokemon.roles.values():
            for tera in role.tera_types:
                seen.add(tera)
        return tuple(seen)


class NonRandomResolver:
    """For OU / customgame / etc.

    - Own side: trust `pokemon.stats` (the server populated these from the
      team we submitted) and short-circuit. EVs/IVs/nature are left blank
      because we don't actually need them; the computed stats are truth.
    - Opponent side: look up curated spread(s) for the species. Phase 1
      returns the default-indexed spread; Phase 2 will narrow via inference.
    """

    def __init__(self, common_spreads: "CommonSpreadsDB", gen_data: GenData):
        self._common = common_spreads
        self._gen_data = gen_data

    def get_spread(self, pokemon: Pokemon, is_opponent: bool) -> Spread:
        if not is_opponent and _has_real_stats(pokemon):
            return Spread(
                level=pokemon.level or 100,
                stats=dict(pokemon.stats),
                item=_clean_item(pokemon.item),
                ability=pokemon.ability or None,
                stats_are_exact=True,
            )

        return self._common.resolve(pokemon, self._gen_data)


def _has_real_stats(pokemon: Pokemon) -> bool:
    """True when pokemon.stats has all six positive values."""
    stats = pokemon.stats
    if not stats:
        return False
    return all((stats.get(s) or 0) > 0 for s in STAT_ORDER)


def _clean_item(item: str | None) -> str | None:
    if not item or item in ("unknown_item", "unknown"):
        return None
    return item


# Avoid circular import at module load time
from .common_spreads import CommonSpreadsDB  # noqa: E402
