"""Tests for role-narrowing in RandbatsData.

Uses the real Dragapult 3-role structure to verify that revealed moves
shrink the candidate role list (and therefore the items/abilities/teras).
"""

import pytest

from src.data.randbats import RandbatsData, RandbatsPokemon, RandbatsRole


@pytest.fixture
def dragapult_data() -> RandbatsData:
    """Build a Dragapult entry with the three real randbats roles."""
    roles = {
        "Fast Support": RandbatsRole(
            name="Fast Support",
            moves=["Dragon Darts", "Hex", "U-turn", "Will-O-Wisp"],
            abilities=["Cursed Body", "Infiltrator"],
            items=["Heavy-Duty Boots"],
            tera_types=["Dragon", "Fairy"],
        ),
        "Fast Attacker": RandbatsRole(
            name="Fast Attacker",
            moves=["Draco Meteor", "Fire Blast", "Shadow Ball", "U-turn"],
            abilities=["Infiltrator"],
            items=["Choice Specs"],
            tera_types=["Dragon", "Fire", "Ghost"],
        ),
        "Tera Blast user": RandbatsRole(
            name="Tera Blast user",
            moves=["Dragon Dance", "Dragon Darts", "Fire Blast", "Tera Blast"],
            abilities=["Clear Body"],
            items=["Life Orb"],
            tera_types=["Ghost"],
        ),
    }
    pokemon = RandbatsPokemon(
        species="Dragapult",
        level=77,
        abilities=["Clear Body", "Cursed Body", "Infiltrator"],
        items=["Choice Specs", "Heavy-Duty Boots", "Life Orb"],
        roles=roles,
    )
    return RandbatsData({"Dragapult": pokemon})


def test_no_revealed_moves_returns_all_roles(dragapult_data):
    roles = dragapult_data.get_compatible_roles("Dragapult", [])
    assert len(roles) == 3


def test_dragon_dance_locks_to_tera_blast_user(dragapult_data):
    roles = dragapult_data.get_compatible_roles("Dragapult", ["Dragon Dance"])
    assert [r.name for r in roles] == ["Tera Blast user"]


def test_uturn_narrows_to_two_roles(dragapult_data):
    roles = dragapult_data.get_compatible_roles("Dragapult", ["U-turn"])
    names = sorted(r.name for r in roles)
    assert names == ["Fast Attacker", "Fast Support"]


def test_multiple_reveals_intersect(dragapult_data):
    # U-turn AND Will-O-Wisp → only Fast Support
    roles = dragapult_data.get_compatible_roles(
        "Dragapult", ["U-turn", "Will-O-Wisp"]
    )
    assert [r.name for r in roles] == ["Fast Support"]


def test_unknown_move_returns_empty_list(dragapult_data):
    # Earthquake is not in any role → no compatible role
    roles = dragapult_data.get_compatible_roles("Dragapult", ["Earthquake"])
    assert roles == []


def test_move_name_normalization(dragapult_data):
    # "Dragon Dance" and "dragondance" should both match the Tera Blast user
    via_space = dragapult_data.get_compatible_roles("Dragapult", ["Dragon Dance"])
    via_normalized = dragapult_data.get_compatible_roles("Dragapult", ["dragondance"])
    via_dash = dragapult_data.get_compatible_roles("Dragapult", ["dragon-dance"])
    assert [r.name for r in via_space] == ["Tera Blast user"]
    assert [r.name for r in via_normalized] == ["Tera Blast user"]
    assert [r.name for r in via_dash] == ["Tera Blast user"]


def test_unknown_species_returns_empty_list(dragapult_data):
    assert dragapult_data.get_compatible_roles("Mewtwo", []) == []


def test_pokemon_state_narrowed_views(dragapult_data):
    """End-to-end: PokemonState.narrowed_* helpers reflect reveals."""
    from src.battle.teams_state import PokemonState

    state = PokemonState(
        species="Dragapult",
        level=77,
        stats={"hp": 1, "atk": 1, "def": 1, "spa": 1, "spd": 1, "spe": 1},
        possible_moves={"dragondance", "dragondarts", "fireblast", "terablast",
                        "dracometeor", "shadowball", "uturn",
                        "hex", "willowisp"},
        possible_abilities=["Clear Body", "Cursed Body", "Infiltrator"],
        possible_items=["Choice Specs", "Heavy-Duty Boots", "Life Orb"],
        possible_tera_types=["Dragon", "Fairy", "Fire", "Ghost"],
    )

    # No reveals → narrowed view equals full union
    assert state.narrowed_items(dragapult_data) == [
        "Heavy-Duty Boots", "Choice Specs", "Life Orb"
    ]

    # Dragon Dance revealed → only Life Orb / Clear Body / Ghost remain
    state.revealed_moves = ["Dragon Dance"]
    assert state.narrowed_items(dragapult_data) == ["Life Orb"]
    assert state.narrowed_abilities(dragapult_data) == ["Clear Body"]
    assert state.narrowed_tera_types(dragapult_data) == ["Ghost"]
    assert state.narrowed_moves(dragapult_data) == {
        "dragondance", "dragondarts", "fireblast", "terablast"
    }


def test_narrowing_falls_back_when_no_role_matches(dragapult_data):
    """If reveals don't match any role, fall back to the full union (don't crash)."""
    from src.battle.teams_state import PokemonState

    state = PokemonState(
        species="Dragapult",
        level=77,
        stats={"hp": 1, "atk": 1, "def": 1, "spa": 1, "spd": 1, "spe": 1},
        possible_items=["Choice Specs", "Heavy-Duty Boots", "Life Orb"],
    )
    state.revealed_moves = ["Earthquake"]  # not in any role

    assert state.narrowed_items(dragapult_data) == [
        "Choice Specs", "Heavy-Duty Boots", "Life Orb"
    ]
