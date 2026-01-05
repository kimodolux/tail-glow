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

    # --- Battle strategy (Turn 1) ---
    battle_strategy: Optional[str]  # Initial game plan from create_battle_strategy

    # --- Matchup calculator (background) ---
    matchup_results: Optional[dict[tuple[str, str], dict[str, Any]]]  # Pokemon pair outcomes

    # --- Expected opponent action ---
    expected_opponent_action: Optional[dict[str, Any]]  # Predicted move/switch with probabilities

    # --- Best options analysis ---
    best_moves: Optional[dict[str, Any]]  # Ranked move options with reasoning
    best_switches: Optional[dict[str, Any]]  # Ranked switch options with reasoning

    # --- Tera analysis ---
    tera_analysis: Optional[dict[str, Any]]  # Tera tracking and recommendations

    # --- Battle memory ---
    battle_log: Optional[str]  # Turn-by-turn history
    battle_analysis: Optional[str]  # Strategic analysis updated each turn
    revealed_sets: Optional[dict[str, dict[str, Any]]]  # Tracked opponent information
