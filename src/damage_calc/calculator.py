"""Damage calculator module using poke-env's built-in damage calculation."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from poke_env.battle import Battle, Move, Pokemon, PokemonType
from poke_env.calc import calculate_damage
from poke_env.data import GenData
from poke_env.stats import compute_raw_stats, STATS_TO_IDX

logger = logging.getLogger(__name__)


@dataclass
class DamageResult:
    """Result of a damage calculation."""

    move: str
    min_damage: int
    max_damage: int
    min_percent: float
    max_percent: float
    ko_chance: Optional[str]  # "guaranteed", "75.0%", None
    is_estimated: bool  # True if move was guessed, not revealed


@dataclass
class MatchupResult:
    """Damage calculations for a matchup between two Pokemon."""

    attacker: str
    defender: str
    defender_hp_percent: float
    results: List[DamageResult]


class DamageCalculator:
    """Calculate damage for battle decisions using poke-env's built-in calculator."""

    def __init__(self, gen: int = 9, randbats_data=None):
        self.gen = gen
        self.gen_data = GenData.from_gen(gen)
        self.randbats_data = randbats_data

    def calculate_our_moves_vs_active(
        self, battle: Battle
    ) -> Optional[MatchupResult]:
        """Calculate damage for all our available moves vs opponent's active Pokemon."""
        if not battle.active_pokemon or not battle.opponent_active_pokemon:
            return None

        attacker = battle.active_pokemon
        defender = battle.opponent_active_pokemon

        # Ensure defender has stats (estimate if needed)
        self._ensure_pokemon_stats(defender, battle)

        results = []
        for move in battle.available_moves:
            result = self._calculate_single(
                attacker, defender, move, battle, is_estimated=False
            )
            if result:
                results.append(result)

        return MatchupResult(
            attacker=attacker.species,
            defender=defender.species,
            defender_hp_percent=defender.current_hp_fraction * 100,
            results=results,
        )

    def calculate_our_moves_vs_bench(
        self, battle: Battle
    ) -> List[MatchupResult]:
        """Calculate our best move vs each seen opponent bench Pokemon."""
        if not battle.active_pokemon:
            return []

        attacker = battle.active_pokemon
        matchups = []

        for pokemon_id, pokemon in battle.opponent_team.items():
            # Skip active Pokemon and fainted Pokemon
            if pokemon.active or pokemon.fainted:
                continue

            # Ensure bench Pokemon has stats
            self._ensure_pokemon_stats(pokemon, battle)

            results = []
            for move in battle.available_moves:
                result = self._calculate_single(
                    attacker, pokemon, move, battle, is_estimated=False
                )
                if result:
                    results.append(result)

            if results:
                matchups.append(
                    MatchupResult(
                        attacker=attacker.species,
                        defender=pokemon.species,
                        defender_hp_percent=pokemon.current_hp_fraction * 100,
                        results=results,
                    )
                )

        return matchups

    def calculate_their_moves_vs_us(
        self, battle: Battle
    ) -> Optional[MatchupResult]:
        """Calculate opponent's damage vs our active Pokemon."""
        if not battle.active_pokemon or not battle.opponent_active_pokemon:
            return None

        attacker = battle.opponent_active_pokemon
        defender = battle.active_pokemon

        # Ensure attacker has stats
        self._ensure_pokemon_stats(attacker, battle)

        # Get moves to calculate
        moves_data = self._get_opponent_moves(attacker)

        results = []
        for move_id, is_estimated in moves_data:
            move = self._get_move(move_id)
            if move:
                result = self._calculate_single(
                    attacker, defender, move, battle, is_estimated=is_estimated
                )
                if result:
                    results.append(result)

        return MatchupResult(
            attacker=attacker.species,
            defender=defender.species,
            defender_hp_percent=defender.current_hp_fraction * 100,
            results=results,
        )

    def calculate_their_moves_vs_bench(
        self, battle: Battle
    ) -> List[MatchupResult]:
        """Calculate opponent active's damage vs our bench Pokemon."""
        if not battle.opponent_active_pokemon:
            return []

        attacker = battle.opponent_active_pokemon
        self._ensure_pokemon_stats(attacker, battle)

        # Get opponent's moves
        moves_data = self._get_opponent_moves(attacker)

        matchups = []
        for pokemon in battle.available_switches:
            results = []
            for move_id, is_estimated in moves_data:
                move = self._get_move(move_id)
                if move:
                    result = self._calculate_single(
                        attacker, pokemon, move, battle, is_estimated=is_estimated
                    )
                    if result:
                        results.append(result)

            if results:
                matchups.append(
                    MatchupResult(
                        attacker=attacker.species,
                        defender=pokemon.species,
                        defender_hp_percent=pokemon.current_hp_fraction * 100,
                        results=results,
                    )
                )

        return matchups

    def _calculate_single(
        self,
        attacker: Pokemon,
        defender: Pokemon,
        move: Move,
        battle: Battle,
        is_estimated: bool,
    ) -> Optional[DamageResult]:
        """Calculate damage for a single move."""
        try:
            # Get identifiers for the calc function
            attacker_id = self._get_pokemon_identifier(attacker, battle)
            defender_id = self._get_pokemon_identifier(defender, battle)

            if not attacker_id or not defender_id:
                return None

            min_dmg, max_dmg = calculate_damage(
                attacker_id, defender_id, move, battle
            )

            # Calculate percentages
            defender_max_hp = defender.max_hp or 100
            defender_current_hp = (
                int(defender.current_hp_fraction * defender_max_hp)
                if defender.current_hp is None
                else defender.current_hp
            )

            min_percent = (min_dmg / defender_max_hp) * 100
            max_percent = (max_dmg / defender_max_hp) * 100

            # Determine KO chance
            ko_chance = self._calculate_ko_chance(
                min_dmg, max_dmg, defender_current_hp
            )

            return DamageResult(
                move=move.id,
                min_damage=min_dmg,
                max_damage=max_dmg,
                min_percent=round(min_percent, 1),
                max_percent=round(max_percent, 1),
                ko_chance=ko_chance,
                is_estimated=is_estimated,
            )
        except Exception as e:
            logger.debug(f"Damage calc failed for {move.id}: {e}")
            return None

    def _get_pokemon_identifier(
        self, pokemon: Pokemon, battle: Battle
    ) -> Optional[str]:
        """Get the battle identifier for a Pokemon."""
        # Check our team
        for pid, p in battle.team.items():
            if p is pokemon:
                return pid

        # Check opponent team
        for pid, p in battle.opponent_team.items():
            if p is pokemon:
                return pid

        return None

    def _ensure_pokemon_stats(self, pokemon: Pokemon, battle: Battle) -> None:
        """Ensure Pokemon has stats defined, estimating if needed."""
        if pokemon.stats and all(
            isinstance(v, (int, float)) for v in pokemon.stats.values()
        ):
            return

        # Need to estimate stats for opponent Pokemon
        species_id = pokemon.species.lower().replace("-", "").replace(" ", "")

        try:
            # Get base stats from pokedex
            if species_id not in self.gen_data.pokedex:
                # Try without forme suffix
                base_species = species_id.split("-")[0] if "-" in pokemon.species else species_id
                if base_species in self.gen_data.pokedex:
                    species_id = base_species
                else:
                    logger.debug(f"Species {pokemon.species} not found in pokedex")
                    return

            level = pokemon.level or 100

            # Use randbats data if available, otherwise fall back to estimates
            if self.randbats_data:
                randbats_evs = self.randbats_data.get_evs(pokemon.species)
                randbats_ivs = self.randbats_data.get_ivs(pokemon.species)
                randbats_level = self.randbats_data.get_level(pokemon.species)

                if randbats_level:
                    level = randbats_level

                # Convert dict to list format [HP, Atk, Def, SpA, SpD, Spe]
                stat_order = ["hp", "atk", "def", "spa", "spd", "spe"]
                evs = [randbats_evs.get(s, 84) for s in stat_order]
                ivs = [randbats_ivs.get(s, 31) for s in stat_order]
            else:
                # Fallback: Random Battles fixed spread estimate
                evs = [84, 84, 84, 84, 84, 84]  # HP, Atk, Def, SpA, SpD, Spe
                ivs = [31, 31, 31, 31, 31, 31]

            raw_stats = compute_raw_stats(
                species_id, evs, ivs, level, "hardy", self.gen_data
            )

            # Set stats on pokemon
            pokemon._stats = {
                "hp": raw_stats[0],
                "atk": raw_stats[1],
                "def": raw_stats[2],
                "spa": raw_stats[3],
                "spd": raw_stats[4],
                "spe": raw_stats[5],
            }

            # Also set max_hp if not set
            if pokemon.max_hp is None:
                pokemon._max_hp = raw_stats[0]

        except Exception as e:
            logger.debug(f"Failed to estimate stats for {pokemon.species}: {e}")

    def _get_opponent_moves(
        self, pokemon: Pokemon
    ) -> List[Tuple[str, bool]]:
        """Get moves to calculate for opponent Pokemon.

        Returns list of (move_id, is_estimated) tuples.
        """
        moves = []

        # First, add revealed moves
        if pokemon.moves:
            for move_id in pokemon.moves:
                moves.append((move_id, False))

        # If we don't have 4 moves, estimate threatening moves
        if len(moves) < 4:
            estimated = self._estimate_threatening_moves(pokemon, len(moves))
            moves.extend(estimated)

        return moves[:4]  # Max 4 moves

    def _estimate_threatening_moves(
        self, pokemon: Pokemon, existing_count: int
    ) -> List[Tuple[str, bool]]:
        """Estimate most threatening moves for a Pokemon based on its species."""
        # Try randbats data first for more accurate move prediction
        if self.randbats_data:
            possible_moves = self.randbats_data.get_possible_moves(pokemon.species)
            if possible_moves:
                return self._score_moves_from_pool(
                    pokemon, possible_moves, existing_count
                )

        # Fallback to learnset estimation
        species_id = pokemon.species.lower().replace("-", "").replace(" ", "")

        # Get learnset for this Pokemon
        learnset = self.gen_data.learnset.get(species_id, {})
        if not learnset:
            # Try base species
            base_species = species_id.split("-")[0] if "-" in pokemon.species else species_id
            learnset = self.gen_data.learnset.get(base_species, {})

        if not learnset:
            return []

        return self._score_moves_from_pool(
            pokemon, set(learnset.keys()), existing_count
        )

    def _score_moves_from_pool(
        self, pokemon: Pokemon, move_pool: set, existing_count: int
    ) -> List[Tuple[str, bool]]:
        """Score and filter moves from a given move pool."""
        # Get Pokemon's types for STAB consideration
        pokemon_types = [t.name.lower() for t in pokemon.types if t]

        # Score moves by threat level
        move_scores: List[Tuple[str, int]] = []

        for move_id in move_pool:
            # Normalize move ID to match gen_data format
            normalized_move = move_id.lower().replace(" ", "").replace("-", "")
            move_data = self.gen_data.moves.get(normalized_move, {})
            if not move_data:
                continue

            # Skip status moves for damage calc purposes
            category = move_data.get("category", "")
            if category == "Status":
                continue

            base_power = move_data.get("basePower", 0)
            if base_power == 0:
                continue

            # Calculate threat score
            score = base_power

            # STAB bonus
            move_type = move_data.get("type", "").lower()
            if move_type in pokemon_types:
                score = int(score * 1.5)

            # Accuracy penalty
            accuracy = move_data.get("accuracy", 100)
            if accuracy and accuracy < 100:
                score = int(score * accuracy / 100)

            move_scores.append((normalized_move, score))

        # Sort by score descending
        move_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top moves we don't already have
        existing_moves = {m[0] for m in self._get_revealed_moves(pokemon)}
        estimated = []
        for move_id, _ in move_scores:
            if move_id not in existing_moves and len(estimated) < (4 - existing_count):
                estimated.append((move_id, True))

        return estimated

    def _get_revealed_moves(self, pokemon: Pokemon) -> List[Tuple[str, bool]]:
        """Get revealed moves for a Pokemon."""
        if pokemon.moves:
            return [(move_id, False) for move_id in pokemon.moves]
        return []

    def _get_move(self, move_id: str) -> Optional[Move]:
        """Get a Move object from move ID."""
        try:
            return Move(move_id, gen=self.gen)
        except Exception:
            return None

    def _calculate_ko_chance(
        self, min_dmg: int, max_dmg: int, current_hp: int
    ) -> Optional[str]:
        """Calculate KO chance from damage range."""
        if min_dmg >= current_hp:
            return "guaranteed"
        elif max_dmg >= current_hp:
            # Estimate probability (16 damage rolls)
            # Simplified: assume uniform distribution
            range_size = max_dmg - min_dmg + 1
            ko_rolls = max_dmg - current_hp + 1
            if ko_rolls > 0:
                chance = (ko_rolls / range_size) * 100
                return f"{chance:.0f}%"
        return None


