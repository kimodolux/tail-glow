"""Game-end analysis prompt - Extracts learnings from completed battles.

Analyzes the complete battle history to identify key matchups learned
and mistakes made that should be stored for future reference.
"""

import re
from typing import Optional

from src.rag.models import MatchupOutcome, MistakeType

GAME_ANALYSIS_SYSTEM_PROMPT = """You are analyzing a completed Pokemon battle to extract learnings for future games.

## Your Task
Review the complete battle history and identify:

1. **Key Matchups**: Pokemon vs Pokemon outcomes that should be remembered
   - Focus on non-obvious results (type advantages that didn't work, unexpected wins)
   - Note the conditions that affected the outcome
   - Consider the roles/sets involved, not just species

2. **Mistakes Made**: Plays that cost us advantage or the game
   - Only flag clear mistakes, not hindsight analysis
   - Include what the better play would have been
   - Consider what information we had at the time

3. **Turning Points**: The key moments that decided the game
   - When did momentum shift?
   - What was the decisive play?

4. **Key Lesson**: The main takeaway from this game

## Output Format

You MUST use EXACTLY this format:

```
## MATCHUPS_LEARNED
- [our_pokemon] ([our_role]) [WINS/LOSES/TRADES/DEPENDS] vs [opponent] ([opponent_role]) when [conditions]: "[lesson]"
- [another matchup in same format]
(Include 1-5 notable matchups)

## MISTAKES
- Turn [X]: [POKEMON_KOD/KOD_ON_SWITCH/SETUP_SNOWBALL/MISSED_KO/BAD_PREDICTION] - [description]. Better: [what we should have done]
(Include 0-3 clear mistakes, or "None identified" if no clear mistakes)

## TURNING_POINT
Turn [X]: [description of the pivotal moment that decided the game]

## SUMMARY
Result: [WON/LOST]
Reason: [1-2 sentence explanation of why we won or lost]
Key lesson: [main takeaway for future games]
```

## Important Guidelines

- Be selective with matchups - only include learnings that would be useful in future games
- Don't include obvious type matchups (Fire beats Grass, etc.)
- Focus on role-specific learnings (e.g., "Choice Specs Dragapult loses to Assault Vest Tyranitar")
- For mistakes, only flag clear errors, not every suboptimal play
- The key lesson should be actionable and specific"""


GAME_ANALYSIS_USER_PROMPT = """Analyze this completed battle.

## Result
{result}

## Our Team Analysis (from turn 1)
{team_analysis}

## Complete Battle History
{battle_history}

## Detected Mistakes During Game
{accumulated_mistakes}

Extract the key learnings from this game."""


def build_game_analysis_prompt(
    won: bool,
    team_analysis: str | None,
    battle_history: str,
    accumulated_mistakes: list | None = None,
) -> str:
    """Build the user prompt for game analysis.

    Args:
        won: Whether we won the battle
        team_analysis: Our team role analysis from turn 1
        battle_history: Complete formatted battle history
        accumulated_mistakes: List of mistakes detected during the game

    Returns:
        Formatted user prompt
    """
    result = "WON" if won else "LOST"

    # Format accumulated mistakes
    mistakes_str = "None detected during game"
    if accumulated_mistakes:
        mistake_lines = []
        for m in accumulated_mistakes:
            if hasattr(m, 'mistake_type'):
                mistake_lines.append(
                    f"- Turn {m.turn}: {m.mistake_type.value} - {m.what_happened}"
                )
        if mistake_lines:
            mistakes_str = "\n".join(mistake_lines)

    return GAME_ANALYSIS_USER_PROMPT.format(
        result=result,
        team_analysis=team_analysis or "No team analysis available",
        battle_history=battle_history,
        accumulated_mistakes=mistakes_str,
    )


