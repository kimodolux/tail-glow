"""Matchup calculator node for pre-computing Pokemon pair outcomes.

This node calculates win/lose/draw outcomes for all Pokemon pairs,
considering current HP, status, and stat boosts. Results are cached
and recalculated when state changes.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from poke_env.battle import Battle, Pokemon

from src.agent.state import AgentState
from src.damage_calc.calculator import DamageCalculator, DamageResult

logger = logging.getLogger(__name__)


@dataclass
class MatchupOutcome:
    """Result of a Pokemon pair matchup simulation."""

    our_pokemon: str
    their_pokemon: str
    outcome: str  # "win", "lose", "draw"
    our_remaining_hp_percent: float  # HP% remaining if we win
    their_remaining_hp_percent: float  # HP% remaining if they win
    turns_to_resolve: int
    notes: str  # e.g., "We outspeed and 2HKO, they 3HKO"


def calculate_matchup_node(state: AgentState) -> dict[str, Any]:
    """Calculate matchup outcomes for all Pokemon pairs.

    This node computes win/lose/draw outcomes for each of our Pokemon
    against each revealed opponent Pokemon, considering:
    - Current HP and status
    - Speed comparison (who attacks first)
    - Damage calculations for both sides
    - Turns to KO for each side

    Args:
        state: Current agent state with battle_object and damage calculations

    Returns:
        Dict with matchup_results mapping (our_pokemon, their_pokemon) to MatchupOutcome
    """
    battle: Optional[Battle] = state.get("battle_object")
    if not battle:
        return {"matchup_results": {}}

    damage_calc_raw = state.get("damage_calc_raw", {})
    speed_calc_raw = state.get("speed_calc_raw", {})
    opponent_sets = state.get("opponent_sets", {})

    calculator = MatchupCalculator(
        battle=battle,
        damage_calc_raw=damage_calc_raw,
        speed_calc_raw=speed_calc_raw,
        opponent_sets=opponent_sets,
    )

    results = calculator.calculate_all_matchups()

    return {"matchup_results": results}


class MatchupCalculator:
    """Calculates win/lose/draw outcomes for Pokemon pairs."""

    def __init__(
        self,
        battle: Battle,
        damage_calc_raw: dict[str, Any],
        speed_calc_raw: dict[str, Any],
        opponent_sets: dict[str, Any],
    ):
        self.battle = battle
        self.damage_calc_raw = damage_calc_raw
        self.speed_calc_raw = speed_calc_raw
        self.opponent_sets = opponent_sets
        self.damage_calculator = DamageCalculator(gen=9, randbats_data=None)

    def calculate_all_matchups(self) -> dict[tuple[str, str], dict[str, Any]]:
        """Calculate matchups for all our Pokemon vs all revealed opponent Pokemon."""
        results = {}

        # Get our available Pokemon (active + switches)
        our_pokemon = self._get_our_pokemon()

        # Get revealed opponent Pokemon
        their_pokemon = self._get_their_pokemon()

        for ours in our_pokemon:
            for theirs in their_pokemon:
                key = (ours.species, theirs.species)
                outcome = self._calculate_single_matchup(ours, theirs)
                if outcome:
                    results[key] = {
                        "outcome": outcome.outcome,
                        "our_remaining_hp_percent": outcome.our_remaining_hp_percent,
                        "their_remaining_hp_percent": outcome.their_remaining_hp_percent,
                        "turns_to_resolve": outcome.turns_to_resolve,
                        "notes": outcome.notes,
                    }

        return results

    def _get_our_pokemon(self) -> list[Pokemon]:
        """Get all our non-fainted Pokemon."""
        pokemon = []
        if self.battle.active_pokemon and not self.battle.active_pokemon.fainted:
            pokemon.append(self.battle.active_pokemon)
        for p in self.battle.available_switches:
            if not p.fainted:
                pokemon.append(p)
        return pokemon

    def _get_their_pokemon(self) -> list[Pokemon]:
        """Get all revealed non-fainted opponent Pokemon."""
        pokemon = []
        for p in self.battle.opponent_team.values():
            if not p.fainted:
                pokemon.append(p)
        return pokemon

    def _calculate_single_matchup(
        self, ours: Pokemon, theirs: Pokemon
    ) -> Optional[MatchupOutcome]:
        """Calculate the outcome of a 1v1 matchup between two Pokemon."""
        try:
            # Get damage data for this matchup
            our_damage = self._get_best_damage(ours, theirs, is_our_attack=True)
            their_damage = self._get_best_damage(theirs, ours, is_our_attack=False)

            if not our_damage or not their_damage:
                return None

            # Get HP values
            our_hp = ours.current_hp_fraction * 100
            their_hp = theirs.current_hp_fraction * 100

            # Calculate turns to KO
            our_turns_to_ko = self._turns_to_ko(our_damage, their_hp)
            their_turns_to_ko = self._turns_to_ko(their_damage, our_hp)

            # Determine who outspeeds
            we_outspeed = self._we_outspeed(ours, theirs)

            # Simulate the fight
            outcome, our_remaining, their_remaining, turns = self._simulate_fight(
                our_hp=our_hp,
                their_hp=their_hp,
                our_damage_per_turn=our_damage,
                their_damage_per_turn=their_damage,
                we_outspeed=we_outspeed,
            )

            # Generate notes
            notes = self._generate_notes(
                we_outspeed=we_outspeed,
                our_turns_to_ko=our_turns_to_ko,
                their_turns_to_ko=their_turns_to_ko,
            )

            return MatchupOutcome(
                our_pokemon=ours.species,
                their_pokemon=theirs.species,
                outcome=outcome,
                our_remaining_hp_percent=round(our_remaining, 1),
                their_remaining_hp_percent=round(their_remaining, 1),
                turns_to_resolve=turns,
                notes=notes,
            )

        except Exception as e:
            logger.debug(f"Failed to calculate matchup {ours.species} vs {theirs.species}: {e}")
            return None

    def _get_best_damage(
        self, attacker: Pokemon, defender: Pokemon, is_our_attack: bool
    ) -> Optional[float]:
        """Get the best average damage percentage from attacker to defender."""
        # Try to get from pre-calculated damage data
        if is_our_attack:
            # Check our_vs_active and our_vs_bench
            matchups = []
            if self.damage_calc_raw.get("our_vs_active"):
                matchups.append(self.damage_calc_raw["our_vs_active"])
            matchups.extend(self.damage_calc_raw.get("our_vs_bench", []))

            for matchup in matchups:
                if (
                    matchup.attacker == attacker.species
                    and matchup.defender == defender.species
                ):
                    if matchup.results:
                        best = max(matchup.results, key=lambda r: r.max_percent)
                        return (best.min_percent + best.max_percent) / 2
        else:
            # Check their_vs_us and their_vs_bench
            matchups = []
            if self.damage_calc_raw.get("their_vs_us"):
                matchups.append(self.damage_calc_raw["their_vs_us"])
            matchups.extend(self.damage_calc_raw.get("their_vs_bench", []))

            for matchup in matchups:
                if (
                    matchup.attacker == attacker.species
                    and matchup.defender == defender.species
                ):
                    if matchup.results:
                        best = max(matchup.results, key=lambda r: r.max_percent)
                        return (best.min_percent + best.max_percent) / 2

        # Fallback: estimate damage (simplified)
        return self._estimate_damage(attacker, defender)

    def _estimate_damage(self, attacker: Pokemon, defender: Pokemon) -> float:
        """Estimate average damage when pre-calculated data isn't available."""
        # Very rough estimate based on type matchup and stats
        # This is a fallback and should rarely be needed
        return 25.0  # Default to 25% damage per turn

    def _turns_to_ko(self, damage_per_turn: float, target_hp: float) -> int:
        """Calculate turns needed to KO a target."""
        if damage_per_turn <= 0:
            return 999  # Can't KO
        return max(1, int((target_hp / damage_per_turn) + 0.99))  # Ceiling

    def _we_outspeed(self, ours: Pokemon, theirs: Pokemon) -> bool:
        """Determine if our Pokemon outspeeds theirs."""
        # Use pre-calculated speed data if available for active matchup
        if self.speed_calc_raw:
            if (
                self.battle.active_pokemon
                and ours.species == self.battle.active_pokemon.species
                and self.battle.opponent_active_pokemon
                and theirs.species == self.battle.opponent_active_pokemon.species
            ):
                return self.speed_calc_raw.get("we_outspeed", True)

        # Estimate based on base stats
        our_speed = self._get_pokemon_speed(ours)
        their_speed = self._get_pokemon_speed(theirs)

        return our_speed > their_speed

    def _get_pokemon_speed(self, pokemon: Pokemon) -> int:
        """Get the effective speed of a Pokemon."""
        if pokemon.stats and pokemon.stats.get("spe"):
            base_speed = pokemon.stats["spe"]
        else:
            base_speed = 100  # Default fallback

        # Apply stat stages
        speed_stage = pokemon.boosts.get("spe", 0) if pokemon.boosts else 0
        multipliers = {
            -6: 2 / 8, -5: 2 / 7, -4: 2 / 6, -3: 2 / 5, -2: 2 / 4, -1: 2 / 3,
            0: 1.0,
            1: 3 / 2, 2: 4 / 2, 3: 5 / 2, 4: 6 / 2, 5: 7 / 2, 6: 8 / 2,
        }
        speed = int(base_speed * multipliers.get(speed_stage, 1.0))

        # Apply paralysis
        if pokemon.status and str(pokemon.status).lower() == "par":
            speed = int(speed * 0.5)

        return speed

    def _simulate_fight(
        self,
        our_hp: float,
        their_hp: float,
        our_damage_per_turn: float,
        their_damage_per_turn: float,
        we_outspeed: bool,
    ) -> tuple[str, float, float, int]:
        """Simulate a fight to determine outcome.

        Returns:
            Tuple of (outcome, our_remaining_hp, their_remaining_hp, turns)
        """
        turns = 0
        max_turns = 20  # Safety limit

        while our_hp > 0 and their_hp > 0 and turns < max_turns:
            turns += 1

            if we_outspeed:
                # We attack first
                their_hp -= our_damage_per_turn
                if their_hp <= 0:
                    break
                # They attack back
                our_hp -= their_damage_per_turn
            else:
                # They attack first
                our_hp -= their_damage_per_turn
                if our_hp <= 0:
                    break
                # We attack back
                their_hp -= our_damage_per_turn

        # Determine outcome
        if our_hp > 0 and their_hp <= 0:
            return ("win", max(0, our_hp), 0, turns)
        elif their_hp > 0 and our_hp <= 0:
            return ("lose", 0, max(0, their_hp), turns)
        else:
            return ("draw", max(0, our_hp), max(0, their_hp), turns)

    def _generate_notes(
        self, we_outspeed: bool, our_turns_to_ko: int, their_turns_to_ko: int
    ) -> str:
        """Generate a human-readable note about the matchup."""
        speed_note = "We outspeed" if we_outspeed else "They outspeed"

        our_ko_text = f"{our_turns_to_ko}HKO" if our_turns_to_ko <= 4 else "slow KO"
        their_ko_text = f"{their_turns_to_ko}HKO" if their_turns_to_ko <= 4 else "slow KO"

        return f"{speed_note}, we {our_ko_text}, they {their_ko_text}"


