"""Create battle strategy prompt - LLM Call (Turn 1 only).

Creates an initial game plan based on team analysis.
"""

CREATE_STRATEGY_SYSTEM_PROMPT = """You are a Pokemon battle strategist. Based on team analysis, create a battle strategy.

Your strategy should identify:
1. **Win conditions**: How this team wins games (e.g., "sweep with Dragonite after removing checks")
2. **Type coverage gaps**: Types that the team struggles to handle
3. **Threats to setup sweepers**: Pokemon/moves that prevent win conditions
4. **Team-wide weaknesses**: Common types that hit multiple team members hard
5. **Key Pokemon to preserve**: Which Pokemon are essential for the win condition
6. **Expendable Pokemon**: Which can be sacrificed for momentum

Be concise and actionable. Focus on information that will help in-battle decision making."""


CREATE_STRATEGY_USER_PROMPT = """Based on this team analysis, create a battle strategy:

## Team Analysis
{team_analysis}

Create a battle strategy document that covers:

1. **Win Conditions**: How does this team win? What's the primary game plan?

2. **Type Coverage Gaps**: What types can this team NOT hit super-effectively? What types wall this team?

3. **Setup Threats**: What prevents the win condition? (priority moves, faster threats, phazers, etc.)

4. **Team Weaknesses**: What types hit 3+ Pokemon super-effectively?

5. **Preserve Priority**: Which Pokemon MUST stay alive for the win condition?

6. **Sack Candidates**: Which Pokemon can be sacrificed for momentum or to bring in a sweeper safely?

Output format:
## Battle Strategy

### Win Conditions
[Primary and secondary win conditions]

### Coverage Gaps
[Types that wall us or we can't hit]

### Setup Threats
[What stops our sweepers]

### Team Weaknesses
[Common weaknesses across the team]

### Preserve
[Pokemon to keep healthy]

### Expendable
[Pokemon that can be sacrificed]"""


def build_create_strategy_prompt(team_analysis: str) -> str:
    """Build the user prompt for battle strategy creation.

    Args:
        team_analysis: The team analysis from analyze_team node

    Returns:
        Formatted user prompt
    """
    return CREATE_STRATEGY_USER_PROMPT.format(team_analysis=team_analysis)
