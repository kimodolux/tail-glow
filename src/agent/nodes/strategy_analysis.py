"""Strategy analysis node - LLM Call to analyze battle progress (Every turn).

Reviews battle history, general strategy principles, and learned strategies
to provide guidance for the decision.
"""

import logging

from ..state import AgentState
from ..prompts import STRATEGY_ANALYSIS_SYSTEM_PROMPT, build_strategy_analysis_prompt
from src.llm import get_llm_provider
from src.battle import format_battle_log
from src.rag.strategy_loader import get_general_strategy_section

logger = logging.getLogger(__name__)


def analyze_strategy_node(state: AgentState) -> dict:
    """
    Call LLM to analyze current battle strategy.

    This node runs after lookup_strategy and before decide_action.
    It uses the battle log, team analysis, strategy context, and
    general strategy principles to provide guidance for the decision.

    Returns only the fields this node modifies.
    """
    battle = state.get("battle_object")

    # Get inputs
    team_analysis = state.get("team_analysis")
    strategy_context = state.get("strategy_context")
    formatted_state = state.get("formatted_state")
    turn_reasoning = state.get("turn_reasoning", {})

    # Load general strategy document (cached)
    general_strategy = get_general_strategy_section()

    # Build battle log from poke-env observations
    battle_log = format_battle_log(battle, turn_reasoning, n_turns=5)

    # Store the formatted log in state for potential use elsewhere
    state_updates = {
        "battle_log_context": battle_log,
        "general_strategy": general_strategy,
    }

    # Skip analysis on turn 1 (no history yet)
    if battle.turn == 1:
        state_updates["strategy_analysis"] = "Turn 1 - no battle history to analyze yet. Focus on the matchup."
        return state_updates

    # Build strategy analysis prompt with general strategy
    user_prompt = build_strategy_analysis_prompt(
        team_analysis=team_analysis,
        strategy_context=strategy_context,
        battle_log=battle_log,
        formatted_state=formatted_state,
        general_strategy=general_strategy,
    )

    try:
        llm = get_llm_provider()
        username = state.get("username")
        trace_id = state.get("trace_id")
        turn = state.get("turn")
        battle_tag = state.get("battle_tag")

        response = llm.generate(
            STRATEGY_ANALYSIS_SYSTEM_PROMPT,
            user_prompt,
            user=username,
            trace_id=trace_id,
            generation_name="analyze_strategy",
            turn=turn,
            battle_tag=battle_tag,
        )
        state_updates["strategy_analysis"] = response
        logger.debug(f"Strategy analysis: {response}")

    except Exception as e:
        logger.error(f"Strategy analysis LLM error: {e}")
        state_updates["strategy_analysis"] = "Unable to analyze strategy - proceeding with available information."

    return state_updates
