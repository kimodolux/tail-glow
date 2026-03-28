"""Prompt templates for battle agent LLM calls.
New prompts will be added as separate modules in this package.
"""

from .team_analysis import (
    TEAM_ANALYSIS_SYSTEM_PROMPT,
    TEAM_ANALYSIS_USER_PROMPT,
    build_team_analysis_prompt,
)
from .decision import (
    DECISION_SYSTEM_PROMPT,
    DECISION_USER_PROMPT,
    build_decision_prompt,
)
from .strategy_analysis import (
    STRATEGY_ANALYSIS_SYSTEM_PROMPT,
    STRATEGY_ANALYSIS_USER_PROMPT,
    build_strategy_analysis_prompt,
)
from .turn_analysis import (
    TURN_ANALYSIS_SYSTEM_PROMPT,
    TURN_ANALYSIS_USER_PROMPT,
    build_turn_analysis_prompt,
    parse_mistake_response,
)
from .game_analysis import (
    GAME_ANALYSIS_SYSTEM_PROMPT,
    GAME_ANALYSIS_USER_PROMPT,
    build_game_analysis_prompt,
    parse_game_analysis_response,
)

__all__ = [
    # Team analysis
    "TEAM_ANALYSIS_SYSTEM_PROMPT",
    "TEAM_ANALYSIS_USER_PROMPT",
    "build_team_analysis_prompt",
    # Decision
    "DECISION_SYSTEM_PROMPT",
    "DECISION_USER_PROMPT",
    "build_decision_prompt",
    # Strategy analysis
    "STRATEGY_ANALYSIS_SYSTEM_PROMPT",
    "STRATEGY_ANALYSIS_USER_PROMPT",
    "build_strategy_analysis_prompt",
    # Turn analysis (self-learning)
    "TURN_ANALYSIS_SYSTEM_PROMPT",
    "TURN_ANALYSIS_USER_PROMPT",
    "build_turn_analysis_prompt",
    "parse_mistake_response",
    # Game analysis (self-learning)
    "GAME_ANALYSIS_SYSTEM_PROMPT",
    "GAME_ANALYSIS_USER_PROMPT",
    "build_game_analysis_prompt",
    "parse_game_analysis_response",
]
