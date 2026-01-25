"""Damage calculator module using poke-env's built-in damage calculation."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from poke_env.battle import Battle, Move, Pokemon, PokemonType
from poke_env.calc import calculate_damage
from poke_env.data import GenData
from poke_env.stats import compute_raw_stats, STATS_TO_IDX

if TYPE_CHECKING:
    from src.battle import TeamsState

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
    # Optional item/ability context when multiple possibilities exist
    assumed_item: Optional[str] = None
    assumed_ability: Optional[str] = None


@dataclass
class MatchupResult:
    """Damage calculations for a matchup between two Pokemon."""

    attacker: str
    defender: str
    defender_hp_percent: float
    results: List[DamageResult]


class DamageCalculator:
    """Calculate damage for battle decisions using poke-env's built-in calculator."""

    def __init__(
        self,
        gen: int = 9,
        randbats_data=None,
        teams_state: Optional["TeamsState"] = None,
    ):
        self.gen = gen
        self.gen_data = GenData.from_gen(gen)
        self.randbats_data = randbats_data
        self.teams_state = teams_state

    def calculate_our_moves_vs_active(
        self, battle: Battle
    ) -> Optional[MatchupResult]:
        """Calculate damage for all our available moves vs opponent's active Pokemon.

        Calculates damage for all possible defender items to show ranges.
        """
        if not battle.active_pokemon or not battle.opponent_active_pokemon:
            return None

        attacker = battle.active_pokemon
        defender = battle.opponent_active_pokemon

        # Ensure both Pokemon have stats (estimate if needed)
        self._ensure_pokemon_stats(attacker, battle)
        self._ensure_pokemon_stats(defender, battle)

        results = []
        for move in battle.available_moves:
            # Calculate with item variants for opponent defender
            variant_results = self._calculate_with_variants(
                attacker, defender, move, battle,
                is_estimated=False,
                vary_defender=True,
            )
            results.extend(variant_results)

        return MatchupResult(
            attacker=attacker.species,
            defender=defender.species,
            defender_hp_percent=defender.current_hp_fraction * 100,
            results=results,
        )

    def calculate_our_moves_vs_bench(
        self, battle: Battle
    ) -> List[MatchupResult]:
        """Calculate our best move vs each seen opponent bench Pokemon.

        Calculates damage for all possible defender items to show ranges.
        """
        if not battle.active_pokemon:
            return []

        attacker = battle.active_pokemon

        # Ensure attacker has stats
        self._ensure_pokemon_stats(attacker, battle)

        matchups = []

        for pokemon_id, pokemon in battle.opponent_team.items():
            # Skip active Pokemon and fainted Pokemon
            if pokemon.active or pokemon.fainted:
                continue

            # Ensure bench Pokemon has stats
            self._ensure_pokemon_stats(pokemon, battle)

            results = []
            for move in battle.available_moves:
                # Calculate with item variants for opponent defender
                variant_results = self._calculate_with_variants(
                    attacker, pokemon, move, battle,
                    is_estimated=False,
                    vary_defender=True,
                )
                results.extend(variant_results)

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
        """Calculate opponent's damage vs our active Pokemon.

        Calculates damage for all possible attacker items to show ranges.
        """
        if not battle.active_pokemon or not battle.opponent_active_pokemon:
            return None

        attacker = battle.opponent_active_pokemon
        defender = battle.active_pokemon

        # Ensure both Pokemon have stats
        self._ensure_pokemon_stats(attacker, battle)
        self._ensure_pokemon_stats(defender, battle)

        # Get moves to calculate
        moves_data = self._get_opponent_moves(attacker)

        results = []
        for move_id, is_estimated in moves_data:
            move = self._get_move(move_id)
            if move:
                # Calculate with item variants for opponent attacker
                variant_results = self._calculate_with_variants(
                    attacker, defender, move, battle,
                    is_estimated=is_estimated,
                    vary_attacker=True,
                )
                results.extend(variant_results)

        return MatchupResult(
            attacker=attacker.species,
            defender=defender.species,
            defender_hp_percent=defender.current_hp_fraction * 100,
            results=results,
        )

    def calculate_their_moves_vs_bench(
        self, battle: Battle
    ) -> List[MatchupResult]:
        """Calculate opponent active's damage vs our bench Pokemon.

        Calculates damage for all possible attacker items to show ranges.
        """
        if not battle.opponent_active_pokemon:
            return []

        attacker = battle.opponent_active_pokemon
        self._ensure_pokemon_stats(attacker, battle)

        # Get opponent's moves
        moves_data = self._get_opponent_moves(attacker)

        matchups = []
        for pokemon in battle.available_switches:
            # Ensure bench Pokemon has stats
            self._ensure_pokemon_stats(pokemon, battle)

            results = []
            for move_id, is_estimated in moves_data:
                move = self._get_move(move_id)
                if move:
                    # Calculate with item variants for opponent attacker
                    variant_results = self._calculate_with_variants(
                        attacker, pokemon, move, battle,
                        is_estimated=is_estimated,
                        vary_attacker=True,
                    )
                    results.extend(variant_results)

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
        assumed_item: Optional[str] = None,
        assumed_ability: Optional[str] = None,
    ) -> Optional[DamageResult]:
        """Calculate damage for a single move with optional item/ability override."""
        try:
            # Get identifiers for the calc function
            attacker_id = self._get_pokemon_identifier(attacker, battle)
            defender_id = self._get_pokemon_identifier(defender, battle)

            if not attacker_id or not defender_id:
                return None

            min_dmg, max_dmg = calculate_damage(
                attacker_id, defender_id, move, battle
            )

            # Get defender's actual max HP from stats (not pokemon.max_hp which may be
            # on Showdown's percentage scale for opponents)
            defender_max_hp = self._get_actual_max_hp(defender, battle)

            # For opponents, current_hp is on 0-100 scale, so we need to convert
            # to actual HP for KO calculations
            is_opponent = any(p is defender for p in battle.opponent_team.values())
            if is_opponent and defender.current_hp is not None:
                # current_hp is a percentage (0-100), convert to actual HP
                defender_current_hp = int((defender.current_hp / 100) * defender_max_hp)
            else:
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
                assumed_item=assumed_item,
                assumed_ability=assumed_ability,
            )
        except Exception as e:
            logger.debug(f"Damage calc failed for {move.id}: {e}")
            return None

    def _calculate_with_variants(
        self,
        attacker: Pokemon,
        defender: Pokemon,
        move: Move,
        battle: Battle,
        is_estimated: bool,
        vary_attacker: bool = False,
        vary_defender: bool = False,
    ) -> List[DamageResult]:
        """Calculate damage for all item/ability variants of a Pokemon.

        If variants produce the same damage range, returns a single result.
        Otherwise returns results for each unique damage range.
        """
        # Get possible items and abilities for the Pokemon we're varying
        attacker_items = ["unknown_item"]
        defender_items = ["unknown_item"]
        attacker_abilities = [None]
        defender_abilities = [None]

        if vary_attacker and self.teams_state:
            state = self.teams_state.get_pokemon_state(attacker.species, is_opponent=True)
            if state:
                if state.revealed_item:
                    attacker_items = [state.revealed_item]
                elif state.possible_items:
                    attacker_items = [self._normalize_item(i) for i in state.possible_items]

                if state.revealed_ability:
                    attacker_abilities = [self._normalize_ability(state.revealed_ability)]
                elif state.possible_abilities:
                    attacker_abilities = [self._normalize_ability(a) for a in state.possible_abilities]

        if vary_defender and self.teams_state:
            state = self.teams_state.get_pokemon_state(defender.species, is_opponent=True)
            if state:
                if state.revealed_item:
                    defender_items = [state.revealed_item]
                elif state.possible_items:
                    defender_items = [self._normalize_item(i) for i in state.possible_items]

                if state.revealed_ability:
                    defender_abilities = [self._normalize_ability(state.revealed_ability)]
                elif state.possible_abilities:
                    defender_abilities = [self._normalize_ability(a) for a in state.possible_abilities]

        # Store original values to restore later
        original_attacker_item = attacker._item
        original_defender_item = defender._item
        original_attacker_ability = attacker._ability
        original_defender_ability = defender._ability

        results: List[DamageResult] = []
        seen_ranges: Dict[Tuple[float, float], DamageResult] = {}

        try:
            for atk_item in attacker_items:
                for def_item in defender_items:
                    for atk_ability in attacker_abilities:
                        for def_ability in defender_abilities:
                            # Set items and abilities for this calculation
                            if vary_attacker:
                                attacker._item = atk_item
                                if atk_ability:
                                    attacker._ability = atk_ability
                            if vary_defender:
                                defender._item = def_item
                                if def_ability:
                                    defender._ability = def_ability

                            # Build assumption strings
                            assumed_item = None
                            assumed_ability = None
                            if vary_attacker:
                                assumed_item = atk_item
                                assumed_ability = atk_ability
                            elif vary_defender:
                                assumed_item = def_item
                                assumed_ability = def_ability

                            result = self._calculate_single(
                                attacker, defender, move, battle, is_estimated,
                                assumed_item=assumed_item,
                                assumed_ability=assumed_ability,
                            )

                            if result:
                                range_key = (result.min_percent, result.max_percent)
                                if range_key not in seen_ranges:
                                    seen_ranges[range_key] = result
                                    results.append(result)
                                else:
                                    # Merge assumptions for same damage range
                                    existing = seen_ranges[range_key]
                                    if result.assumed_item and existing.assumed_item:
                                        if result.assumed_item not in existing.assumed_item:
                                            existing.assumed_item = f"{existing.assumed_item}/{result.assumed_item}"
                                    if result.assumed_ability and existing.assumed_ability:
                                        if result.assumed_ability not in existing.assumed_ability:
                                            existing.assumed_ability = f"{existing.assumed_ability}/{result.assumed_ability}"
        finally:
            # Restore original items and abilities
            attacker._item = original_attacker_item
            defender._item = original_defender_item
            attacker._ability = original_attacker_ability
            defender._ability = original_defender_ability

        # If all variants produced the same damage, clear the assumptions
        if len(results) == 1 and (results[0].assumed_item or results[0].assumed_ability):
            results[0] = DamageResult(
                move=results[0].move,
                min_damage=results[0].min_damage,
                max_damage=results[0].max_damage,
                min_percent=results[0].min_percent,
                max_percent=results[0].max_percent,
                ko_chance=results[0].ko_chance,
                is_estimated=results[0].is_estimated,
                assumed_item=None,  # Clear since all items give same result
                assumed_ability=None,
            )

        return results

    def _normalize_item(self, item: str) -> str:
        """Normalize item name for poke-env."""
        return item.lower().replace(" ", "").replace("-", "")

    def _normalize_ability(self, ability: str) -> str:
        """Normalize ability name for poke-env."""
        return ability.lower().replace(" ", "").replace("-", "")

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

    def _get_actual_max_hp(self, pokemon: Pokemon, battle: Battle) -> int:
        """Get the actual max HP for a Pokemon.

        For opponents, Showdown reports max_hp on a 0-100 percentage scale,
        but we need the actual HP stat for damage calculations.
        """
        # Try TeamsState first for cached calculated stats
        if self.teams_state:
            is_opponent = any(p is pokemon for p in battle.opponent_team.values())
            cached_state = self.teams_state.get_pokemon_state(pokemon.species, is_opponent)
            if cached_state and cached_state.stats:
                hp_stat = cached_state.stats.get("hp", 0)
                if hp_stat > 0:
                    return hp_stat

        # For our own Pokemon, max_hp is accurate
        is_opponent = any(p is pokemon for p in battle.opponent_team.values())
        if not is_opponent and pokemon.max_hp > 0:
            return pokemon.max_hp

        # Fallback: calculate from pokemon._stats if available
        if pokemon._stats and "hp" in pokemon._stats:
            return pokemon._stats["hp"]

        # Last resort: use pokemon.max_hp (may be on 0-100 scale for opponents)
        # This fallback is imperfect but better than nothing
        return pokemon.max_hp or 100

    def _ensure_pokemon_stats(self, pokemon: Pokemon, battle: Battle) -> None:
        """Set Pokemon stats and level from cached TeamsState or randbats data.

        Uses TeamsState cache when available (preferred), otherwise calculates
        from randbats data. This ensures consistent stats across turns.
        Items are handled separately via _calculate_with_variants for opponents.
        """
        # Try to get cached stats from TeamsState first
        if self.teams_state:
            # Determine if this is an opponent Pokemon
            is_opponent = any(p is pokemon for p in battle.opponent_team.values())
            cached_state = self.teams_state.get_pokemon_state(pokemon.species, is_opponent)

            if cached_state and cached_state.stats:
                pokemon._stats = dict(cached_state.stats)
                pokemon._level = cached_state.level
                # Note: We don't modify pokemon._max_hp here because for opponents,
                # Showdown uses a 0-100 percentage scale for current_hp, and changing
                # max_hp would break current_hp_fraction calculations.
                # Use _get_actual_max_hp() for damage percentage calculations instead.
                return

        # Fallback: calculate stats from randbats data
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

            # Always use randbats data when available
            if self.randbats_data:
                randbats_evs = self.randbats_data.get_evs(pokemon.species)
                randbats_ivs = self.randbats_data.get_ivs(pokemon.species)
                level = self.randbats_data.get_level(pokemon.species) or pokemon.level or 100

                # Convert dict to list format [HP, Atk, Def, SpA, SpD, Spe]
                stat_order = ["hp", "atk", "def", "spa", "spd", "spe"]
                evs = [randbats_evs[s] for s in stat_order]
                ivs = [randbats_ivs[s] for s in stat_order]
            else:
                # Fallback: Random Battles fixed spread estimate
                level = pokemon.level or 100
                evs = [85, 85, 85, 85, 85, 85]  # HP, Atk, Def, SpA, SpD, Spe
                ivs = [31, 31, 31, 31, 31, 31]

            raw_stats = compute_raw_stats(
                species_id, evs, ivs, level, "hardy", self.gen_data
            )

            # Set stats and level on pokemon
            pokemon._stats = {
                "hp": raw_stats[0],
                "atk": raw_stats[1],
                "def": raw_stats[2],
                "spa": raw_stats[3],
                "spd": raw_stats[4],
                "spe": raw_stats[5],
            }
            pokemon._level = level

            # Note: We don't modify pokemon._max_hp here because for opponents,
            # Showdown uses a 0-100 percentage scale for current_hp, and changing
            # max_hp would break current_hp_fraction calculations.
            # Use _get_actual_max_hp() for damage percentage calculations instead.

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
        # Group results by move
        move_results = _group_by_move(our_vs_active.results)
        for move, results in move_results.items():
            lines.append(_format_move_results(move, results))
        lines.append("")

    # Opponent's threats to us
    if their_vs_us and their_vs_us.results:
        lines.append(
            f"### {_format_species(their_vs_us.attacker)}'s Threats to "
            f"{_format_species(their_vs_us.defender)} ({their_vs_us.defender_hp_percent:.0f}% HP)"
        )
        # Group results by move
        move_results = _group_by_move(their_vs_us.results)
        for move, results in move_results.items():
            lines.append(_format_move_results(move, results, show_estimated=True))
        lines.append("")

    # Our moves vs opponent bench (summarized)
    if our_vs_bench:
        lines.append("### Your Moves vs Opponent Bench")
        for matchup in our_vs_bench:
            if matchup.results:
                best = max(matchup.results, key=lambda x: x.max_percent)
                ko_str = f", {best.ko_chance}" if best.ko_chance else ""
                assumption_str = _format_assumptions(best)
                lines.append(
                    f"- vs {_format_species(matchup.defender)}: "
                    f"Best = {_format_move(best.move)} ({best.min_percent}-{best.max_percent}%{ko_str}){assumption_str}"
                )
        lines.append("")

    # Threats to our bench (summarized)
    if their_vs_bench:
        lines.append("### Threats to Your Bench")
        for matchup in their_vs_bench:
            if matchup.results:
                worst = max(matchup.results, key=lambda x: x.max_percent)
                est_str = " (est)" if worst.is_estimated else ""
                assumption_str = _format_assumptions(worst)
                lines.append(
                    f"- {_format_species(matchup.defender)} takes: "
                    f"{_format_move(worst.move)} {worst.min_percent}-{worst.max_percent}%{est_str}{assumption_str}"
                )
        lines.append("")

    return "\n".join(lines)


