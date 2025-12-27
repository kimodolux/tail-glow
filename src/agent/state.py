"""State schema for LangGraph agent."""

from typing import TypedDict, Optional, Literal, Any


class AgentState(TypedDict):
    """State for LangGraph agent - designed for extensibility."""

    # Battle context
    battle_tag: str  # Unique battle ID
    battle_object: Optional[Any]  # Reference to poke-env Battle
    turn: int  # Current turn number

    # Formatted state for LLM
    formatted_state: str  # Human-readable game state

    # Tool results (extensible dictionary)
    tool_results: dict[str, Any]  # All tool outputs
    # Example: {"damage_calc": {...}, "rag_retrieval": [...]}

    # LLM interaction
    llm_response: str  # Raw LLM output
    reasoning: Optional[str]  # Extracted reasoning for chat

    # Parsed decision
    action_type: Optional[Literal["move", "switch"]]
    action_target: Optional[str]  # Move name or Pokemon slot

    # Error handling
    error: Optional[str]  # Error message if any
