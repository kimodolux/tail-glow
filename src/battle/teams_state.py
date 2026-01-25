"""Team state tracking for battles.

Maintains calculated stats and revealed information for both teams,
persisting across turns to avoid redundant calculations.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from poke_env.battle import Battle, Pokemon
from poke_env.data import GenData
from poke_env.stats import compute_raw_stats

from src.data.randbats import RandbatsData

logger = logging.getLogger(__name__)


@dataclass
class PokemonState:
    """Complete state for a Pokemon combining revealed info and randbats data."""

    # Identity
    species: str

    # Calculated stats (from randbats level/EVs/IVs) - computed once
    level: int
    stats: Dict[str, int]  # hp, atk, def, spa, spd, spe

    # Battle state (updates each turn)
    current_hp_percent: float = 100.0
    status: Optional[str] = None  # brn, par, slp, frz, psn, tox
    boosts: Dict[str, int] = field(default_factory=dict)  # atk: +2, spe: -1, etc.

    # Revealed info (updates as battle progresses)
    revealed_moves: List[str] = field(default_factory=list)
    revealed_ability: Optional[str] = None
    revealed_item: Optional[str] = None
    terastallized: bool = False
    tera_type: Optional[str] = None

    # Possible options (from randbats, static after init)
    possible_moves: Set[str] = field(default_factory=set)
    possible_abilities: List[str] = field(default_factory=list)
    possible_items: List[str] = field(default_factory=list)
    possible_tera_types: List[str] = field(default_factory=list)

    # Flags
    is_active: bool = False
    is_fainted: bool = False

    def unrevealed_moves(self) -> Set[str]:
        """Get moves that are possible but not yet revealed."""
        revealed_set = {m.lower().replace(" ", "").replace("-", "") for m in self.revealed_moves}
        return self.possible_moves - revealed_set


class TeamsState:
    """Tracks both teams throughout the battle with cached stats."""

    def __init__(self, gen: int = 9, randbats_data: Optional[RandbatsData] = None):
        self.gen = gen
        self.gen_data = GenData.from_gen(gen)
        self.randbats_data = randbats_data

        self.our_team: Dict[str, PokemonState] = {}  # species -> state
        self.their_team: Dict[str, PokemonState] = {}  # species -> state

    def update_from_battle(self, battle: Battle) -> None:
        """Update team states from current battle object."""
        self._update_our_team(battle)
        self._update_their_team(battle)

    def _update_our_team(self, battle: Battle) -> None:
        """Update our team from battle.team."""
        for pokemon_id, pokemon in battle.team.items():
            species = pokemon.species

            if species not in self.our_team:
                # First time seeing this Pokemon - calculate stats
                self.our_team[species] = self._create_pokemon_state(pokemon, is_opponent=False)

            # Update dynamic state
            self._update_dynamic_state(self.our_team[species], pokemon)

    def _update_their_team(self, battle: Battle) -> None:
        """Update opponent team from battle.opponent_team."""
        for pokemon_id, pokemon in battle.opponent_team.items():
            species = pokemon.species

            if species not in self.their_team:
                # First time seeing this Pokemon - calculate stats and load randbats data
                self.their_team[species] = self._create_pokemon_state(pokemon, is_opponent=True)

            # Update dynamic state and revealed info
            state = self.their_team[species]
            self._update_dynamic_state(state, pokemon)
            self._update_revealed_info(state, pokemon)

    def _create_pokemon_state(self, pokemon: Pokemon, is_opponent: bool) -> PokemonState:
        """Create a new PokemonState with calculated stats."""
        species = pokemon.species
        side = "opponent" if is_opponent else "our"
        logger.info(f"TeamsState: Creating state for {side} Pokemon '{species}'")

        # Calculate stats from randbats data
        level, stats = self._calculate_stats(pokemon)

        if not stats:
            logger.warning(f"#### UNEXPECTED: Empty stats dict for '{species}' ####")

        # Get possible options from randbats data
        possible_moves: Set[str] = set()
        possible_abilities: List[str] = []
        possible_items: List[str] = []
        possible_tera_types: List[str] = []

        if self.randbats_data:
            possible_moves = self.randbats_data.get_possible_moves(species)
            possible_abilities = self.randbats_data.get_possible_abilities(species)
            possible_items = self.randbats_data.get_possible_items(species)

            # Get tera types from randbats data
            randbats_pokemon = self.randbats_data.get_pokemon(species)
            if randbats_pokemon:
                for role in randbats_pokemon.roles.values():
                    possible_tera_types.extend(role.tera_types)
                possible_tera_types = list(set(possible_tera_types))  # Dedupe
            else:
                logger.warning(
                    f"#### UNEXPECTED: No randbats pokemon data for '{species}' "
                    f"when creating state ####"
                )
        else:
            logger.warning(
                f"#### UNEXPECTED: No randbats_data when creating state for '{species}' ####"
            )

        return PokemonState(
            species=species,
            level=level,
            stats=stats,
            possible_moves=possible_moves,
            possible_abilities=possible_abilities,
            possible_items=possible_items,
            possible_tera_types=possible_tera_types,
        )

    def _calculate_stats(self, pokemon: Pokemon) -> tuple[int, Dict[str, int]]:
        """Calculate stats using randbats data."""
        species = pokemon.species
        species_id = species.lower().replace("-", "").replace(" ", "")

        # Handle species not in pokedex
        if species_id not in self.gen_data.pokedex:
            base_species = species_id.split("-")[0] if "-" in species else species_id
            if base_species in self.gen_data.pokedex:
                logger.info(f"TeamsState: '{species}' not in pokedex, using base '{base_species}'")
                species_id = base_species
            else:
                # Fallback to pokemon's existing stats if available
                logger.warning(
                    f"#### UNEXPECTED: '{species}' not in pokedex and no base species found, "
                    f"using pokemon.stats fallback ####"
                )
                return pokemon.level or 100, dict(pokemon.stats) if pokemon.stats else {}

        # Get level/EVs/IVs from randbats data
        if self.randbats_data:
            randbats_level = self.randbats_data.get_level(species)
            if randbats_level:
                level = randbats_level
                logger.debug(f"TeamsState: '{species}' using randbats level {level}")
            else:
                level = pokemon.level or 100
                logger.warning(
                    f"#### UNEXPECTED: No randbats level for '{species}', "
                    f"using fallback level {level} ####"
                )
            evs_dict = self.randbats_data.get_evs(species)
            ivs_dict = self.randbats_data.get_ivs(species)

            stat_order = ["hp", "atk", "def", "spa", "spd", "spe"]
            evs = [evs_dict[s] for s in stat_order]
            ivs = [ivs_dict[s] for s in stat_order]
        else:
            level = pokemon.level or 100
            evs = [85, 85, 85, 85, 85, 85]
            ivs = [31, 31, 31, 31, 31, 31]
            logger.warning(
                f"#### UNEXPECTED: No randbats_data available for '{species}', "
                f"using fallback level={level}, EVs=85, IVs=31 ####"
            )

        raw_stats = compute_raw_stats(
            species_id, evs, ivs, level, "hardy", self.gen_data
        )

        stats = {
            "hp": raw_stats[0],
            "atk": raw_stats[1],
            "def": raw_stats[2],
            "spa": raw_stats[3],
            "spd": raw_stats[4],
            "spe": raw_stats[5],
        }

        logger.info(
            f"TeamsState: Calculated stats for '{species}' (L{level}): "
            f"HP={stats['hp']}, Atk={stats['atk']}, Def={stats['def']}, "
            f"SpA={stats['spa']}, SpD={stats['spd']}, Spe={stats['spe']}"
        )

        return level, stats

    def _update_dynamic_state(self, state: PokemonState, pokemon: Pokemon) -> None:
        """Update battle-dynamic state (HP, status, boosts, active/fainted)."""
        state.current_hp_percent = pokemon.current_hp_fraction * 100
        state.status = pokemon.status.name if pokemon.status else None
        state.boosts = dict(pokemon.boosts) if pokemon.boosts else {}
        state.is_active = pokemon.active
        state.is_fainted = pokemon.fainted

    def _update_revealed_info(self, state: PokemonState, pokemon: Pokemon) -> None:
        """Update revealed moves/ability/item for opponent Pokemon."""
        # Revealed moves
        if pokemon.moves:
            for move_id in pokemon.moves:
                normalized = move_id.lower().replace(" ", "").replace("-", "")
                if normalized not in [m.lower().replace(" ", "").replace("-", "") for m in state.revealed_moves]:
                    state.revealed_moves.append(move_id)

        # Revealed ability
        if pokemon.ability and not state.revealed_ability:
            state.revealed_ability = pokemon.ability

        # Revealed item
        if pokemon.item and pokemon.item != "unknown_item" and not state.revealed_item:
            state.revealed_item = pokemon.item

    def get_pokemon_state(self, species: str, is_opponent: bool) -> Optional[PokemonState]:
        """Get cached state for a Pokemon."""
        team = self.their_team if is_opponent else self.our_team
        return team.get(species)

    def get_stats(self, species: str, is_opponent: bool) -> Optional[Dict[str, int]]:
        """Get cached stats for a Pokemon."""
        state = self.get_pokemon_state(species, is_opponent)
        return state.stats if state else None

    def get_level(self, species: str, is_opponent: bool) -> Optional[int]:
        """Get cached level for a Pokemon."""
        state = self.get_pokemon_state(species, is_opponent)
        return state.level if state else None
