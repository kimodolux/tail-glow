"""Curated common Smogon-style spreads + role-based fallback.

The JSON at `src/data/smogon-common.json` ships a hand-picked list of
common spreads per Pokemon (a "prior" over opponent EV/item/nature). For
species not in the file, we fall back to a role-based heuristic: 252 EVs
in each of the two highest base stats, 4 in the third highest.

Phase 1 returns the default-indexed spread. The full `spreads` list is
kept reachable via `lookup_all` so a future inference engine (Phase 2) can
narrow the posterior from observed damage.
"""

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from poke_env.battle import Pokemon
from poke_env.data import GenData

from .resolver import (
    STAT_ORDER,
    Spread,
    _compute_stats,
    _normalize_species,
    _resolve_pokedex_id,
)

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).parent.parent / "data" / "smogon-common.json"


@dataclass(frozen=True)
class CuratedSpread:
    """One curated spread entry loaded from JSON."""

    name: str
    evs: dict[str, int]
    ivs: dict[str, int]
    nature: str
    level: int
    item: str | None
    ability: str | None
    moves: tuple[str, ...]


@dataclass(frozen=True)
class SpeciesEntry:
    spreads: tuple[CuratedSpread, ...]
    default_idx: int

    def default(self) -> CuratedSpread:
        return self.spreads[self.default_idx]


class CommonSpreadsDB:
    """JSON-backed curated spreads + role-based fallback."""

    def __init__(self, entries: dict[str, SpeciesEntry]):
        self._entries = entries

    @classmethod
    def from_file(cls, path: Path = _DATA_PATH) -> "CommonSpreadsDB":
        if not path.exists():
            logger.warning("smogon-common.json not found at %s; using empty DB", path)
            return cls({})
        data = json.loads(path.read_text())
        species_map = data.get("pokemon", {})
        entries: dict[str, SpeciesEntry] = {}
        for species_key, entry in species_map.items():
            spreads = tuple(_parse_spread(s) for s in entry["spreads"])
            default_idx = int(entry.get("default_spread_idx", 0))
            entries[_normalize_species(species_key)] = SpeciesEntry(spreads, default_idx)
        logger.info("Loaded %d curated species from %s", len(entries), path.name)
        return cls(entries)

    def lookup_all(self, species: str) -> tuple[CuratedSpread, ...]:
        """All curated spreads for the species, or () if uncovered."""
        entry = self._entries.get(_normalize_species(species))
        return entry.spreads if entry else ()

    def with_overrides(self, overrides: dict) -> "CommonSpreadsDB":
        """Return a new DB with `overrides` merged on top of the current entries.

        `overrides` follows the same shape as the `pokemon` section of
        smogon-common.json: `{species: {spreads: [...], default_spread_idx: N}}`.
        Species in `overrides` fully replace any existing entry (no spread-level
        merging — author the full entry for the species you're overriding).

        Used by scenario tests to pin a specific opponent spread per fixture
        without mutating the global JSON.
        """
        if not overrides:
            return self
        merged = dict(self._entries)
        for species_key, entry in overrides.items():
            spreads = tuple(_parse_spread(s) for s in entry["spreads"])
            default_idx = int(entry.get("default_spread_idx", 0))
            merged[_normalize_species(species_key)] = SpeciesEntry(spreads, default_idx)
        return CommonSpreadsDB(merged)

    def resolve(self, pokemon: Pokemon, gen_data: GenData) -> Spread:
        """Resolve a Pokemon to a Spread using the curated entry or fallback."""
        species_id = _resolve_pokedex_id(pokemon.species, gen_data)
        entry = self._entries.get(_normalize_species(pokemon.species))

        if entry is not None:
            chosen = entry.default()
            all_spreads = entry.spreads
        else:
            chosen = _role_based_fallback(pokemon.species, species_id, gen_data)
            all_spreads = (chosen,)
            logger.debug(
                "No curated spread for %s; using role-based fallback %s",
                pokemon.species,
                chosen.name,
            )

        if species_id is None:
            stats = dict(pokemon.stats) if pokemon.stats else {}
        else:
            stats = _compute_stats(
                species_id, chosen.evs, chosen.ivs, chosen.level, chosen.nature, gen_data
            )

        return Spread(
            level=chosen.level,
            stats=stats,
            evs=dict(chosen.evs),
            ivs=dict(chosen.ivs),
            nature=chosen.nature,
            item=chosen.item,
            ability=chosen.ability,
            moves=chosen.moves,
            possible_moves=frozenset(m for s in all_spreads for m in s.moves),
            possible_items=tuple({s.item for s in all_spreads if s.item}),
            possible_abilities=tuple({s.ability for s in all_spreads if s.ability}),
        )


@lru_cache(maxsize=1)
def load_common_spreads() -> CommonSpreadsDB:
    return CommonSpreadsDB.from_file()


def _parse_spread(raw: dict) -> CuratedSpread:
    evs = {s: int(raw.get("evs", {}).get(s, 0)) for s in STAT_ORDER}
    ivs = {s: int(raw.get("ivs", {}).get(s, 31)) for s in STAT_ORDER}
    moves = tuple(m.lower().replace(" ", "").replace("-", "") for m in raw.get("moves", []))
    return CuratedSpread(
        name=raw.get("name", "unnamed"),
        evs=evs,
        ivs=ivs,
        nature=raw.get("nature", "hardy").lower(),
        level=int(raw.get("level", 100)),
        item=raw.get("item"),
        ability=raw.get("ability"),
        moves=moves,
    )


def _role_based_fallback(
    species: str, species_id: str | None, gen_data: GenData
) -> CuratedSpread:
    """Pick a sensible default spread when the species isn't in the JSON.

    Heuristic: 252 EVs in each of the two highest base stats, 4 in the third
    highest. Nature is "hardy" (neutral) because we don't know which spread
    the opponent actually picked.
    """
    evs = {s: 0 for s in STAT_ORDER}
    if species_id is not None and species_id in gen_data.pokedex:
        base_stats = gen_data.pokedex[species_id].get("baseStats", {})
        # poke-env's pokedex uses Showdown stat keys: hp, atk, def, spa, spd, spe
        ranked = sorted(STAT_ORDER, key=lambda s: -int(base_stats.get(s, 0)))
        for stat in ranked[:2]:
            evs[stat] = 252
        if len(ranked) >= 3:
            evs[ranked[2]] = 4
    else:
        # No pokedex data — split evenly across "common" attacker stats
        for stat in ("atk", "spa", "spe"):
            evs[stat] = 168

    return CuratedSpread(
        name="role-based fallback",
        evs=evs,
        ivs={s: 31 for s in STAT_ORDER},
        nature="hardy",
        level=100,
        item=None,
        ability=None,
        moves=(),
    )
