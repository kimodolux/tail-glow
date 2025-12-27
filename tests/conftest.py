"""Pytest fixtures for Tail Glow tests."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_pokemon():
    """Create a mock Pokemon object."""
    pokemon = MagicMock()
    pokemon.species = "garchomp"
    pokemon.current_hp = 280
    pokemon.max_hp = 357
    pokemon.current_hp_fraction = 280 / 357
    pokemon.types = [MagicMock(name="DRAGON"), MagicMock(name="GROUND")]
    pokemon.types[0].name = "DRAGON"
    pokemon.types[1].name = "GROUND"
    pokemon.status = None
    pokemon.boosts = {}
    return pokemon


@pytest.fixture
def mock_opponent_pokemon():
    """Create a mock opponent Pokemon object."""
    pokemon = MagicMock()
    pokemon.species = "weavile"
    pokemon.current_hp_fraction = 1.0
    pokemon.types = [MagicMock(name="DARK"), MagicMock(name="ICE")]
    pokemon.types[0].name = "DARK"
    pokemon.types[1].name = "ICE"
    pokemon.status = None
    pokemon.boosts = {}
    return pokemon


@pytest.fixture
def mock_move():
    """Create a mock Move object."""
    move = MagicMock()
    move.id = "earthquake"
    move.base_power = 100
    move.accuracy = 100
    move.type = MagicMock()
    move.type.name = "GROUND"
    move.category = MagicMock()
    move.category.name = "PHYSICAL"
    return move


@pytest.fixture
def mock_battle(mock_pokemon, mock_opponent_pokemon, mock_move):
    """Create a mock Battle object."""
    battle = MagicMock()
    battle.turn = 5
    battle.battle_tag = "battle-gen9randombattle-12345"
    battle.active_pokemon = mock_pokemon
    battle.opponent_active_pokemon = mock_opponent_pokemon
    battle.available_moves = [mock_move]
    battle.available_switches = []
    battle.weather = {}
    battle.fields = []
    battle.side_conditions = []
    battle.opponent_side_conditions = []
    return battle


@pytest.fixture
def sample_agent_state():
    """Create a sample AgentState for testing."""
    return {
        "battle_tag": "battle-gen9randombattle-12345",
        "battle_object": None,
        "turn": 5,
        "formatted_state": "# Turn 5\n\n## Active Pokemon\n...",
        "tool_results": {},
        "llm_response": "",
        "action_type": None,
        "action_target": None,
        "error": None,
    }