def format_matchup_results(
    matchup_results: Optional[dict[tuple[str, str], dict[str, Any]]],
    our_active: Optional[str] = None,
) -> str:
    """Format matchup results for LLM consumption.

    Args:
        matchup_results: Dict mapping (our_pokemon, their_pokemon) to outcome data
        our_active: Species name of our active Pokemon (to highlight relevant matchups)

    Returns:
        Formatted string for LLM
    """
    if not matchup_results:
        return ""

    lines = ["## Matchup Analysis"]
    lines.append("")

    # Group by our Pokemon
    by_ours: dict[str, list[tuple[str, dict]]] = {}
    for (ours, theirs), data in matchup_results.items():
        if ours not in by_ours:
            by_ours[ours] = []
        by_ours[ours].append((theirs, data))

    # Sort to show active Pokemon first
    sorted_ours = sorted(by_ours.keys(), key=lambda x: (x != our_active, x))

    for ours in sorted_ours:
        matchups = by_ours[ours]
        marker = " (active)" if ours == our_active else ""
        lines.append(f"### {_format_species(ours)}{marker}")

        for theirs, data in sorted(matchups, key=lambda x: x[0]):
            outcome = data["outcome"].upper()
            if outcome == "WIN":
                remaining = f"with {data['our_remaining_hp_percent']:.0f}% HP"
            elif outcome == "LOSE":
                remaining = f"they have {data['their_remaining_hp_percent']:.0f}% HP"
            else:
                remaining = "mutual KO"

            lines.append(
                f"- vs {_format_species(theirs)}: **{outcome}** {remaining} "
                f"({data['turns_to_resolve']} turns) - {data['notes']}"
            )

        lines.append("")

    return "\n".join(lines)


def _format_species(species: str) -> str:
    """Format species name for display."""
    return species.replace("-", " ").title()
