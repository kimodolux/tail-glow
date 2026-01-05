"""LangGraph agent for Pokemon battle decisions.

Architecture:
- Team Analysis Graph: Runs on turn 1 only
  - analyze_team (LLM #1) → create_battle_strategy (LLM #2)
- Main Battle Graph: Runs every turn with parallel information gathering
  - Sequential: format_state → fetch_sets → expected_move (LLM #3)
  - Parallel: damage, speed, types, effects, matchup_calc, best_moves, best_switches, tera
  - Sequential: decide (LLM #4) → parse → battle_memory (LLM #5)
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
)
from .nodes.create_strategy import create_strategy_node
from .nodes.expected_move import expected_move_node
from .nodes.best_moves import best_moves_node
from .nodes.best_switches import best_switches_node
from .nodes.tera import tera_node
from .nodes.battle_memory import battle_memory_node
from .nodes.matchup_calculator import calculate_matchup_node

logger = logging.getLogger(__name__)


def create_team_analysis_graph() -> StateGraph:
    """Build the team analysis graph (runs on turn 1 only).

    This graph performs:
    - LLM Call #1: Analyze team roles, strengths, weaknesses
    - LLM Call #2: Create initial battle strategy
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("analyze_team", analyze_team_node)
    workflow.add_node("create_strategy", create_strategy_node)

    workflow.add_edge(START, "analyze_team")
    workflow.add_edge("analyze_team", "create_strategy")
    workflow.add_edge("create_strategy", END)

    return workflow.compile()


def create_battle_graph() -> StateGraph:
    """Build the main battle decision graph (runs every turn).

    Flow:
    1. format_state - Format battle state for display/context
    2. fetch_opponent_sets - Get randbats data for opponent Pokemon
    3. PARALLEL Phase 1: damage, speed, types, effects, matchup_calc
    4. expected_move - LLM predicts opponent's action
    5. PARALLEL Phase 2: best_moves, best_switches, tera (uses expected_move)
    6. decide_action - LLM makes final decision
    7. parse_decision - Extract action from LLM response
    8. battle_memory - Update battle history and analysis
    """
    workflow = StateGraph(AgentState)

    # Add all nodes
    workflow.add_node("format_state", format_state_node)
    workflow.add_node("fetch_opponent_sets", fetch_opponent_sets_node)

    # Data gathering nodes (parallel phase 1)
    workflow.add_node("calculate_damage", calculate_damage_node)
    workflow.add_node("calculate_speed", calculate_speed_node)
    workflow.add_node("get_type_matchups", get_type_matchups_node)
    workflow.add_node("get_effects", get_effects_node)
    workflow.add_node("calculate_matchup", calculate_matchup_node)
    workflow.add_node("lookup_strategy", lookup_strategy_node)

    # Expected opponent move (needs damage/speed data)
    workflow.add_node("expected_move", expected_move_node)

    # Analysis nodes (parallel phase 2 - need expected_move)
    workflow.add_node("best_moves", best_moves_node)
    workflow.add_node("best_switches", best_switches_node)
    workflow.add_node("tera", tera_node)

    # Decision and memory
    workflow.add_node("decide_action", decide_action_node)
    workflow.add_node("parse_decision", parse_decision_node)
    workflow.add_node("battle_memory", battle_memory_node)

    # Sequential start
    workflow.add_edge(START, "format_state")
    workflow.add_edge("format_state", "fetch_opponent_sets")

    # Parallel fan-out phase 1: Data gathering
    workflow.add_edge("fetch_opponent_sets", "calculate_damage")
    workflow.add_edge("fetch_opponent_sets", "calculate_speed")
    workflow.add_edge("fetch_opponent_sets", "get_type_matchups")
    workflow.add_edge("fetch_opponent_sets", "get_effects")
    workflow.add_edge("fetch_opponent_sets", "calculate_matchup")
    workflow.add_edge("fetch_opponent_sets", "lookup_strategy")

    # Fan-in to expected_move (waits for damage and speed)
    workflow.add_edge("calculate_damage", "expected_move")
    workflow.add_edge("calculate_speed", "expected_move")
    workflow.add_edge("get_type_matchups", "expected_move")
    workflow.add_edge("get_effects", "expected_move")
    workflow.add_edge("calculate_matchup", "expected_move")
    workflow.add_edge("lookup_strategy", "expected_move")

    # Parallel fan-out phase 2: Analysis (needs expected_move)
    workflow.add_edge("expected_move", "best_moves")
    workflow.add_edge("expected_move", "best_switches")
    workflow.add_edge("expected_move", "tera")

    # Fan-in to decide_action
    workflow.add_edge("best_moves", "decide_action")
    workflow.add_edge("best_switches", "decide_action")
    workflow.add_edge("tera", "decide_action")

    # Sequential end
    workflow.add_edge("decide_action", "parse_decision")
    workflow.add_edge("parse_decision", "battle_memory")
    workflow.add_edge("battle_memory", END)

    return workflow.compile()


def create_agent() -> StateGraph:
    """Build the LangGraph state machine.

    Returns the main battle graph for backward compatibility.
    Use create_battle_graph() and create_team_analysis_graph()
    directly for the new multi-graph architecture.
    """
    return create_battle_graph()
