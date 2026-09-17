"""Decision prompt - the per-turn decision LLM call.

The LLM decides from the formatted battle state and the list of available
moves and switches.
"""


DECISION_SYSTEM_PROMPT = """You are a competitive Pokemon battler playing a single battle on Pokemon Showdown.

Each turn you are given the current battle state and your available moves and switches. Briefly predict what the opponent is likely to do, then choose the action that best handles that.

If your active Pokemon has fainted you must switch: pick the best counter to the opponent's active Pokemon.

## Output

Respond with ONLY these two lines (no headers, no step-by-step analysis):
REASONING: [1-2 sentences — your opponent read and chosen action]
ACTION: [move name or "Switch to Pokemon"]"""


DECISION_USER_PROMPT = """Based on this battle information, choose your action.

## Current Situation
{formatted_state}

## Available Options

**Moves:**
{available_moves}

**Switches:**
{available_switches}

---

Respond with ONLY these two lines (no headers, no step-by-step analysis):
REASONING: [1-2 sentences — your opponent read and chosen action]
ACTION: [move name or "Switch to Pokemon"]"""


def build_decision_prompt(
    formatted_state: str,
    available_moves: str,
    available_switches: str,
) -> str:
    """Build the user prompt for the action decision."""
    return DECISION_USER_PROMPT.format(
        formatted_state=formatted_state or "No state available",
        available_moves=available_moves or "None available",
        available_switches=available_switches or "None available",
    )
