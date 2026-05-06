"""Per-game memory store for battle state tracking."""

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .event_parser import ParsedTurnEvent

logger = logging.getLogger(__name__)

# Rolling window size for turn history
TURN_HISTORY_WINDOW = 5


@dataclass
class OpponentPattern:
    """Tracks opponent behavioral tendencies (raw stats only)."""

    total_turns: int = 0
    switches: int = 0  # How often they switch
    switch_on_threat: int = 0  # Switches when we have super-effective
    stays_in_bad_matchup: int = 0  # Stays when they shouldn't
    setup_moves_used: int = 0  # Swords Dance, Calm Mind, etc.
    predicted_our_switch: int = 0  # Used Pursuit, or predicted with coverage

    @property
    def switch_rate(self) -> float:
        """Calculate switch rate as fraction."""
        return self.switches / max(self.total_turns, 1)


@dataclass
class StrategicNote:
    """An observation the agent makes about the game state."""

    turn: int
    category: str  # "threat", "win_condition", "observation"
    content: str
    pokemon_involved: list[str] = field(default_factory=list)


# Common setup moves to detect
SETUP_MOVES = {
    "swordsdance",
    "nastyplot",
    "calmmind",
    "dragondance",
    "shellsmash",
    "quiverdance",
    "bulkup",
    "irondefense",
    "amnesia",
    "agility",
    "rockpolish",
    "autotomize",
    "coil",
    "curse",
    "growth",
    "workup",
    "honeclaws",
    "bellydrum",
    "tailglow",
    "geomancy",
    "shiftgear",
    "victorydance",
}


