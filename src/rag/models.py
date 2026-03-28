"""Data models for the self-learning RAG system.

These models define the structure for storing and retrieving:
- Matchup learnings (Pokemon vs Pokemon outcomes)
- Mistake learnings (errors to avoid in future games)
- Game summaries (complete battle analysis)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class MistakeType(str, Enum):
    """Types of mistakes the agent can detect and learn from."""

    POKEMON_KOD = "pokemon_kod"  # Our Pokemon was KO'd when it could have been saved
    KOD_ON_SWITCH = "kod_on_switch"  # Pokemon was KO'd as it switched in
    SETUP_SNOWBALL = "setup_snowball"  # Let opponent setup too many boosts
    NO_ANSWER_ENDGAME = "no_answer_endgame"  # Endgame with no counter to a threat
    MISSED_KO = "missed_ko"  # Had KO opportunity but didn't take it
    BAD_PREDICTION = "bad_prediction"  # Made wrong prediction (switched into counter, etc.)


class MatchupOutcome(str, Enum):
    """Possible outcomes of a Pokemon matchup."""

    WINS = "wins"  # Our Pokemon wins the matchup
    LOSES = "loses"  # Our Pokemon loses the matchup
    TRADES = "trades"  # Both Pokemon faint or take significant damage
    DEPENDS = "depends"  # Outcome depends on specific conditions


@dataclass
class SetContext:
    """Context about a Pokemon's set/role in a specific battle.

    This captures the role and known moves/items to distinguish between
    different sets of the same Pokemon (e.g., Physical vs Special Dragapult).
    """

    format: str  # e.g., "gen9randombattle", "gen9ou"
    role: str  # e.g., "special_attacker", "physical_sweeper", "wall"
    key_moves: list[str] = field(default_factory=list)  # Moves we saw/used
    item: Optional[str] = None  # Item if known
    ability: Optional[str] = None  # Ability if known
    tera_type: Optional[str] = None  # Tera type if used/revealed


@dataclass
class MatchupLearning:
    """A learned matchup outcome between two Pokemon.

    Stores context-rich information about how a matchup played out,
    including roles, conditions, and the key lesson learned.
    """

    # Our Pokemon
    pokemon: str  # Species name (lowercase)
    our_role: str  # Role we were filling
    our_set_context: SetContext  # Full set context

    # Opponent Pokemon
    opponent: str  # Species name (lowercase)
    opponent_role: str  # Their apparent role

    # Outcome
    outcome: MatchupOutcome  # How the matchup resolved

    # Fields with defaults (must come after non-default fields)
    opponent_set_hints: list[str] = field(default_factory=list)  # Moves we saw them use
    conditions: str = ""  # Conditions that affected outcome (e.g., "after +1 speed")
    lesson: str = ""  # Human-readable takeaway

    # Metadata
    battle_id: str = ""
    turn: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_document(self) -> str:
        """Convert to a text document for vector storage."""
        moves_str = ", ".join(self.our_set_context.key_moves) if self.our_set_context.key_moves else "unknown moves"
        opp_moves_str = ", ".join(self.opponent_set_hints) if self.opponent_set_hints else "unknown moves"

        return (
            f"{self.pokemon} ({self.our_role}) {self.outcome.value} vs {self.opponent} ({self.opponent_role}). "
            f"Our moves: {moves_str}. Their moves: {opp_moves_str}. "
            f"Conditions: {self.conditions}. "
            f"Lesson: {self.lesson}"
        )

    def to_metadata(self) -> dict:
        """Convert to metadata dict for ChromaDB storage."""
        return {
            "type": "matchup",
            "pokemon": self.pokemon,
            "opponent": self.opponent,
            "outcome": self.outcome.value,
            "format": self.our_set_context.format,
            "our_role": self.our_role,
            "opponent_role": self.opponent_role,
            "battle_id": self.battle_id,
            "turn": self.turn,
        }


@dataclass
class MistakeLearning:
    """A learned mistake to avoid in future games.

    Captures what went wrong, why, and what the better play would have been.
    """

    # Classification
    mistake_type: MistakeType

    # Context - who was involved
    our_pokemon: str  # Our Pokemon involved
    our_role: str  # What role it was filling
    opponent: str  # Opponent Pokemon involved
    opponent_role: str  # Their apparent role

    # What happened
    context: str  # Situation description (e.g., "Turn 5, opponent at +2 attack")
    what_happened: str  # Actual events (e.g., "Stayed in and got KO'd by boosted attack")
    better_play: str  # What we should have done (e.g., "Switch to resist or priority user")

    # Metadata
    battle_id: str = ""
    turn: int = 0
    format: str = "gen9randombattle"
    created_at: datetime = field(default_factory=datetime.now)

    def to_document(self) -> str:
        """Convert to a text document for vector storage."""
        return (
            f"Mistake ({self.mistake_type.value}): {self.context}. "
            f"Our {self.our_pokemon} ({self.our_role}) vs their {self.opponent} ({self.opponent_role}). "
            f"What happened: {self.what_happened}. "
            f"Better play: {self.better_play}"
        )

    def to_metadata(self) -> dict:
        """Convert to metadata dict for ChromaDB storage."""
        return {
            "type": "mistake",
            "mistake_type": self.mistake_type.value,
            "pokemon": self.our_pokemon,
            "opponent": self.opponent,
            "our_role": self.our_role,
            "opponent_role": self.opponent_role,
            "format": self.format,
            "battle_id": self.battle_id,
            "turn": self.turn,
        }


@dataclass
class GameSummary:
    """Summary of a completed game for learning extraction.

    Aggregates all learnings from a single battle.
    """

    battle_id: str
    won: bool
    format: str

    # Extracted learnings
    matchups_learned: list[MatchupLearning] = field(default_factory=list)
    mistakes_made: list[MistakeLearning] = field(default_factory=list)

    # Analysis
    turning_points: list[str] = field(default_factory=list)  # Key moments that decided the game
    win_condition_achieved: Optional[str] = None  # How we won (if we won)
    loss_reason: Optional[str] = None  # Why we lost (if we lost)
    key_lesson: str = ""  # Main takeaway from this game

    created_at: datetime = field(default_factory=datetime.now)
