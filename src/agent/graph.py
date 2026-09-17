"""LangGraph agent for Pokemon battle decisions.

Flow (every turn):
    decide_action [LLM] -> parse_decision
"""

import logging

from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .nodes import (
    decide_action_node,
    parse_decision_node,
)

logger = logging.getLogger(__name__)


def create_battle_graph() -> StateGraph:
    """Build the battle decision graph (runs every turn).

    Flow:
    1. decide_action - Make the move/switch decision [LLM]
    2. parse_decision - Extract structured action from the LLM response
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("decide_action", decide_action_node)
    workflow.add_node("parse_decision", parse_decision_node)

    workflow.add_edge(START, "decide_action")
    workflow.add_edge("decide_action", "parse_decision")
    workflow.add_edge("parse_decision", END)

    return workflow.compile()


def create_agent() -> StateGraph:
    """Build the battle decision graph."""
    return create_battle_graph()
