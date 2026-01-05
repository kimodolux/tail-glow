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

# New prompts from graph refactor
from .create_strategy import (
    CREATE_STRATEGY_SYSTEM_PROMPT,
    CREATE_STRATEGY_USER_PROMPT,
    build_create_strategy_prompt,
)
from .expected_move import (
    EXPECTED_MOVE_SYSTEM_PROMPT,
    EXPECTED_MOVE_USER_PROMPT,
    build_expected_move_prompt,
)
from .battle_memory import (
    BATTLE_MEMORY_SYSTEM_PROMPT,
    BATTLE_MEMORY_USER_PROMPT,
    build_battle_memory_prompt,
)

__all__ = [
    # Original prompts
    "TEAM_ANALYSIS_SYSTEM_PROMPT",
    "TEAM_ANALYSIS_USER_PROMPT",
    "build_team_analysis_prompt",
    "DECISION_SYSTEM_PROMPT",
    "DECISION_USER_PROMPT",
    "build_decision_prompt",
    # New prompts
    "CREATE_STRATEGY_SYSTEM_PROMPT",
    "CREATE_STRATEGY_USER_PROMPT",
    "build_create_strategy_prompt",
    "EXPECTED_MOVE_SYSTEM_PROMPT",
    "EXPECTED_MOVE_USER_PROMPT",
    "build_expected_move_prompt",
    "BATTLE_MEMORY_SYSTEM_PROMPT",
    "BATTLE_MEMORY_USER_PROMPT",
    "build_battle_memory_prompt",
]
