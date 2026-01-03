"""Speed analysis node - calculates speed comparisons and priority moves."""

import logging

from ..state import AgentState

logger = logging.getLogger(__name__)


def calculate_speed_node(state: AgentState) -> dict:
    """
    Calculate speed comparison between active Pokemon.
    Returns only the fields this node modifies to avoid concurrent write issues.
    """
    battle = state.get("battle_object")
    if not battle:
        logger.warning("No battle object in state, skipping speed calc")
        return {"speed_analysis": None}

    try:
        from src.speed import SpeedCalculator, format_speed_analysis
        from src.data import get_randbats_data

        calculator = SpeedCalculator(gen=9, randbats_data=get_randbats_data())

        # Get opponent sets from state (populated by fetch_sets_node)
        opponent_sets = state.get("opponent_sets", {})

        # Calculate speed matchup
        analysis = calculator.calculate_speed_matchup(battle, opponent_sets)

        if analysis:
            # Format for LLM consumption
            speed_text = format_speed_analysis(analysis)

            logger.info(
                f"Speed calc: {analysis.our_speed} vs {analysis.their_speed} - "
                f"{'We outspeed' if analysis.we_outspeed else 'They outspeed'}"
            )

            return {
                "speed_analysis": speed_text,
                "speed_calc_raw": {
                    "our_speed": analysis.our_speed,
                    "their_speed": analysis.their_speed,
                    "we_outspeed": analysis.we_outspeed,
                    "our_priority": [
                        {"move": m.move_id, "priority": m.priority}
                        for m in analysis.our_priority_moves
                    ],
                    "their_priority": [
                        {"move": m.move_id, "priority": m.priority, "estimated": m.is_estimated}
                        for m in analysis.their_priority_moves
                    ],
                },
            }
        else:
            logger.warning("Speed calculation returned no result")
            return {"speed_analysis": None, "speed_calc_raw": None}

    except Exception as e:
        logger.error(f"Speed calculation failed: {e}", exc_info=True)
        return {"speed_analysis": None, "speed_calc_raw": None}
