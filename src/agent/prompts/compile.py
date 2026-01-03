"""Compile prompt - LLM Call #2 (Every turn).

Synthesizes all gathered information into a focused battle analysis.
"""

COMPILE_SYSTEM_PROMPT = """You are a Pokemon battle analyst. Your job is to synthesize battle information into a concise, actionable analysis.

Focus on:
1. The key threat or opportunity this turn
2. Critical risks to avoid
3. The best available options

Be direct and specific. Reference the damage calculations and speed analysis to support your conclusions."""

COMPILE_USER_PROMPT = """Synthesize this battle information into a concise analysis:

## Current Situation
{formatted_state}

{damage_calculations}

{speed_analysis}

{type_matchups}

{effects_analysis}

{strategy_context}

## Our Team Analysis
{team_analysis}

---

Provide a focused 3-5 sentence analysis covering:
1. **Key Threat/Opportunity**: What's most important this turn?
2. **Risks**: What should we be careful about?
3. **Best Options**: What are our strongest plays?

Be specific - reference damage percentages, KO chances, and speed comparisons from the data above."""


def build_compile_prompt(
    formatted_state: str,
    damage_calculations: str | None,
    speed_analysis: str | None,
    type_matchups: str | None,
    effects_analysis: str | None,
    strategy_context: str | None,
    team_analysis: str | None,
) -> str:
    """Build the user prompt for context compilation.

    Args:
        formatted_state: Current battle state
        damage_calculations: Formatted damage calc results
        speed_analysis: Formatted speed analysis
        type_matchups: Formatted type matchup info
        effects_analysis: Formatted effects info
        strategy_context: Retrieved strategy documents
        team_analysis: Team role analysis from turn 1

    Returns:
        Formatted user prompt
    """
    return COMPILE_USER_PROMPT.format(
        formatted_state=formatted_state or "No state available",
        damage_calculations=damage_calculations or "No damage calculations available",
        speed_analysis=speed_analysis or "No speed analysis available",
        type_matchups=type_matchups or "No type matchups available",
        effects_analysis=effects_analysis or "No effects analysis available",
        strategy_context=strategy_context or "No strategy notes available",
        team_analysis=team_analysis or "No team analysis available",
    )
