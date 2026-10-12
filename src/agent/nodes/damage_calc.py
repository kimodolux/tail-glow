"""Damage calc node - deterministic damage estimates for the current turn.

Runs between ``format_state`` and ``decide_action``. Uses poke-env's gen9
damage calculator to work out how much damage our moves do to the opponent and
how much the opponent's revealed moves do to us (and our switches), so the
decision LLM reasons over concrete numbers rather than guessing.
"""

import logging

from ..state import AgentState
from ..damage import compute_damage_report

logger = logging.getLogger(__name__)


def damage_calc_node(state: AgentState) -> AgentState:
    """Attach a deterministic damage report to the state."""
    battle = state.get("battle_object")
    if not battle:
        state["damage_report"] = None
        return state

    try:
        state["damage_report"] = compute_damage_report(
            battle, state.get("opponent_belief")
        )
    except Exception as e:
        logger.error(f"Damage calc node error: {e}")
        state["damage_report"] = None

    return state
