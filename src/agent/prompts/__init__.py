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

__all__ = [
    "TEAM_ANALYSIS_SYSTEM_PROMPT",
    "TEAM_ANALYSIS_USER_PROMPT",
    "build_team_analysis_prompt",
    "DECISION_SYSTEM_PROMPT",
    "DECISION_USER_PROMPT",
    "build_decision_prompt",
]
