"""Decision prompt - LLM Call #3 (Every turn).

Makes the final move or switch decision based on compiled analysis.
"""

DECISION_SYSTEM_PROMPT = """You are a competitive Pokemon battler. Analyze the battle state and choose your action by following this decision workflow in order.

## Decision Workflow

Evaluate each step in sequence. Stop at the first step that applies.

### Step 1: Threat Check - Do they have a fast kill on us?
If the opponent outspeeds AND can KO our active Pokemon this turn:
- Switch to a Pokemon that beats their active
- A good switch-in: survives the incoming attack with minimal damage AND can win the matchup (either by outspeeding and KOing, or being bulky enough to trade favorably)

### Step 2: Fast Kill - Can we KO them first?
If we outspeed AND can KO the opponent this turn:
- Use the KO move

### Step 3: Slow Kill - Can we trade KOs?
If they outspeed but we survive their attack AND can KO them in return:
- Use the KO move (acceptable trade)

### Step 4: Matchup Calculation - Who wins the extended fight?
When neither side has an immediate KO, calculate the matchup:
- Count how many turns each side needs to KO the other
- If we win (e.g., we need 2 hits, they need 3): stay in and use the most damaging move
- If we lose the matchup: switch to something that wins
- Factor in switch-in damage when evaluating switches
- Avoid endless switching - only switch when it meaningfully improves your position

## Rules
1. Choose from the available moves or switches listed
2. Provide concise reasoning (< 280 characters)
3. Output format must be exactly:
   REASONING: [your reasoning]
   ACTION: [move name or "Switch to Pokemon"]"""


DECISION_USER_PROMPT = """Based on this analysis, choose your action.

## Battle Analysis
{compiled_analysis}

## Available Options

**Moves:**
{available_moves}

**Switches:**
{available_switches}

---

Choose the optimal play. Format your response as:
REASONING: [1-2 sentence explanation]
ACTION: [move name or "Switch to Pokemon"]"""


def build_decision_prompt(
    compiled_analysis: str,
    available_moves: str,
    available_switches: str,
) -> str:
    """Build the user prompt for action decision.

    Args:
        compiled_analysis: Synthesized battle analysis from compile step
        available_moves: List of available moves
        available_switches: List of available switches

    Returns:
        Formatted user prompt
    """
    return DECISION_USER_PROMPT.format(
        compiled_analysis=compiled_analysis,
        available_moves=available_moves or "None available",
        available_switches=available_switches or "None available",
    )