class GameMemory:
    """Per-game memory store for battle state tracking."""

    def __init__(self):
        # Rolling window of last N turns
        self.turn_events: deque[ParsedTurnEvent] = deque(maxlen=TURN_HISTORY_WINDOW)
        self.opponent_pattern: OpponentPattern = OpponentPattern()
        self.strategic_notes: list[StrategicNote] = []

        # Prediction tracking
        self.predictions: dict[int, str] = {}  # turn -> what we predicted
        self.outcomes: dict[int, str] = {}  # turn -> what actually happened
        self.correct_predictions: int = 0
        self.total_predictions: int = 0

    def add_turn_event(self, event: ParsedTurnEvent) -> None:
        """Record what happened this turn (auto-evicts old turns)."""
        self.turn_events.append(event)
        self._update_opponent_patterns(event)

    def _update_opponent_patterns(self, event: ParsedTurnEvent) -> None:
        """Update opponent pattern stats from turn event."""
        self.opponent_pattern.total_turns += 1

        # Track switches
        if event.opponent_action.startswith("switch:"):
            self.opponent_pattern.switches += 1

        # Track setup moves
        if event.opponent_action.startswith("move:"):
            move_name = event.opponent_action.split(":", 1)[1].lower().replace(" ", "")
            if move_name in SETUP_MOVES:
                self.opponent_pattern.setup_moves_used += 1

    def add_strategic_note(
        self,
        turn: int,
        category: str,
        content: str,
        pokemon: Optional[list[str]] = None,
    ) -> None:
        """Add an observation about the game."""
        self.strategic_notes.append(
            StrategicNote(turn, category, content, pokemon or [])
        )

    def record_prediction(self, turn: int, prediction: str, outcome: str) -> None:
        """Record prediction and whether it was correct (legacy string-based)."""
        self.predictions[turn] = prediction
        self.outcomes[turn] = outcome
        self.total_predictions += 1

        # Simple check - see if prediction appears in outcome
        if prediction.lower() in outcome.lower():
            self.correct_predictions += 1

    def record_structured_prediction(
        self, turn: int, prediction: dict, outcome: str
    ) -> None:
        """Record and evaluate a structured prediction distribution.

        Args:
            turn: Turn number
            prediction: Dict with moves, switches, top_prediction, reasoning
            outcome: What opponent actually did (e.g., "move:Ice Beam")
        """
        self.total_predictions += 1

        # Extract action name from outcome (e.g., "move:Ice Beam" → "Ice Beam")
        outcome_action = outcome.split(":", 1)[1] if ":" in outcome else outcome
        outcome_norm = self._normalize_action(outcome_action)

        # Check if top prediction was correct
        top = prediction.get("top_prediction", {})
        top_action = top.get("action", "")
        top_action_norm = self._normalize_action(top_action)

        if top_action_norm and top_action_norm in outcome_norm:
            self.correct_predictions += 1

        # Store for history (use top prediction for display)
        self.predictions[turn] = top_action or "unknown"
        self.outcomes[turn] = outcome_action

        # Log probability assigned to actual outcome (for calibration analysis)
        # Structure: {"action": {"probability": 0.45, "reasoning": "..."}}
        all_actions = {**prediction.get("moves", {}), **prediction.get("switches", {})}
        for action, data in all_actions.items():
            action_norm = self._normalize_action(action)
            if action_norm in outcome_norm:
                # Handle both new dict structure and legacy float
                if isinstance(data, dict):
                    prob = data.get("probability", 0)
                    reasoning = data.get("reasoning", "")
                else:
                    prob = data
                    reasoning = ""
                logger.info(
                    f"Turn {turn}: assigned {prob*100:.0f}% to actual action '{outcome_action}'"
                    f"{f' ({reasoning})' if reasoning else ''}"
                )
                break

    def _normalize_action(self, action: str) -> str:
        """Normalize action name for comparison."""
        return action.lower().replace(" ", "").replace("-", "")

    def format_for_prompt(self) -> str:
        """Format memory as context for LLM prompts."""
        lines = ["=== GAME MEMORY ===", ""]

        # Opponent patterns
        p = self.opponent_pattern
        if p.total_turns > 0:
            lines.append(f"OPPONENT PATTERNS ({p.total_turns} turns):")
            lines.append(f"- Switches: {p.switches}/{p.total_turns}")
            if p.switch_on_threat > 0:
                lines.append(f"- Switch on threat: {p.switch_on_threat}")
            if p.setup_moves_used > 0:
                lines.append(f"- Setup moves used: {p.setup_moves_used}")
            if p.predicted_our_switch > 0:
                lines.append(f"- Predicted our switch: {p.predicted_our_switch}")
            lines.append("")

        # Turn history (last 5)
        if self.turn_events:
            lines.append(f"RECENT TURNS (last {len(self.turn_events)}):")
            for event in self.turn_events:
                lines.append(self._format_turn_event(event))
            lines.append("")

        # Strategic notes
        if self.strategic_notes:
            lines.append("STRATEGIC NOTES:")
            for note in self.strategic_notes:
                lines.append(f"- [T{note.turn}] {note.content}")
            lines.append("")

        # Prediction accuracy
        if self.total_predictions > 0:
            accuracy = self.correct_predictions / self.total_predictions * 100
            lines.append(
                f"PREDICTION ACCURACY: {self.correct_predictions}/{self.total_predictions} ({accuracy:.0f}%)"
            )

        return "\n".join(lines)

    def _format_turn_event(self, event: ParsedTurnEvent) -> str:
        """Format single turn event as concise string."""
        parts = [f"T{event.turn}:"]
        parts.append(f"We {event.our_action}")
        parts.append(f"vs {event.opponent_action}")

        if event.damage_dealt:
            parts.append(f"(dealt {event.damage_dealt}%)")
        if event.damage_taken:
            parts.append(f"(took {event.damage_taken}%)")
        if event.our_ko:
            parts.append(f"[KO'd {event.our_ko}]")
        if event.their_ko:
            parts.append(f"[Lost {event.their_ko}]")

        return " ".join(parts)

    def get_summary_stats(self) -> dict:
        """Get summary stats for debugging/logging."""
        return {
            "turns_recorded": len(self.turn_events),
            "total_turns_seen": self.opponent_pattern.total_turns,
            "opponent_switches": self.opponent_pattern.switches,
            "opponent_setups": self.opponent_pattern.setup_moves_used,
            "strategic_notes": len(self.strategic_notes),
            "prediction_accuracy": (
                f"{self.correct_predictions}/{self.total_predictions}"
                if self.total_predictions > 0
                else "N/A"
            ),
        }
