"""LangGraph agent for Pokemon battle decisions."""

import re
import logging

from langgraph.graph import StateGraph, END

from .state import AgentState
from .prompts import SYSTEM_PROMPT, build_user_prompt
from src.llm import get_llm_provider
from src.config import Config

logger = logging.getLogger(__name__)


def format_state_node(state: AgentState) -> AgentState:
    """
    Pass-through node for future extensibility.
    In MVP, formatting happens before graph invocation.
    Could be used to add tool results to formatted state.
    """
    return state


def calculate_damage_node(state: AgentState) -> AgentState:
    """
    Calculate damage for all relevant matchups.
    Adds damage calculations to formatted_state for LLM consumption.
    """
    if not Config.ENABLE_DAMAGE_CALC:
        return state

    battle = state.get("battle_object")
    if not battle:
        logger.warning("No battle object in state, skipping damage calc")
        return state

    try:
        from src.damage_calc import DamageCalculator, format_damage_calculations

        calculator = DamageCalculator(gen=9)

        # Calculate all matchups
        our_vs_active = calculator.calculate_our_moves_vs_active(battle)
        our_vs_bench = calculator.calculate_our_moves_vs_bench(battle)
        their_vs_us = calculator.calculate_their_moves_vs_us(battle)
        their_vs_bench = calculator.calculate_their_moves_vs_bench(battle)

        logger.info(
            f"Damage calc results - our_vs_active: {our_vs_active is not None}, "
            f"their_vs_us: {their_vs_us is not None}"
        )

        # Store raw results in tool_results
        state["tool_results"]["damage_calc"] = {
            "our_vs_active": our_vs_active,
            "our_vs_bench": our_vs_bench,
            "their_vs_us": their_vs_us,
            "their_vs_bench": their_vs_bench,
        }

        # Format and append to formatted_state
        damage_text = format_damage_calculations(
            our_vs_active, our_vs_bench, their_vs_us, their_vs_bench
        )

        if damage_text.strip():
            state["formatted_state"] = state["formatted_state"] + "\n\n" + damage_text
            logger.info("Damage calculations added to state")
        else:
            logger.warning("Damage calculations produced empty output")

    except Exception as e:
        logger.error(f"Damage calculation failed: {e}", exc_info=True)
        state["tool_results"]["damage_calc_error"] = str(e)

    return state


def decide_action_node(state: AgentState) -> AgentState:
    """
    Call LLM to decide action.
    Handles errors gracefully with fallback.
    """
    llm = get_llm_provider()
    user_prompt = build_user_prompt(state["formatted_state"])

    try:
        response = llm.generate(SYSTEM_PROMPT, user_prompt)
        state["llm_response"] = response
        logger.debug(f"LLM response: {response}")
    except Exception as e:
        logger.error(f"LLM error: {e}")
        state["error"] = f"LLM error: {e}"
        state["llm_response"] = "ACTION: Struggle"  # Fallback

    return state


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


def create_agent() -> StateGraph:
    """Build the LangGraph state machine."""

    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("format_state", format_state_node)
    workflow.add_node("calculate_damage", calculate_damage_node)
    workflow.add_node("decide_action", decide_action_node)
    workflow.add_node("parse_decision", parse_decision_node)

    # Define edges (sequential flow)
    # format_state -> calculate_damage -> decide_action -> parse_decision -> END
    workflow.set_entry_point("format_state")
    workflow.add_edge("format_state", "calculate_damage")
    workflow.add_edge("calculate_damage", "decide_action")
    workflow.add_edge("decide_action", "parse_decision")
    workflow.add_edge("parse_decision", END)

    return workflow.compile()
