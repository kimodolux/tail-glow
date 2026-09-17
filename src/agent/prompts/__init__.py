"""Prompt templates for battle agent LLM calls."""

from .decision import (
    DECISION_SYSTEM_PROMPT,
    DECISION_USER_PROMPT,
    build_decision_prompt,
)

__all__ = [
    "DECISION_SYSTEM_PROMPT",
    "DECISION_USER_PROMPT",
    "build_decision_prompt",
]
