"""State schema for LangGraph agent."""

from typing import TypedDict, Optional, Literal, Any


class AgentState(TypedDict):
    """State for LangGraph agent - designed for extensibility."""

    # Player context
    username: Optional[str]  # Player username (e.g., TailGlow1, TailGlow2) for Langfuse tracking

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

    # --- Team analysis ---
    team_analysis: Optional[str]  # LLM analysis of our team roles (Turn 1)

    # --- Parallel node outputs ---
    opponent_sets: dict[str, Any]  # Randbats data for opponent Pokemon
    damage_calculations: Optional[str]  # Formatted damage calc results
    damage_calc_raw: Optional[dict[str, Any]]  # Raw damage calc data
    speed_analysis: Optional[str]  # Speed comparison + priority info
    speed_calc_raw: Optional[dict[str, Any]]  # Raw speed calc data
    type_matchups: Optional[str]  # Offensive/defensive matchups
    effects_analysis: Optional[str]  # Relevant item/ability/move effects
    strategy_context: Optional[str]  # RAG retrieval results

    # --- Compiled context ---
    compiled_analysis: Optional[str]  # Synthesized battle analysis
