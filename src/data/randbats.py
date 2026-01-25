"""Randbats data fetcher and parser.

Fetches random battle sets from pkmn.github.io and provides helper methods
for looking up Pokemon data including levels, EVs, IVs, and possible moves.

Usage:
    # At startup
    await init_randbats_data("gen9randombattle")

    # Anywhere in code
    from src.data.randbats import get_randbats_data
    data = get_randbats_data()
    if data:
        evs = data.get_evs("Pikachu")
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import httpx

logger = logging.getLogger(__name__)

# Module-level cache for randbats data
_randbats_cache: Optional["RandbatsData"] = None


@dataclass
class RandbatsRole:
    """A single role for a Pokemon in random battles."""

    name: str
    moves: List[str]
    abilities: List[str]
    items: List[str]
    tera_types: List[str] = field(default_factory=list)
    evs: Dict[str, int] = field(default_factory=dict)
    ivs: Dict[str, int] = field(default_factory=dict)


@dataclass
class RandbatsPokemon:
    """Data for a single Pokemon in random battles."""

    species: str
    level: int
    abilities: List[str]
    items: List[str]
    roles: Dict[str, RandbatsRole]
    evs: Dict[str, int] = field(default_factory=dict)
    ivs: Dict[str, int] = field(default_factory=dict)


class RandbatsData:
    """Container for random battle set data with lookup methods."""

    def __init__(self, data: Dict[str, RandbatsPokemon]):
        self._data = data
        self._normalized_lookup: Dict[str, str] = {}
        for species in data.keys():
            normalized = self._normalize_species(species)
            self._normalized_lookup[normalized] = species

    def __len__(self) -> int:
        return len(self._data)

    def _normalize_species(self, species: str) -> str:
        """Normalize species name for lookup."""
        return species.lower().replace("-", "").replace(" ", "").replace(".", "")

    def get_pokemon(self, species: str) -> Optional[RandbatsPokemon]:
        """Get Pokemon data by species name.

        Handles forme variants by falling back to base species if the full
        forme name isn't found (e.g., "Tatsugiri-Curly" -> "Tatsugiri").
        """
        normalized = self._normalize_species(species)
        original = self._normalized_lookup.get(normalized)
        if original:
            logger.debug(f"Randbats lookup: '{species}' -> '{original}' (exact match)")
            return self._data.get(original)

        # Try base species without forme suffix
        if "-" in species:
            base_species = species.split("-")[0]
            normalized_base = self._normalize_species(base_species)
            original_base = self._normalized_lookup.get(normalized_base)
            if original_base:
                logger.info(f"Randbats lookup: '{species}' -> '{original_base}' (forme fallback)")
                return self._data.get(original_base)

        # Try prefix matching for already-normalized names (e.g., "tatsugiricurly")
        # where the dash was already stripped during normalization
        for lookup_normalized, lookup_original in self._normalized_lookup.items():
            # Check if normalized name starts with a known base species
            if normalized.startswith(lookup_normalized) and len(normalized) > len(lookup_normalized):
                logger.info(f"Randbats lookup: '{species}' -> '{lookup_original}' (prefix match)")
                return self._data.get(lookup_original)

        logger.warning(f"#### UNEXPECTED: Randbats lookup failed for '{species}' (normalized: '{normalized}') ####")
        return None

    def get_level(self, species: str) -> Optional[int]:
        """Get the randbats level for a Pokemon."""
        pokemon = self.get_pokemon(species)
        if pokemon:
            logger.debug(f"Randbats level for '{species}': {pokemon.level}")
            return pokemon.level
        logger.warning(f"#### UNEXPECTED: No randbats level for '{species}', will use fallback ####")
        return None

    def get_evs(self, species: str) -> Dict[str, int]:
        """Get EVs for a Pokemon, defaulting unspecified stats to 84.

        Random battles use 84 EVs in each stat as the default,
        but some Pokemon have custom spreads defined.
        """
        pokemon = self.get_pokemon(species)
        if not pokemon:
            logger.warning(f"#### UNEXPECTED: No randbats EVs for '{species}', using default 84s ####")
            return {"hp": 84, "atk": 84, "def": 84, "spa": 84, "spd": 84, "spe": 84}

        base_evs = {"hp": 84, "atk": 84, "def": 84, "spa": 84, "spd": 84, "spe": 84}
        if pokemon.evs:
            base_evs.update(pokemon.evs)
            logger.debug(f"Randbats EVs for '{species}': custom spread {pokemon.evs}")
        return base_evs

    def get_ivs(self, species: str) -> Dict[str, int]:
        """Get IVs for a Pokemon, defaulting unspecified stats to 31."""
        pokemon = self.get_pokemon(species)
        if not pokemon:
            logger.warning(f"#### UNEXPECTED: No randbats IVs for '{species}', using default 31s ####")
            return {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}

        base_ivs = {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31}
        if pokemon.ivs:
            base_ivs.update(pokemon.ivs)
            logger.debug(f"Randbats IVs for '{species}': custom spread {pokemon.ivs}")
        return base_ivs

    def get_possible_moves(self, species: str) -> Set[str]:
        """Get all possible moves across all roles for a Pokemon."""
        pokemon = self.get_pokemon(species)
        if not pokemon:
            logger.warning(f"#### UNEXPECTED: No randbats moves for '{species}' ####")
            return set()

        moves: Set[str] = set()
        for role in pokemon.roles.values():
            for move in role.moves:
                moves.add(self._normalize_move(move))
        logger.debug(f"Randbats moves for '{species}': {len(moves)} possible moves")
        return moves

    def get_possible_abilities(self, species: str) -> List[str]:
        """Get all possible abilities for a Pokemon."""
        pokemon = self.get_pokemon(species)
        if not pokemon:
            logger.warning(f"#### UNEXPECTED: No randbats abilities for '{species}' ####")
            return []
        return pokemon.abilities

    def get_possible_items(self, species: str) -> List[str]:
        """Get all possible items for a Pokemon."""
        pokemon = self.get_pokemon(species)
        if not pokemon:
            logger.warning(f"#### UNEXPECTED: No randbats items for '{species}' ####")
            return []
        return pokemon.items

    def _normalize_move(self, move: str) -> str:
        """Normalize move name to match poke-env format."""
        return move.lower().replace(" ", "").replace("-", "")


def _parse_randbats_json(raw_data: Dict[str, Any]) -> Dict[str, RandbatsPokemon]:
    """Parse raw JSON data into RandbatsPokemon objects."""
    result: Dict[str, RandbatsPokemon] = {}

    for species, data in raw_data.items():
        if not isinstance(data, dict):
            continue

        level = data.get("level", 100)
        abilities = data.get("abilities", [])
        items = data.get("items", [])
        evs = _parse_evs(data.get("evs", {}))
        ivs = _parse_ivs(data.get("ivs", {}))

        roles: Dict[str, RandbatsRole] = {}
        roles_data = data.get("roles", {})

        for role_name, role_data in roles_data.items():
            if not isinstance(role_data, dict):
                continue

            role = RandbatsRole(
                name=role_name,
                moves=role_data.get("moves", []),
                abilities=role_data.get("abilities", abilities),
                items=role_data.get("items", items),
                tera_types=role_data.get("teraTypes", []),
                evs=_parse_evs(role_data.get("evs", {})),
                ivs=_parse_ivs(role_data.get("ivs", {})),
            )
            roles[role_name] = role

        pokemon = RandbatsPokemon(
            species=species,
            level=level,
            abilities=abilities,
            items=items,
            roles=roles,
            evs=evs,
            ivs=ivs,
        )
        result[species] = pokemon

    return result


def _parse_evs(evs_data: Dict[str, Any]) -> Dict[str, int]:
    """Parse EV data, normalizing stat names."""
    stat_map = {
        "hp": "hp",
        "atk": "atk",
        "def": "def",
        "spa": "spa",
        "spd": "spd",
        "spe": "spe",
    }
    result: Dict[str, int] = {}
    for stat, value in evs_data.items():
        normalized_stat = stat_map.get(stat.lower(), stat.lower())
        if isinstance(value, (int, float)):
            result[normalized_stat] = int(value)
    return result


def _parse_ivs(ivs_data: Dict[str, Any]) -> Dict[str, int]:
    """Parse IV data, normalizing stat names."""
    stat_map = {
        "hp": "hp",
        "atk": "atk",
        "def": "def",
        "spa": "spa",
        "spd": "spd",
        "spe": "spe",
    }
    result: Dict[str, int] = {}
    for stat, value in ivs_data.items():
        normalized_stat = stat_map.get(stat.lower(), stat.lower())
        if isinstance(value, (int, float)):
            result[normalized_stat] = int(value)
    return result


def get_randbats_data() -> Optional[RandbatsData]:
    """Get the cached randbats data.

    Returns None if init_randbats_data() hasn't been called yet.
    """
    return _randbats_cache


async def init_randbats_data(
    battle_format: str,
    url_template: str = "https://pkmn.github.io/randbats/data/{format}.json",
    timeout: float = 30.0,
) -> Optional[RandbatsData]:
    """Fetch and cache random battle sets from pkmn.github.io.

    Call this once at startup. After this, use get_randbats_data() to access
    the cached data from anywhere in the codebase.

    Args:
        battle_format: The battle format (e.g., "gen9randombattle")
        url_template: URL template with {format} placeholder
        timeout: Request timeout in seconds

    Returns:
        RandbatsData object with parsed Pokemon data, or None on failure
    """
    global _randbats_cache

    url = url_template.format(format=battle_format)
    logger.info(f"Fetching randbats data from {url}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=timeout)
            response.raise_for_status()
            raw_data = response.json()

        parsed = _parse_randbats_json(raw_data)
        _randbats_cache = RandbatsData(parsed)
        logger.info(f"Cached randbats data for {len(_randbats_cache)} Pokemon")
        return _randbats_cache
    except Exception as e:
        logger.warning(f"Failed to fetch randbats data: {e}")
        return None


# Keep for backwards compatibility
async def fetch_randbats_data(
    battle_format: str,
    url_template: str = "https://pkmn.github.io/randbats/data/{format}.json",
    timeout: float = 30.0,
) -> RandbatsData:
    """Fetch random battle sets from pkmn.github.io.

    Note: Prefer using init_randbats_data() at startup and get_randbats_data()
    elsewhere. This function is kept for backwards compatibility.
    """
    result = await init_randbats_data(battle_format, url_template, timeout)
    if result is None:
        raise RuntimeError("Failed to fetch randbats data")
    return result
