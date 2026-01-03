"""LangGraph agent for Pokemon battle decisions.

Architecture:
- Team Analysis Graph: Runs on turn 1 only (LLM Call #1)
- Main Battle Graph: Runs every turn with parallel information gathering
  - Sequential: format_state → fetch_sets
  - Parallel: damage, speed, types, effects (fan-out)
  - Sequential: strategy_rag → compile (LLM #2) → decide (LLM #3) → parse
"""

import logging

from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .nodes import (
    format_state_node,
    calculate_damage_node,
    decide_action_node,
    parse_decision_node,
    fetch_opponent_sets_node,
    calculate_speed_node,
    get_type_matchups_node,
    get_effects_node,
    lookup_strategy_node,
    analyze_team_node,
    compile_context_node,
)

logger = logging.getLogger(__name__)


def create_team_analysis_graph() -> StateGraph:
    """Build the team analysis graph (runs on turn 1 only).

    This graph performs LLM Call #1 to analyze our team's roles,
    strengths, and weaknesses.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("analyze_team", analyze_team_node)

    workflow.add_edge(START, "analyze_team")
    workflow.add_edge("analyze_team", END)

    return workflow.compile()


def create_battle_graph() -> StateGraph:
    """Build the main battle decision graph (runs every turn).

    Flow:
    1. format_state - Format battle state for display/context
    2. fetch_opponent_sets - Get randbats data for opponent Pokemon
    3. PARALLEL: damage, speed, types, effects - Information gathering
    4. strategy_rag - Retrieve strategy documents
    5. compile_context - LLM Call #2: Synthesize all info
    6. decide_action - LLM Call #3: Make final decision
    7. parse_decision - Extract action from LLM response
    """
    workflow = StateGraph(AgentState)

    # Add all nodes
    workflow.add_node("format_state", format_state_node)
    workflow.add_node("fetch_opponent_sets", fetch_opponent_sets_node)
    workflow.add_node("calculate_damage", calculate_damage_node)
    workflow.add_node("calculate_speed", calculate_speed_node)
    workflow.add_node("get_type_matchups", get_type_matchups_node)
    workflow.add_node("get_effects", get_effects_node)
    workflow.add_node("lookup_strategy", lookup_strategy_node)
    workflow.add_node("compile_context", compile_context_node)
    workflow.add_node("decide_action", decide_action_node)
    workflow.add_node("parse_decision", parse_decision_node)

    # Sequential start
    workflow.add_edge(START, "format_state")
    workflow.add_edge("format_state", "fetch_opponent_sets")

    # Parallel fan-out from fetch_opponent_sets
    workflow.add_edge("fetch_opponent_sets", "calculate_damage")
    workflow.add_edge("fetch_opponent_sets", "calculate_speed")
    workflow.add_edge("fetch_opponent_sets", "get_type_matchups")
    workflow.add_edge("fetch_opponent_sets", "get_effects")

    # Fan-in to lookup_strategy (waits for all parallel nodes)
    workflow.add_edge("calculate_damage", "lookup_strategy")
    workflow.add_edge("calculate_speed", "lookup_strategy")
    workflow.add_edge("get_type_matchups", "lookup_strategy")
    workflow.add_edge("get_effects", "lookup_strategy")

    # Continue sequential
    workflow.add_edge("lookup_strategy", "compile_context")
    workflow.add_edge("compile_context", "decide_action")
    workflow.add_edge("decide_action", "parse_decision")
    workflow.add_edge("parse_decision", END)

    return workflow.compile()


def create_agent() -> StateGraph:
    """Build the LangGraph state machine.

    Returns the main battle graph for backward compatibility.
    Use create_battle_graph() and create_team_analysis_graph()
    directly for the new multi-graph architecture.
    """
    return create_battle_graph()
