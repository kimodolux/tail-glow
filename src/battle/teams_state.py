"""Team state tracking for battles.

Maintains calculated stats and revealed information for both teams,
persisting across turns to avoid redundant calculations.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from poke_env.battle import Battle, Pokemon
from poke_env.data import GenData

from src.data.randbats import RandbatsData, RandbatsRole
from src.stats import StatsResolver

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

    def compatible_roles(self, randbats: RandbatsData) -> List[RandbatsRole]:
        """Roles whose move pool contains every revealed move."""
        return randbats.get_compatible_roles(self.species, self.revealed_moves)

    def narrowed_moves(self, randbats: RandbatsData) -> Set[str]:
        """Possible moves restricted to roles still compatible with reveals.

        Falls back to the full union when nothing has been revealed yet or
        when no role matches (data mismatch — keeps callers safe).
        """
        roles = self.compatible_roles(randbats)
        if not roles:
            return self.possible_moves
        narrowed: Set[str] = set()
        for role in roles:
            for move in role.moves:
                narrowed.add(move.lower().replace(" ", "").replace("-", ""))
        return narrowed

    def narrowed_items(self, randbats: RandbatsData) -> List[str]:
        """Possible items restricted to roles still compatible with reveals."""
        roles = self.compatible_roles(randbats)
        if not roles:
            return self.possible_items
        seen: Set[str] = set()
        narrowed: List[str] = []
        for role in roles:
            for item in role.items:
                if item not in seen:
                    seen.add(item)
                    narrowed.append(item)
        return narrowed or self.possible_items

    def narrowed_abilities(self, randbats: RandbatsData) -> List[str]:
        """Possible abilities restricted to roles still compatible with reveals."""
        roles = self.compatible_roles(randbats)
        if not roles:
            return self.possible_abilities
        seen: Set[str] = set()
        narrowed: List[str] = []
        for role in roles:
            for ability in role.abilities:
                if ability not in seen:
                    seen.add(ability)
                    narrowed.append(ability)
        return narrowed or self.possible_abilities

    def narrowed_tera_types(self, randbats: RandbatsData) -> List[str]:
        """Possible tera types restricted to roles still compatible with reveals."""
        roles = self.compatible_roles(randbats)
        if not roles:
            return self.possible_tera_types
        seen: Set[str] = set()
        narrowed: List[str] = []
        for role in roles:
            for tera in role.tera_types:
                if tera not in seen:
                    seen.add(tera)
                    narrowed.append(tera)
        return narrowed or self.possible_tera_types


class TeamsState:
    """Tracks both teams throughout the battle with cached stats."""

    def __init__(
        self,
        stats_resolver: StatsResolver,
        gen: int = 9,
        randbats_data: Optional[RandbatsData] = None,
    ):
        self.gen = gen
        self.gen_data = GenData.from_gen(gen)
        self.randbats_data = randbats_data
        self.stats_resolver = stats_resolver

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
        """Create a new PokemonState by asking the stats resolver."""
        species = pokemon.species
        side = "opponent" if is_opponent else "our"
        logger.info(f"TeamsState: Creating state for {side} Pokemon '{species}'")

        spread = self.stats_resolver.get_spread(pokemon, is_opponent=is_opponent)

        if not spread.stats:
            logger.warning(f"#### UNEXPECTED: Empty stats dict for '{species}' ####")
        else:
            logger.info(
                f"TeamsState: stats for '{species}' (L{spread.level}): "
                f"HP={spread.stats.get('hp')}, Atk={spread.stats.get('atk')}, "
                f"Def={spread.stats.get('def')}, SpA={spread.stats.get('spa')}, "
                f"SpD={spread.stats.get('spd')}, Spe={spread.stats.get('spe')} "
                f"(exact={spread.stats_are_exact})"
            )

        return PokemonState(
            species=species,
            level=spread.level,
            stats=dict(spread.stats),
            possible_moves=set(spread.possible_moves),
            possible_abilities=list(spread.possible_abilities),
            possible_items=list(spread.possible_items),
            possible_tera_types=list(spread.possible_tera_types),
        )

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