def _group_by_move(results: List[DamageResult]) -> Dict[str, List[DamageResult]]:
    """Group damage results by move name."""
    grouped: Dict[str, List[DamageResult]] = {}
    for r in results:
        if r.move not in grouped:
            grouped[r.move] = []
        grouped[r.move].append(r)
    # Sort each group by max_percent descending
    for move in grouped:
        grouped[move] = sorted(grouped[move], key=lambda x: -x.max_percent)
    return grouped


def _format_move_results(
    move: str, results: List[DamageResult], show_estimated: bool = False
) -> str:
    """Format multiple damage results for a single move."""
    if len(results) == 1:
        r = results[0]
        ko_str = f", {r.ko_chance} KO" if r.ko_chance else ""
        est_str = " (estimated)" if show_estimated and r.is_estimated else ""
        return f"- {_format_move(move)}: {r.min_percent}-{r.max_percent}%{ko_str}{est_str}"
    else:
        # Multiple item/ability variants - show each
        parts = []
        for r in results:
            ko_str = f" {r.ko_chance} KO" if r.ko_chance else ""
            # Build assumption string (item and/or ability)
            assumptions = []
            if r.assumed_item:
                assumptions.append(r.assumed_item)
            if r.assumed_ability:
                assumptions.append(r.assumed_ability)
            assumption_str = f"w/{'+'.join(assumptions)}" if assumptions else ""
            parts.append(f"{r.min_percent}-{r.max_percent}%{ko_str} {assumption_str}".strip())
        est_str = " (estimated)" if show_estimated and results[0].is_estimated else ""
        return f"- {_format_move(move)}: {' | '.join(parts)}{est_str}"


def _format_assumptions(result: DamageResult) -> str:
    """Format item/ability assumptions for display."""
    assumptions = []
    if result.assumed_item:
        assumptions.append(result.assumed_item)
    if result.assumed_ability:
        assumptions.append(result.assumed_ability)
    return f" w/{'+'.join(assumptions)}" if assumptions else ""


def _format_species(species: str) -> str:
    """Format species name for display."""
    return species.replace("-", " ").title()


def _format_move(move_id: str) -> str:
    """Format move name for display."""
    return move_id.replace("-", " ").title()
