"""State schema for the LangGraph battle agent."""

from typing import TypedDict, Optional, Literal, Any


class AgentState(TypedDict):
    """State passed through the battle decision graph each turn."""

    # Player context
    username: Optional[str]  # Player username (for tracing)

    # Battle context
    battle_tag: str  # Unique battle ID
    battle_object: Optional[Any]  # Reference to poke-env Battle
    turn: int  # Current turn number

    # Formatted state for LLM
    formatted_state: str  # Human-readable game state

    # LLM interaction
    llm_response: str  # Raw LLM output
    reasoning: Optional[str]  # Extracted reasoning for chat / logging

    # Parsed decision
    action_type: Optional[Literal["move", "switch"]]
    action_target: Optional[str]  # Move name or Pokemon species

    # Error handling
    error: Optional[str]  # Error message if any

    # Tracing
    trace_id: Optional[str]  # Parent trace ID for nesting LLM calls
