"""Decision prompt - the per-turn decision LLM call.

The LLM decides from the formatted battle state and the list of available
moves and switches. The response is returned as structured data (see the
``Decision`` schema in the decide node), so the prompt only guides content,
not output format.
"""


DECISION_SYSTEM_PROMPT = """You are a competitive Pokemon battler playing a single battle on Pokemon Showdown.

Each turn you are given the current battle state and your available moves and switches. Briefly predict what the opponent is likely to do, then choose the action that best handles that.

Choose exactly one action:
- To attack, set action_type to "move" and action_target to the move name.
- To switch, set action_type to "switch" and action_target to the species to switch in.

If your active Pokemon has fainted you must switch: pick the best counter to the opponent's active Pokemon.

Use only a move or switch that appears in the available options for this turn."""


DECISION_USER_PROMPT = """Based on this battle information, choose your action.

{formatted_state}"""


def build_decision_prompt(formatted_state: str) -> str:
    """Build the user prompt for the action decision."""
    return DECISION_USER_PROMPT.format(
        formatted_state=formatted_state or "No state available",
    )
