"""Team analysis prompt - LLM Call #1 (Turn 1 only).

Analyzes the team composition to identify roles, strengths, and weaknesses.
"""

TEAM_ANALYSIS_SYSTEM_PROMPT = """You are an expert Pokemon team analyst. Your job is to analyze a team composition and identify each Pokemon's competitive role.

For each Pokemon, identify:
1. **Role**: sweeper, wallbreaker, wall, pivot, revenge killer, setup sweeper, hazard setter, support, etc.
2. **Strengths**: What types or Pokemon it handles well
3. **Weaknesses**: What threatens it
4. **Key features**: Important moves, abilities, or items to leverage

Keep your analysis concise - 1-2 sentences per Pokemon plus a brief team summary."""


TEAM_ANALYSIS_USER_PROMPT = """Analyze this Pokemon team and catalog each member's role:

{team_info}

Provide:
1. A role classification for each Pokemon
2. What each Pokemon is good at handling
3. Key threats to watch out for
4. A brief team summary (offensive/defensive balance, synergy notes)

Output format:
## Team Analysis

**[Pokemon 1 Name]**: [Role] - [Brief description of strengths and what it handles]

**[Pokemon 2 Name]**: [Role] - [Brief description]

... (continue for all Pokemon)

## Team Summary
[2-3 sentences about team composition, win conditions, and key threats to the team]"""


def build_team_analysis_prompt(team_info: str) -> str:
    """Build the user prompt for team analysis.

    Args:
        team_info: Formatted string describing the team

    Returns:
        Formatted user prompt
    """
    return TEAM_ANALYSIS_USER_PROMPT.format(team_info=team_info)
