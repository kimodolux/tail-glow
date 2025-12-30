"""Speed calculation module for battle decisions.

Uses poke-env's stat utilities and randbats data to calculate speed
comparisons and priority move analysis.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from poke_env.battle import Battle, Move, Pokemon, Status
from poke_env.data import GenData
from poke_env.stats import compute_raw_stats

logger = logging.getLogger(__name__)


# Speed boost multipliers by stage
SPEED_STAGE_MULTIPLIERS = {
    -6: 2/8,
    -5: 2/7,
    -4: 2/6,
    -3: 2/5,
    -2: 2/4,
    -1: 2/3,
    0: 1.0,
    1: 3/2,
    2: 4/2,
    3: 5/2,
    4: 6/2,
    5: 7/2,
    6: 8/2,
}


@dataclass
class PriorityMove:
    """A move with non-zero priority."""
    move_id: str
    priority: int
    is_estimated: bool = False


@dataclass
class SpeedAnalysis:
    """Results of speed comparison between two Pokemon."""
    our_speed: int
    their_speed: int
    their_speed_with_scarf: Optional[int]
    we_outspeed: bool
    we_outspeed_if_they_scarf: bool
    our_priority_moves: list[PriorityMove] = field(default_factory=list)
    their_priority_moves: list[PriorityMove] = field(default_factory=list)
    trick_room_active: bool = False
    tailwind_active: bool = False
    opponent_tailwind_active: bool = False
    notes: list[str] = field(default_factory=list)


class SpeedCalculator:
    """Calculate speed comparisons for battle decisions."""

    def __init__(self, gen: int = 9, randbats_data=None):
        self.gen = gen
        self.gen_data = GenData.from_gen(gen)
        self.randbats_data = randbats_data

    def calculate_speed_matchup(
        self,
        battle: Battle,
        opponent_sets: Optional[dict[str, Any]] = None,
    ) -> Optional[SpeedAnalysis]:
        """Calculate speed comparison between active Pokemon.

        Args:
            battle: The current battle state
            opponent_sets: Optional randbats data for opponent Pokemon

        Returns:
            SpeedAnalysis with comparison results, or None if no active Pokemon
        """
        if not battle.active_pokemon or not battle.opponent_active_pokemon:
            return None

        our_pokemon = battle.active_pokemon
        their_pokemon = battle.opponent_active_pokemon

        # Calculate base speeds
        our_speed = self._get_speed(our_pokemon, is_opponent=False)
        their_speed = self._get_speed(their_pokemon, is_opponent=True)

        # Check for field conditions
        trick_room_active = self._is_trick_room_active(battle)
        tailwind_active = self._is_tailwind_active(battle, our_side=True)
        opponent_tailwind_active = self._is_tailwind_active(battle, our_side=False)

        # Apply speed modifiers
        our_modified = self._apply_speed_modifiers(
            our_speed, our_pokemon, tailwind_active
        )
        their_modified = self._apply_speed_modifiers(
            their_speed, their_pokemon, opponent_tailwind_active
        )

        # Calculate scarf scenario
        their_scarf_speed = None
        could_have_scarf = self._could_have_choice_scarf(their_pokemon, opponent_sets)
        if could_have_scarf:
            their_scarf_speed = int(their_modified * 1.5)

        # Determine who outspeeds
        if trick_room_active:
            we_outspeed = our_modified < their_modified
            we_outspeed_scarf = our_modified < their_scarf_speed if their_scarf_speed else we_outspeed
        else:
            we_outspeed = our_modified > their_modified
            we_outspeed_scarf = our_modified > their_scarf_speed if their_scarf_speed else we_outspeed

        # Get priority moves
        our_priority = self._get_priority_moves(
            battle.available_moves, is_estimated=False
        )
        their_priority = self._get_opponent_priority_moves(
            their_pokemon, opponent_sets
        )

        # Build notes
        notes = []
        if our_pokemon.status == Status.PAR:
            notes.append("You are paralyzed (Speed halved)")
        if their_pokemon.status == Status.PAR:
            notes.append("Opponent is paralyzed (Speed halved)")
        if trick_room_active:
            notes.append("Trick Room is active (slower moves first)")
        if tailwind_active:
            notes.append("Your Tailwind is active (Speed doubled)")
        if opponent_tailwind_active:
            notes.append("Opponent's Tailwind is active (Speed doubled)")
        if could_have_scarf:
            notes.append("Opponent could have Choice Scarf")

        return SpeedAnalysis(
            our_speed=our_modified,
            their_speed=their_modified,
            their_speed_with_scarf=their_scarf_speed,
            we_outspeed=we_outspeed,
            we_outspeed_if_they_scarf=we_outspeed_scarf,
            our_priority_moves=our_priority,
            their_priority_moves=their_priority,
            trick_room_active=trick_room_active,
            tailwind_active=tailwind_active,
            opponent_tailwind_active=opponent_tailwind_active,
            notes=notes,
        )

    def _get_speed(self, pokemon: Pokemon, is_opponent: bool) -> int:
        """Get the speed stat for a Pokemon."""
        # For our Pokemon, we have exact stats
        if not is_opponent and pokemon.stats:
            return pokemon.stats.get("spe")

        # For opponent, try to get from stats if available
        if pokemon.stats and pokemon.stats.get("spe"):
            return pokemon.stats.get("spe")

        # Estimate from randbats data
        return self._estimate_speed(pokemon)

    def _estimate_speed(self, pokemon: Pokemon) -> int:
        """Estimate speed stat from species data."""
        species_id = pokemon.species.lower().replace("-", "").replace(" ", "")

        # Try randbats data first
        if self.randbats_data:
            evs = self.randbats_data.get_evs(pokemon.species)
            ivs = self.randbats_data.get_ivs(pokemon.species)
            level = self.randbats_data.get_level(pokemon.species) or pokemon.level or 100
        else:
            # Randbats standard: 85 EVs, 31 IVs
            evs = {"spe": 85}
            ivs = {"spe": 31}
            level = pokemon.level or 100

        # Get species data
        if species_id not in self.gen_data.pokedex:
            base_species = species_id.split("-")[0] if "-" in pokemon.species else species_id
            if base_species in self.gen_data.pokedex:
                species_id = base_species
            else:
                return 100  # Default fallback

        try:
            stat_order = ["hp", "atk", "def", "spa", "spd", "spe"]
            evs_list = [evs.get(s, 84) for s in stat_order]
            ivs_list = [ivs.get(s, 31) for s in stat_order]

            raw_stats = compute_raw_stats(
                species_id, evs_list, ivs_list, level, "hardy", self.gen_data
            )
            return raw_stats[5]  # Speed is index 5
        except Exception as e:
            logger.debug(f"Failed to estimate speed for {pokemon.species}: {e}")
            return 100

    def _apply_speed_modifiers(
        self,
        base_speed: int,
        pokemon: Pokemon,
        tailwind: bool,
    ) -> int:
        """Apply speed modifiers (status, boosts, tailwind)."""
        speed = base_speed

        # Apply stat stages
        speed_stage = pokemon.boosts.get("spe", 0) if pokemon.boosts else 0
        speed = int(speed * SPEED_STAGE_MULTIPLIERS.get(speed_stage, 1.0))

        # Apply paralysis
        if pokemon.status == Status.PAR:
            speed = int(speed * 0.5)

        # Apply Tailwind
        if tailwind:
            speed = int(speed * 2)

        return speed

    def _is_trick_room_active(self, battle: Battle) -> bool:
        """Check if Trick Room is currently active."""
        # Check battle.fields for Trick Room
        if hasattr(battle, 'fields') and battle.fields:
            for field in battle.fields:
                if 'trickroom' in str(field).lower():
                    return True
        return False

    def _is_tailwind_active(self, battle: Battle, our_side: bool) -> bool:
        """Check if Tailwind is active on a side."""
        conditions = battle.side_conditions if our_side else battle.opponent_side_conditions
        if conditions:
            for condition in conditions:
                if 'tailwind' in str(condition).lower():
                    return True
        return False

    def _could_have_choice_scarf(
        self,
        pokemon: Pokemon,
        opponent_sets: Optional[dict[str, Any]],
    ) -> bool:
        """Check if opponent could be holding Choice Scarf."""
        # If item is known and it's not a scarf, return False
        if pokemon.item and pokemon.item.lower() not in ['', 'unknown']:
            return 'scarf' in pokemon.item.lower() or 'choicescarf' in pokemon.item.lower().replace(" ", "")

        # Check randbats data for possible items
        if self.randbats_data:
            possible_items = self.randbats_data.get_possible_items(pokemon.species)
            if possible_items:
                return any('scarf' in item.lower() for item in possible_items)

        # Default: could have scarf if item unknown
        return True

    def _get_priority_moves(
        self,
        moves: list[Move],
        is_estimated: bool,
    ) -> list[PriorityMove]:
        """Get moves with non-zero priority."""
        priority_moves = []
        for move in moves:
            if move.priority != 0:
                priority_moves.append(PriorityMove(
                    move_id=move.id,
                    priority=move.priority,
                    is_estimated=is_estimated,
                ))
        return sorted(priority_moves, key=lambda m: -m.priority)

    def _get_opponent_priority_moves(
        self,
        pokemon: Pokemon,
        opponent_sets: Optional[dict[str, Any]],
    ) -> list[PriorityMove]:
        """Get priority moves for opponent (revealed + estimated)."""
        priority_moves = []

        # Check revealed moves
        if pokemon.moves:
            for move_id in pokemon.moves:
                try:
                    move = Move(move_id, gen=self.gen)
                    if move.priority != 0:
                        priority_moves.append(PriorityMove(
                            move_id=move_id,
                            priority=move.priority,
                            is_estimated=False,
                        ))
                except Exception:
                    pass

        # Check randbats possible moves for priority
        if self.randbats_data:
            possible_moves = self.randbats_data.get_possible_moves(pokemon.species)
            revealed = set(pokemon.moves.keys()) if pokemon.moves else set()

            for move_id in possible_moves:
                if move_id in revealed:
                    continue
                try:
                    move = Move(move_id, gen=self.gen)
                    if move.priority != 0:
                        priority_moves.append(PriorityMove(
                            move_id=move_id,
                            priority=move.priority,
                            is_estimated=True,
                        ))
                except Exception:
                    pass

        return sorted(priority_moves, key=lambda m: -m.priority)


def format_speed_analysis(analysis: Optional[SpeedAnalysis]) -> str:
    """Format speed analysis for LLM consumption."""
    if not analysis:
        return ""

    lines = ["## Speed Analysis"]
    lines.append("")

    # Speed comparison
    verdict = "YOU OUTSPEED" if analysis.we_outspeed else "THEY OUTSPEED"
    lines.append(f"**Base:** You ({analysis.our_speed}) vs Them ({analysis.their_speed}) - **{verdict}**")

    # Scarf scenario
    if analysis.their_speed_with_scarf:
        scarf_verdict = "You still outspeed" if analysis.we_outspeed_if_they_scarf else "They outspeed"
        lines.append(f"**If they have Choice Scarf:** {analysis.their_speed_with_scarf} speed - {scarf_verdict}")

    # Priority moves
    if analysis.our_priority_moves or analysis.their_priority_moves:
        lines.append("")
        lines.append("**Priority Moves:**")
        if analysis.our_priority_moves:
            our_str = ", ".join(
                f"{m.move_id.replace('-', ' ').title()} (+{m.priority})"
                for m in analysis.our_priority_moves
            )
            lines.append(f"- Your options: {our_str}")
        else:
            lines.append("- Your options: None")

        if analysis.their_priority_moves:
            their_str = ", ".join(
                f"{m.move_id.replace('-', ' ').title()} (+{m.priority})" +
                (" (estimated)" if m.is_estimated else "")
                for m in analysis.their_priority_moves
            )
            lines.append(f"- Their options: {their_str}")
        else:
            lines.append("- Their options: None")

    # Notes
    if analysis.notes:
        lines.append("")
        lines.append("**Notes:**")
        for note in analysis.notes:
            lines.append(f"- {note}")

    # Final verdict
    lines.append("")
    if analysis.trick_room_active:
        lines.append("**Verdict:** Trick Room active - slower Pokemon moves first!")
    elif analysis.we_outspeed:
        lines.append("**Verdict:** You move first.")
    else:
        lines.append("**Verdict:** They move first. If at low HP, you may get KO'd before acting.")

    return "\n".join(lines)
