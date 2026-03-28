"""Turn analysis prompt - Detects mistakes after each turn.

Analyzes the previous turn's outcome to identify potential mistakes
that should be learned from and avoided in future games.
"""

from src.rag.models import MistakeType

TURN_ANALYSIS_SYSTEM_PROMPT = """You are analyzing a Pokemon battle turn to detect if a mistake was made.

Your job is to identify mistakes we made that we should learn from. Be selective - only flag clear mistakes, not every suboptimal play.

## Mistake Types to Detect

1. **POKEMON_KOD**: Our Pokemon was KO'd when it could have been avoided
   - We stayed in when we should have switched
   - We misjudged the damage we would take
   - We didn't account for their priority move

2. **KOD_ON_SWITCH**: Our Pokemon was KO'd as it switched in
   - We switched into a predicted move
   - We didn't account for coverage moves
   - Note: Sometimes sacrificing a Pokemon is correct - only flag if it was a mistake

3. **SETUP_SNOWBALL**: We let the opponent setup too much
   - They got 2+ boosts that we could have prevented
   - We had a faster attacker or priority move available
   - We stayed in too long trying to do damage

4. **MISSED_KO**: We had a KO opportunity but didn't take it
   - We used a non-KO move when we had the KO
   - We switched out when we could have eliminated a threat
   - The damage calc showed we could KO but we didn't

5. **BAD_PREDICTION**: We made a wrong prediction that cost us
   - We doubled into a resist
   - We predicted a switch that didn't happen
   - Note: Only flag if the prediction was unreasonable given the information

## What is NOT a Mistake

- Losing a calculated trade (1-for-1 that benefits us)
- Sacrificing a Pokemon to get a free switch
- Playing safe when ahead
- Losing to a critical hit or unlikely event
- Making a reasonable prediction that didn't work out

## Analysis Instructions

1. Review what happened on the turn
2. Consider our reasoning at the time
3. Think about what information we had available
4. Determine if there was a clearly better play
5. If a mistake was made, identify what we should have done

## Output Format

If a mistake was detected, output EXACTLY in this format:
```
MISTAKE_DETECTED
TYPE: [mistake_type from the list above]
CONTEXT: [1 sentence describing the situation before the turn]
WHAT_HAPPENED: [1 sentence describing what occurred]
BETTER_PLAY: [1 sentence describing what we should have done]
LESSON: [1 sentence takeaway for future games]
```

If no clear mistake was made, output:
```
NO_MISTAKE_DETECTED
REASON: [Brief explanation of why this wasn't a mistake, or why any suboptimal play was reasonable]
```"""


TURN_ANALYSIS_USER_PROMPT = """Analyze the previous turn for potential mistakes.

## Turn {turn_number} Events
{turn_events}

## Our Reasoning at the Time
{our_reasoning}

## Damage Context (What We Knew)
{damage_context}

## Outcome
{outcome}

Was this a mistake? If so, what should we have done differently?"""


def build_turn_analysis_prompt(
    turn_number: int,
    turn_events: str,
    our_reasoning: str | None,
    damage_context: str | None,
    outcome: str,
) -> str:
    """Build the user prompt for turn analysis.

    Args:
        turn_number: The turn being analyzed
        turn_events: Description of what happened on the turn
        our_reasoning: Our stated reasoning for the move (if available)
        damage_context: Damage calculations we had access to
        outcome: The result of the turn (who took damage, KOs, etc.)

    Returns:
        Formatted user prompt
    """
    return TURN_ANALYSIS_USER_PROMPT.format(
        turn_number=turn_number,
        turn_events=turn_events or "No turn events recorded",
        our_reasoning=our_reasoning or "No reasoning recorded",
        damage_context=damage_context or "No damage calculations available",
        outcome=outcome or "Unknown outcome",
    )


def parse_mistake_response(response: str) -> dict | None:
    """Parse the LLM response to extract mistake information.

    Args:
        response: Raw LLM response

    Returns:
        Dict with mistake details, or None if no mistake detected
    """
    response = response.strip()

    if response.startswith("NO_MISTAKE_DETECTED"):
        return None

    if not response.startswith("MISTAKE_DETECTED"):
        # Unexpected format - try to extract what we can
        return None

    result = {}
    lines = response.split("\n")

    for line in lines:
        line = line.strip()
        if line.startswith("TYPE:"):
            type_str = line.replace("TYPE:", "").strip().upper()
            # Map to MistakeType enum
            try:
                result["mistake_type"] = MistakeType(type_str.lower())
            except ValueError:
                # Try to match by name
                for mt in MistakeType:
                    if mt.name == type_str or mt.value == type_str.lower():
                        result["mistake_type"] = mt
                        break
        elif line.startswith("CONTEXT:"):
            result["context"] = line.replace("CONTEXT:", "").strip()
        elif line.startswith("WHAT_HAPPENED:"):
            result["what_happened"] = line.replace("WHAT_HAPPENED:", "").strip()
        elif line.startswith("BETTER_PLAY:"):
            result["better_play"] = line.replace("BETTER_PLAY:", "").strip()
        elif line.startswith("LESSON:"):
            result["lesson"] = line.replace("LESSON:", "").strip()

    # Validate we have required fields
    if "mistake_type" in result and "what_happened" in result:
        return result

    return None
