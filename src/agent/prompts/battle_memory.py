"""Battle memory prompt - LLM analysis of battle progress.

Updates strategic analysis based on battle history each turn.
"""

BATTLE_MEMORY_SYSTEM_PROMPT = """You are analyzing a Pokemon battle in progress. Your job is to update the strategic analysis based on what has happened.

Consider:
1. What has been revealed about the opponent's team (moves, items, abilities)
2. Which Pokemon have fainted on each side
3. How the battle is progressing (who has momentum)
4. Whether the original strategy needs adjustment
5. Any patterns in opponent behavior

Be concise and actionable. Focus on information that will help the next decision."""


BATTLE_MEMORY_USER_PROMPT = """Update the battle analysis based on this turn's events.

## Original Strategy
{battle_strategy}

## Previous Analysis
{previous_analysis}

## Battle Log
{battle_log}

## Current Turn Events
{turn_events}

## Revealed Information
Our fainted: {our_fainted}
Their fainted: {their_fainted}

Opponent's revealed sets:
{revealed_sets}

## Current Game State
{current_state}

Provide an updated analysis:

1. **Turn Summary**: What happened this turn (1 sentence)

2. **Key Observations**: What did we learn? (items revealed, move patterns, etc.)

3. **Momentum Assessment**: Who has the advantage right now?

4. **Strategy Adjustments**: Should we adjust our approach based on what we've learned?

5. **Immediate Priorities**: What's the most important thing to do next turn?

Output format:
## Turn {turn_number} Analysis

**Summary:** [What happened]

**Observations:**
- [Key observation 1]
- [Key observation 2]

**Momentum:** [Who has advantage and why]

**Strategy Notes:** [Any adjustments needed]

**Priority:** [Most important action next turn]"""


def build_battle_memory_prompt(
    battle_strategy: str,
    previous_analysis: str,
    battle_log: str,
    turn_events: str,
    our_fainted: str,
    their_fainted: str,
    revealed_sets: str,
    current_state: str,
    turn_number: int,
) -> str:
    """Build the user prompt for battle memory analysis.

    Args:
        battle_strategy: Original strategy from turn 1
        previous_analysis: Analysis from previous turn
        battle_log: Full battle history
        turn_events: Events from this turn
        our_fainted: List of our fainted Pokemon
        their_fainted: List of their fainted Pokemon
        revealed_sets: Information about opponent's revealed moves/items
        current_state: Current game state summary
        turn_number: Current turn number

    Returns:
        Formatted user prompt
    """
    return BATTLE_MEMORY_USER_PROMPT.format(
        battle_strategy=battle_strategy or "No initial strategy",
        previous_analysis=previous_analysis or "No previous analysis",
        battle_log=battle_log or "No previous turns",
        turn_events=turn_events,
        our_fainted=our_fainted or "None",
        their_fainted=their_fainted or "None",
        revealed_sets=revealed_sets or "No revealed information",
        current_state=current_state,
        turn_number=turn_number,
    )
