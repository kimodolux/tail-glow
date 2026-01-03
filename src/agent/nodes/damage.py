"""Damage calculation node for battle graph."""

import logging

from ..state import AgentState
from src.config import Config

logger = logging.getLogger(__name__)


def calculate_damage_node(state: AgentState) -> dict:
    """
    Calculate damage for all relevant matchups.
    Returns only the fields this node modifies to avoid concurrent write issues.
    """
    if not Config.ENABLE_DAMAGE_CALC:
        return {}

    battle = state.get("battle_object")
    if not battle:
        logger.warning("No battle object in state, skipping damage calc")
        return {}

    try:
        from src.damage_calc import DamageCalculator, format_damage_calculations
        from src.data import get_randbats_data

        calculator = DamageCalculator(gen=9, randbats_data=get_randbats_data())

        # Calculate all matchups
        our_vs_active = calculator.calculate_our_moves_vs_active(battle)
        our_vs_bench = calculator.calculate_our_moves_vs_bench(battle)
        their_vs_us = calculator.calculate_their_moves_vs_us(battle)
        their_vs_bench = calculator.calculate_their_moves_vs_bench(battle)

        logger.info(f"Damage calc - our_vs_active: {our_vs_active}")
        logger.info(f"Damage calc - our_vs_bench: {our_vs_bench}")
        logger.info(f"Damage calc - their_vs_us: {their_vs_us}")
        logger.info(f"Damage calc - their_vs_bench: {their_vs_bench}")

        # Format damage calculations
        damage_text = format_damage_calculations(
            our_vs_active, our_vs_bench, their_vs_us, their_vs_bench
        )

        if damage_text.strip():
            logger.info("Damage calculations added to state")
            return {
                "damage_calculations": damage_text,
                "damage_calc_raw": {
                    "our_vs_active": our_vs_active,
                    "our_vs_bench": our_vs_bench,
                    "their_vs_us": their_vs_us,
                    "their_vs_bench": their_vs_bench,
                },
            }
        else:
            logger.warning("Damage calculations produced empty output")
            return {"damage_calculations": None, "damage_calc_raw": None}

    except Exception as e:
        logger.error(f"Damage calculation failed: {e}", exc_info=True)
        return {"damage_calculations": None, "damage_calc_raw": None}
