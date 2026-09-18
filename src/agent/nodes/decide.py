"""Decision node - the per-turn decision LLM call.

Consumes the formatted battle state (which already includes the available
moves and switches) and produces a structured decision. Opponent prediction
is reasoned about inline in the `reasoning` field.
"""

import logging
from typing import Literal

from pydantic import BaseModel, Field

from ..state import AgentState
from ..prompts import DECISION_SYSTEM_PROMPT, build_decision_prompt
from src.llm import get_llm_provider

logger = logging.getLogger(__name__)


class Decision(BaseModel):
    """The structured action the LLM commits to for this turn."""

    reasoning: str = Field(
        description="1-2 sentences: the opponent read and why this action was chosen."
    )
    action_type: Literal["move", "switch"] = Field(
        description="Whether to use a move or switch to another Pokemon."
    )
    action_target: str = Field(
        description="The move name (if action_type is 'move') or the species to "
        "switch to (if action_type is 'switch')."
    )


def decide_action_node(state: AgentState) -> AgentState:
    """Call the LLM to decide a structured action from the current battle state."""
    battle = state.get("battle_object")
    user_prompt = build_decision_prompt(state.get("formatted_state", "Unknown battle state"))

    try:
        llm = get_llm_provider()
        decision = llm.generate_structured(
            DECISION_SYSTEM_PROMPT,
            user_prompt,
            Decision,
            user=state.get("username"),
            trace_id=state.get("trace_id"),
            generation_name="decide_action",
            turn=state.get("turn"),
            battle_tag=state.get("battle_tag"),
        )
        state["reasoning"] = decision.reasoning
        state["action_type"] = decision.action_type
        state["action_target"] = decision.action_target
        logger.debug(f"Decision: {decision!r}")
    except Exception as e:
        logger.error(f"Decision LLM error: {e}")
        state["error"] = f"Decision error: {e}"
        _apply_fallback(state, battle)

    return state


def _apply_fallback(state: AgentState, battle) -> None:
    """Pick a sane default action directly when the LLM decision fails."""
    state["reasoning"] = "LLM error fallback."
    if battle and battle.available_moves:
        state["action_type"] = "move"
        state["action_target"] = battle.available_moves[0].id
    elif battle and battle.available_switches:
        state["action_type"] = "switch"
        state["action_target"] = battle.available_switches[0].species
    else:
        state["action_type"] = "move"
        state["action_target"] = None
