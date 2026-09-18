"""LangGraph agent for Pokemon battle decisions.

Flow (every turn):
    format_state -> decide_action [LLM]
"""

import logging

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from .state import AgentState
from .nodes import (
    format_state_node,
    decide_action_node,
)

logger = logging.getLogger(__name__)


def create_battle_graph() -> CompiledStateGraph:
    """Build the battle decision graph (runs every turn).

    Flow:
    1. format_state  - Turn the battle object into LLM-readable text
    2. decide_action - Make the structured move/switch decision [LLM]
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("format_state", format_state_node)
    workflow.add_node("decide_action", decide_action_node)

    workflow.add_edge(START, "format_state")
    workflow.add_edge("format_state", "decide_action")
    workflow.add_edge("decide_action", END)

    return workflow.compile()


def create_agent() -> CompiledStateGraph:
    """Build the battle decision graph."""
    return create_battle_graph()