def parse_game_analysis_response(response: str) -> dict:
    """Parse the LLM response to extract structured learnings.

    Args:
        response: Raw LLM response

    Returns:
        Dict with parsed learnings:
        - matchups: List of matchup dicts
        - mistakes: List of mistake dicts
        - turning_point: Dict with turn and description
        - summary: Dict with result, reason, lesson
    """
    result = {
        "matchups": [],
        "mistakes": [],
        "turning_point": None,
        "summary": {},
    }

    # Split into sections
    sections = response.split("##")

    for section in sections:
        section = section.strip()
        if not section:
            continue

        if section.startswith("MATCHUPS_LEARNED"):
            result["matchups"] = _parse_matchups(section)
        elif section.startswith("MISTAKES"):
            result["mistakes"] = _parse_mistakes(section)
        elif section.startswith("TURNING_POINT"):
            result["turning_point"] = _parse_turning_point(section)
        elif section.startswith("SUMMARY"):
            result["summary"] = _parse_summary(section)

    return result


def _parse_matchups(section: str) -> list[dict]:
    """Parse the matchups section.

    Expected format:
    - [our_pokemon] ([our_role]) [WINS/LOSES/TRADES/DEPENDS] vs [opponent] ([opponent_role]) when [conditions]: "[lesson]"
    """
    matchups = []
    lines = section.split("\n")

    # Pattern: - pokemon (role) OUTCOME vs opponent (role) when conditions: "lesson"
    pattern = r'-\s*(\w+)\s*\(([^)]+)\)\s*(WINS|LOSES|TRADES|DEPENDS)\s*vs\s*(\w+)\s*\(([^)]+)\)\s*when\s*([^:]+):\s*["\']?([^"\']+)["\']?'

    for line in lines:
        line = line.strip()
        if not line or not line.startswith("-"):
            continue

        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            outcome_str = match.group(3).upper()
            try:
                outcome = MatchupOutcome(outcome_str.lower())
            except ValueError:
                outcome = MatchupOutcome.DEPENDS

            matchups.append({
                "pokemon": match.group(1).lower(),
                "our_role": match.group(2).strip(),
                "outcome": outcome,
                "opponent": match.group(4).lower(),
                "opponent_role": match.group(5).strip(),
                "conditions": match.group(6).strip(),
                "lesson": match.group(7).strip(),
            })

    return matchups


def _parse_mistakes(section: str) -> list[dict]:
    """Parse the mistakes section.

    Expected format:
    - Turn [X]: [MISTAKE_TYPE] - [description]. Better: [what we should have done]
    """
    mistakes = []
    lines = section.split("\n")

    # Pattern: - Turn X: TYPE - description. Better: better_play
    pattern = r'-\s*Turn\s*(\d+):\s*(\w+)\s*-\s*([^.]+)\.\s*Better:\s*(.+)'

    for line in lines:
        line = line.strip()
        if not line or not line.startswith("-"):
            continue

        if "None identified" in line.lower():
            continue

        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            type_str = match.group(2).upper()
            try:
                mistake_type = MistakeType(type_str.lower())
            except ValueError:
                # Try to match by name
                mistake_type = MistakeType.BAD_PREDICTION
                for mt in MistakeType:
                    if mt.name == type_str or type_str in mt.name:
                        mistake_type = mt
                        break

            mistakes.append({
                "turn": int(match.group(1)),
                "mistake_type": mistake_type,
                "what_happened": match.group(3).strip(),
                "better_play": match.group(4).strip(),
            })

    return mistakes


def _parse_turning_point(section: str) -> Optional[dict]:
    """Parse the turning point section.

    Expected format:
    Turn [X]: [description]
    """
    lines = section.split("\n")

    pattern = r'Turn\s*(\d+):\s*(.+)'

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            return {
                "turn": int(match.group(1)),
                "description": match.group(2).strip(),
            }

    return None


def _parse_summary(section: str) -> dict:
    """Parse the summary section.

    Expected format:
    Result: [WON/LOST]
    Reason: [explanation]
    Key lesson: [lesson]
    """
    result = {}
    lines = section.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.lower().startswith("result:"):
            result["won"] = "WON" in line.upper()
        elif line.lower().startswith("reason:"):
            result["reason"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("key lesson:"):
            result["key_lesson"] = line.split(":", 1)[1].strip()

    return result
