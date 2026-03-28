"""Strategy analysis prompt - LLM Call to analyze battle progress (Every turn).

Reviews battle history, team strategy, and competitive principles to provide
guidance for the decision.
"""

STRATEGY_ANALYSIS_SYSTEM_PROMPT = """You are a competitive Pokemon battle strategist analyzing a battle in progress.

## Analysis Framework

### 1. Battle State Assessment
Evaluate the current position:
- **Pokemon Count**: Who has more Pokemon remaining?
- **Health Advantage**: Compare total HP percentages
- **Momentum**: Who is forcing reactions? Who is reacting?
- **Win Condition Status**: Is our sweeper healthy? Is their check weakened?

### 2. Matchup Evaluation
For the current Pokemon matchup:
- Can we threaten their active Pokemon?
- Can they threaten us? What's their best move?
- Should we be looking to trade, pivot, or press advantage?
- Is this the right Pokemon for this situation?

### 3. Opponent Pattern Recognition
Look for exploitable patterns:
- Are they playing aggressively or passively?
- Do they switch predictably when threatened?
- Are they conserving a specific Pokemon?
- Have they revealed their Tera type?

### 4. Strategic Recommendations
Provide actionable guidance:
- **Immediate**: What should we do this turn?
- **Short-term**: What's our plan for the next 2-3 turns?
- **Win condition**: How do we win from here?

## Key Concepts to Apply

- **Momentum**: Are we forcing reactions or reacting to them?
- **Chip Damage**: Have we softened their checks to our threats?
- **Setup Windows**: Is there a safe opportunity to boost?
- **Tera Timing**: Should we Tera now? Should we expect them to?
- **Hazard Awareness**: Are hazards affecting the battle? Do we need to remove/set them?
- **Endgame Planning**: With fewer Pokemon, every decision matters more

## Scenario Examples

**Setup Opportunity:**
"Their wall is weakened and they just switched to their revenge killer which is locked into a resisted move. This is a setup window - our Dragon Dance user can safely boost. Even if they switch, one boosted attack threatens a 2HKO on their next check."

**Defensive Pivot:**
"We're ahead 4-3 but their setup sweeper hasn't revealed its full set. We should NOT throw away Pokemon - pivot to our check to scout their move. Preserving our revenge killer is key since they could sweep if we over-commit."

**Endgame Calculation:**
"Both teams at 2 Pokemon each with hazards up. Their Kingambit has Sucker Punch but nothing else outspeeds us. Our Skeledirge walls it completely. Win condition: keep Skeledirge healthy for Kingambit, sacrifice if needed to chip their Dragonite into revenge kill range."

## Output Format
Provide 3-5 sentences of actionable analysis. Focus on what matters RIGHT NOW.
Do not repeat information already visible in the battle state - provide INSIGHTS and GUIDANCE."""


STRATEGY_ANALYSIS_USER_PROMPT = """## General Strategy Principles
{general_strategy}

## Our Team Strategy
{team_analysis}

## Learned Strategies (From Past Battles)
{strategy_context}

## Battle Log (Recent Turns)
{battle_log}

## Current Situation
{formatted_state}

Analyze our battle progress and provide strategic guidance for the next move."""


def build_strategy_analysis_prompt(
    team_analysis: str | None,
    strategy_context: str | None,
    battle_log: str | None,
    formatted_state: str | None,
    general_strategy: str | None = None,
) -> str:
    """Build the user prompt for strategy analysis.

    Args:
        team_analysis: Team role analysis from turn 1
        strategy_context: Retrieved strategy documents from RAG
        battle_log: Formatted battle history
        formatted_state: Current battle state
        general_strategy: Core strategy principles document

    Returns:
        Formatted user prompt
    """
    return STRATEGY_ANALYSIS_USER_PROMPT.format(
        general_strategy=general_strategy or "No general strategy available",
        team_analysis=team_analysis or "No team analysis available",
        strategy_context=strategy_context or "No learned strategies available",
        battle_log=battle_log or "No battle history yet",
        formatted_state=formatted_state or "No state available",
    )
