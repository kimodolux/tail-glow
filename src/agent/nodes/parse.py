"""Parse decision node for battle graph."""

import re
import logging

from ..state import AgentState

logger = logging.getLogger(__name__)


def parse_decision_node(state: AgentState) -> AgentState:
    """
    Parse LLM response into structured action and reasoning.
    Extracts both REASONING and ACTION from response.
    """
    response = state["llm_response"]

    # Extract reasoning
    reasoning_match = re.search(
        r"REASONING:\s*(.+?)(?=\nACTION:|$)",
        response,
        re.IGNORECASE | re.DOTALL
    )
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()
        # Truncate for chat limit (~300 char limit in Showdown)
        state["reasoning"] = reasoning[:280] if len(reasoning) > 280 else reasoning
        logger.info(f"Parsed reasoning: {state['reasoning']}")
    else:
        state["reasoning"] = None
        logger.debug("No reasoning found in response")

    # Look for "ACTION: [move/switch]"
    match = re.search(r"ACTION:\s*(.+?)(?:\n|$)", response, re.IGNORECASE)

    if match:
        action_text = match.group(1).strip()
        logger.info(f"Parsed action: {action_text}")

        if "switch" in action_text.lower():
            state["action_type"] = "switch"
            # Extract Pokemon name after "switch to"
            pokemon_match = re.search(r"switch to\s+(.+)", action_text, re.IGNORECASE)
            if pokemon_match:
                state["action_target"] = pokemon_match.group(1).strip().lower()
            else:
                # Try to get anything after "switch"
                pokemon_match = re.search(r"switch\s+(.+)", action_text, re.IGNORECASE)
                state["action_target"] = (
                    pokemon_match.group(1).strip().lower() if pokemon_match else None
                )
        else:
            state["action_type"] = "move"
            # Clean up move name: remove extra text, normalize
            move_name = action_text.lower()
            # Remove common extra text
            move_name = re.sub(r"\s*\(.*\)", "", move_name)  # Remove parenthetical text
            move_name = re.sub(r"\s*-.*$", "", move_name)  # Remove text after dash
            move_name = move_name.strip()
            state["action_target"] = move_name
    else:
        logger.warning(f"Could not parse LLM response: {response}")
        state["error"] = "Could not parse response"
        state["action_type"] = "move"
        state["action_target"] = None  # Will trigger fallback in client

    return state
