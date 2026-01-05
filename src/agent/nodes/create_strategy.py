"""Create battle strategy node - LLM Call (Turn 1 only).

Creates an initial game plan based on team analysis.
Runs after analyze_team_node.
"""

import logging
from typing import Any

from src.agent.state import AgentState
from src.agent.prompts.create_strategy import (
    CREATE_STRATEGY_SYSTEM_PROMPT,
    build_create_strategy_prompt,
)
from src.llm import get_llm_provider

logger = logging.getLogger(__name__)


def create_strategy_node(state: AgentState) -> dict[str, Any]:
    """Create initial battle strategy based on team analysis.

    Called only on turn 1, after analyze_team_node.
    Creates a strategic game plan that will be updated by battle_memory.

    Args:
        state: Current agent state with team_analysis

    Returns:
        Dict with battle_strategy
    """
    team_analysis = state.get("team_analysis")

    if not team_analysis:
        logger.warning("No team analysis available, skipping strategy creation")
        return {"battle_strategy": None}

    try:
        llm = get_llm_provider()
        user_prompt = build_create_strategy_prompt(team_analysis)
        username = state.get("username")

        response = llm.generate(
            CREATE_STRATEGY_SYSTEM_PROMPT,
            user_prompt,
            user=username,
        )

        battle_strategy = response.strip()
        logger.info("Battle strategy created successfully")

        return {"battle_strategy": battle_strategy}

    except Exception as e:
        logger.error(f"Strategy creation failed: {e}", exc_info=True)
        return {"battle_strategy": None}
