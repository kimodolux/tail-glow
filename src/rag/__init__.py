"""RAG (Retrieval Augmented Generation) module for strategy lookup and self-learning."""

from .store import StrategyStore, get_strategy_store, init_strategy_store
from .retriever import StrategyRetriever, format_strategy_context
from .strategy_loader import load_general_strategy, get_general_strategy_section, clear_strategy_cache
from .models import (
    MistakeType,
    MatchupOutcome,
    SetContext,
    MatchupLearning,
    MistakeLearning,
    GameSummary,
)

__all__ = [
    # Store
    "StrategyStore",
    "get_strategy_store",
    "init_strategy_store",
    # Retriever
    "StrategyRetriever",
    "format_strategy_context",
    # Strategy loader
    "load_general_strategy",
    "get_general_strategy_section",
    "clear_strategy_cache",
    # Models
    "MistakeType",
    "MatchupOutcome",
    "SetContext",
    "MatchupLearning",
    "MistakeLearning",
    "GameSummary",
]