def format_damage_calculations(
    our_vs_active: Optional[MatchupResult],
    our_vs_bench: List[MatchupResult],
    their_vs_us: Optional[MatchupResult],
    their_vs_bench: List[MatchupResult],
) -> str:
    """Format damage calculation results for LLM consumption."""
    lines = []
    lines.append("## Damage Calculations")
    lines.append("")

    # Our moves vs opponent active
    if our_vs_active and our_vs_active.results:
        lines.append(
            f"### Your Moves vs {_format_species(our_vs_active.defender)} "
            f"({our_vs_active.defender_hp_percent:.0f}% HP)"
        )
        for r in sorted(our_vs_active.results, key=lambda x: -x.max_percent):
            ko_str = f", {r.ko_chance} KO" if r.ko_chance else ""
            lines.append(f"- {_format_move(r.move)}: {r.min_percent}-{r.max_percent}%{ko_str}")
        lines.append("")

    # Opponent's threats to us
    if their_vs_us and their_vs_us.results:
        lines.append(
            f"### {_format_species(their_vs_us.attacker)}'s Threats to "
            f"{_format_species(their_vs_us.defender)} ({their_vs_us.defender_hp_percent:.0f}% HP)"
        )
        for r in sorted(their_vs_us.results, key=lambda x: -x.max_percent):
            est_str = " (estimated)" if r.is_estimated else ""
            ko_str = f", {r.ko_chance} KO" if r.ko_chance else ""
            lines.append(f"- {_format_move(r.move)}: {r.min_percent}-{r.max_percent}%{ko_str}{est_str}")
        lines.append("")

    # Our moves vs opponent bench (summarized)
    if our_vs_bench:
        lines.append("### Your Moves vs Opponent Bench")
        for matchup in our_vs_bench:
            if matchup.results:
                best = max(matchup.results, key=lambda x: x.max_percent)
                ko_str = f", {best.ko_chance}" if best.ko_chance else ""
                lines.append(
                    f"- vs {_format_species(matchup.defender)}: "
                    f"Best = {_format_move(best.move)} ({best.min_percent}-{best.max_percent}%{ko_str})"
                )
        lines.append("")

    # Threats to our bench (summarized)
    if their_vs_bench:
        lines.append("### Threats to Your Bench")
        for matchup in their_vs_bench:
            if matchup.results:
                worst = max(matchup.results, key=lambda x: x.max_percent)
                est_str = " (est)" if worst.is_estimated else ""
                lines.append(
                    f"- {_format_species(matchup.defender)} takes: "
                    f"{_format_move(worst.move)} {worst.min_percent}-{worst.max_percent}%{est_str}"
                )
        lines.append("")

    return "\n".join(lines)


def _format_species(species: str) -> str:
    """Format species name for display."""
    return species.replace("-", " ").title()


def _format_move(move_id: str) -> str:
    """Format move name for display."""
    return move_id.replace("-", " ").title()
