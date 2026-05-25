"""Tests for the per-turn mechanics resolver.

Covers both selection paths: keyword matching against the effects text and
battle-state triggers (weather, field, side conditions).
"""

from collections import namedtuple
from types import SimpleNamespace

import pytest

_FakeEnum = namedtuple("_FakeEnum", ["name"])  # hashable stand-in for poke-env enums

from src.rag.mechanics_resolver import (
    clear_mechanics_cache,
    load_mechanics_chunks,
    resolve_mechanics,
)
from src.rag.strategy_loader import (
    clear_strategy_cache,
    get_general_strategy_section,
)


@pytest.fixture(autouse=True)
def _reset_caches():
    clear_mechanics_cache()
    clear_strategy_cache()
    yield
    clear_mechanics_cache()
    clear_strategy_cache()


def _fake_battle(weather=None, fields=None, side=None, opp_side=None):
    """Build a stand-in for poke-env's Battle with only the attributes we read."""
    def _enums(names):
        return {_FakeEnum(n): 1 for n in (names or [])}

    return SimpleNamespace(
        weather=_enums(weather),
        fields=_enums(fields),
        side_conditions=_enums(side),
        opponent_side_conditions=_enums(opp_side),
    )


def test_chunks_load_and_have_bodies():
    chunks = load_mechanics_chunks()
    assert chunks, "expected at least one mechanics chunk on disk"
    names = {c.name for c in chunks}
    # Spot-check a few chunks we expect by name
    assert {"weather_sun", "weather_rain", "hazards", "priority"} <= names
    # Every chunk should have a non-empty body
    assert all(c.body.strip() for c in chunks)


def test_keyword_match_pulls_chunk():
    """An ability/move name in the effects text should pull in the relevant chunk."""
    effects = "Ability (Drought): summons sun on switch-in"
    out = resolve_mechanics(effects, battle=None)
    assert "# Sun" in out
    # Unrelated chunks should not appear
    assert "# Rain" not in out
    assert "# Misty Terrain" not in out


def test_battle_state_trigger_pulls_chunk():
    """Active weather should trigger the matching chunk even without keyword hits."""
    battle = _fake_battle(weather=["RAINDANCE"])
    out = resolve_mechanics(effects_analysis=None, battle=battle)
    assert "# Rain" in out
    assert "# Sun" not in out


def test_side_condition_trigger_pulls_hazards():
    battle = _fake_battle(opp_side=["STEALTH_ROCK"])
    out = resolve_mechanics(effects_analysis=None, battle=battle)
    assert "# Entry Hazards" in out


def test_field_trigger_pulls_trick_room():
    battle = _fake_battle(fields=["TRICK_ROOM"])
    out = resolve_mechanics(effects_analysis=None, battle=battle)
    assert "# Trick Room" in out


def test_no_match_returns_empty_string():
    """Plain text with no mechanics references and no battle state -> empty output."""
    out = resolve_mechanics(
        effects_analysis="Your Garchomp has no special effects noted",
        battle=_fake_battle(),
    )
    assert out == ""


def test_multiple_matches_concatenated():
    """Keyword and trigger matches both apply and produce a combined section."""
    effects = "Possible moves: Sucker Punch, Sticky Web"
    battle = _fake_battle(weather=["SUNNYDAY"])
    out = resolve_mechanics(effects, battle)
    assert "## Relevant Mechanics" in out
    assert "# Priority" in out
    assert "# Entry Hazards" in out
    assert "# Sun" in out


def test_core_strategy_section_loads_mechanics_core_not_full_dump():
    """The always-on strategy section should pull mechanics_core only."""
    section = get_general_strategy_section()
    assert "Terastallization" in section
    assert "Status Conditions" in section
    assert "Stat Stages" in section
    # Chunk-only content should NOT be in the always-on section. We match on
    # phrases unique to the chunk bodies (the chunks may otherwise be mentioned
    # in passing inside core docs, which is fine).
    assert "Chlorophyll: Doubles Speed" not in section
    assert "Layer 1: 12.5% damage" not in section
    assert "Priority Brackets (high to low)" not in section
    assert "Aurora Veil" not in section


def test_resolver_robust_to_missing_battle_attrs():
    """A battle missing the optional attrs (None / not set) shouldn't blow up."""
    battle = SimpleNamespace()  # no weather/fields/side_conditions
    out = resolve_mechanics("plain effects text", battle)
    assert out == ""
