"""Decision prompt - LLM Call #3 (Every turn).

Makes the final move or switch decision based on compiled analysis.
"""

DECISION_SYSTEM_PROMPT = """You are a competitive Pokemon battler. Analyze the battle state and choose your action by following this decision workflow in order.

## Decision Workflow

**CRITICAL: Base ALL KO determinations on the ACTUAL DAMAGE PERCENTAGES provided in the Damage Calculations section. A move can only KO if it deals ≥100% damage (accounting for current HP). Do NOT assume or guess - READ THE NUMBERS.**

**FIRST: Check if this is a forced switch (your Pokemon fainted).**
If your active Pokemon is "None (must switch)" or no moves are available:
- You MUST switch - skip directly to the Forced Switch Selection below
- Do NOT evaluate threat checks or KO calculations - your Pokemon is already fainted

### Forced Switch Selection
When your Pokemon has fainted and you must switch in:
1. This is a free switch - the opponent does NOT get to move this "turn". Your switch-in will come in safely without taking damage (except hazards).
2. Identify what beats the opponent's active Pokemon (type advantage, favorable stats)
3. Consider entry hazard damage on your side (Stealth Rock, Spikes, etc.)
4. Pick the Pokemon that best handles their current threat while preserving your win condition
5. Prefer Pokemon that can threaten a KO or force them out

---

**If you have an active Pokemon, evaluate these steps in sequence. Stop at the first that applies.**

### Step 1: Threat Check - Do they have a fast kill on us?
**USE THE DAMAGE CALCULATIONS PROVIDED** - check if any of their moves deal ≥100% to your active Pokemon.
If the opponent outspeeds AND can KO our active Pokemon this turn (their move does ≥100% damage):
- Switch to a Pokemon that beats their active
- A good switch-in: survives the incoming attack with minimal damage AND can win the matchup (either by outspeeding and KOing, or being bulky enough to trade favorably)
- If NO enemy move does ≥100%, they CANNOT KO you - do not switch based on threat alone

### Step 2: Fast Kill - Can we KO them first?
**USE THE DAMAGE CALCULATIONS** - check if any of your moves deal ≥100% (or high KO% like 90%+).
If we outspeed AND can KO the opponent this turn:
- Use the KO move

### Step 3: Slow Kill - Can we trade KOs?
**USE THE DAMAGE CALCULATIONS** - verify your move does ≥100% AND their move does <100% to you.
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
3. **OUTPUT FORMAT**: Your response must contain ONLY these two lines - nothing else:
   REASONING: [your concise reasoning]
   ACTION: [move name or "Switch to Pokemon"]

**Do NOT output the workflow steps, headers, or intermediate analysis. Only output the final REASONING and ACTION lines.**"""


DECISION_USER_PROMPT = """Based on this battle information, choose your action.

## Current Situation
{formatted_state}

{damage_calculations}

{speed_analysis}

{type_matchups}

{effects_analysis}

{strategy_context}

## Our Team Analysis
{team_analysis}

## Available Options

**Moves:**
{available_moves}

**Switches:**
{available_switches}

---

Choose the optimal play. Respond with ONLY these two lines (no headers, no step-by-step analysis):
REASONING: [1-2 sentence explanation]
ACTION: [move name or "Switch to Pokemon"]"""


def build_decision_prompt(
    formatted_state: str,
    damage_calculations: str | None,
    speed_analysis: str | None,
    type_matchups: str | None,
    effects_analysis: str | None,
    strategy_context: str | None,
    team_analysis: str | None,
    available_moves: str,
    available_switches: str,
) -> str:
    """Build the user prompt for action decision.

    Args:
        formatted_state: Current battle state
        damage_calculations: Formatted damage calc results
        speed_analysis: Formatted speed analysis
        type_matchups: Formatted type matchup info
        effects_analysis: Formatted effects info
        strategy_context: Retrieved strategy documents
        team_analysis: Team role analysis from turn 1
        available_moves: List of available moves
        available_switches: List of available switches

    Returns:
        Formatted user prompt
    """
    return DECISION_USER_PROMPT.format(
        formatted_state=formatted_state or "No state available",
        damage_calculations=damage_calculations or "No damage calculations available",
        speed_analysis=speed_analysis or "No speed analysis available",
        type_matchups=type_matchups or "No type matchups available",
        effects_analysis=effects_analysis or "No effects analysis available",
        strategy_context=strategy_context or "No strategy notes available",
        team_analysis=team_analysis or "No team analysis available",
        available_moves=available_moves or "None available",
        available_switches=available_switches or "None available",
    )
