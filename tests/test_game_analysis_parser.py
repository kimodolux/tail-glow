from src.agent.prompts.game_analysis import parse_game_analysis_response
from src.rag.models import MatchupOutcome


def test_parse_matchups_with_simple_names():
    response = """## MATCHUPS_LEARNED
- Dragapult (special_attacker) WINS vs Garchomp (physical_attacker) when both are healthy: "Draco Meteor forces the KO."

## MISTAKES
None identified

## TURNING_POINT
Turn 4: Dragapult removed Garchomp.

## SUMMARY
Result: WON
Reason: Dragapult broke their team.
Key lesson: Preserve speed control.
"""

    parsed = parse_game_analysis_response(response)

    assert parsed["matchups"] == [
        {
            "pokemon": "dragapult",
            "our_role": "special_attacker",
            "outcome": MatchupOutcome.WINS,
            "opponent": "garchomp",
            "opponent_role": "physical_attacker",
            "conditions": "both are healthy",
            "lesson": "Draco Meteor forces the KO.",
        }
    ]


def test_parse_matchups_with_spaces_hyphens_and_apostrophes():
    response = """## MATCHUPS_LEARNED
- Iron Valiant (mixed_attacker) WINS vs Wo-Chien (wall) when boosted by Booster Energy: "Moonblast breaks through."
- Landorus-Therian (pivot) DEPENDS vs Farfetch'd (physical_attacker) when hazards are up: "Intimidate gives enough room to pivot."

## MISTAKES
None identified

## TURNING_POINT
Turn 8: Iron Valiant cleaned.

## SUMMARY
Result: WON
Reason: Form matchups were handled well.
Key lesson: Track exact forms.
"""

    parsed = parse_game_analysis_response(response)

    assert [m["pokemon"] for m in parsed["matchups"]] == [
        "iron valiant",
        "landorus-therian",
    ]
    assert [m["opponent"] for m in parsed["matchups"]] == [
        "wo-chien",
        "farfetch'd",
    ]
    assert parsed["matchups"][0]["outcome"] == MatchupOutcome.WINS
    assert parsed["matchups"][1]["outcome"] == MatchupOutcome.DEPENDS
