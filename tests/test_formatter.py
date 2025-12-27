"""Tests for battle state formatter."""

import pytest
from src.showdown.formatter import format_battle_state, _format_pokemon, _format_move


class TestFormatPokemon:
    """Tests for _format_pokemon function."""

    def test_format_pokemon_basic(self, mock_pokemon):
        """Test basic Pokemon formatting."""
        result = _format_pokemon(mock_pokemon)
        assert "Garchomp" in result
        assert "HP" in result
        assert "Dragon" in result
        assert "Ground" in result

    def test_format_pokemon_with_status(self, mock_pokemon):
        """Test Pokemon formatting with status condition."""
        mock_pokemon.status = type("Status", (), {"name": "brn"})()
        result = _format_pokemon(mock_pokemon)
        assert "Burned" in result

    def test_format_pokemon_with_boosts(self, mock_pokemon):
        """Test Pokemon formatting with stat boosts."""
        mock_pokemon.boosts = {"atk": 2, "spe": -1}
        result = _format_pokemon(mock_pokemon)
        assert "+2" in result
        assert "-1" in result

    def test_format_opponent_pokemon(self, mock_opponent_pokemon):
        """Test opponent Pokemon formatting (HP as percentage only)."""
        result = _format_pokemon(mock_opponent_pokemon, is_opponent=True)
        assert "100% HP" in result
        assert "Weavile" in result


class TestFormatMove:
    """Tests for _format_move function."""

    def test_format_move_basic(self, mock_move):
        """Test basic move formatting."""
        result = _format_move(mock_move, 1)
        assert "1." in result
        assert "Earthquake" in result
        assert "Ground" in result
        assert "100" in result


class TestFormatBattleState:
    """Tests for format_battle_state function."""

    def test_format_includes_turn(self, mock_battle):
        """Test that formatted state includes turn number."""
        result = format_battle_state(mock_battle)
        assert "Turn 5" in result

    def test_format_includes_active_pokemon(self, mock_battle):
        """Test that formatted state includes active Pokemon."""
        result = format_battle_state(mock_battle)
        assert "Your Pokemon" in result
        assert "Opponent Pokemon" in result

    def test_format_includes_moves(self, mock_battle):
        """Test that formatted state includes available moves."""
        result = format_battle_state(mock_battle)
        assert "Available Moves" in result
        assert "Earthquake" in result

    def test_format_includes_switches(self, mock_battle, mock_pokemon):
        """Test that formatted state includes available switches."""
        switch_pokemon = mock_pokemon
        switch_pokemon.species = "rotom-wash"
        mock_battle.available_switches = [switch_pokemon]

        result = format_battle_state(mock_battle)
        assert "Available Switches" in result
        assert "Rotom" in result

    def test_format_includes_field_conditions(self, mock_battle):
        """Test that formatted state includes field conditions section."""
        result = format_battle_state(mock_battle)
        assert "Field Conditions" in result

    def test_format_ends_with_prompt(self, mock_battle):
        """Test that formatted state ends with action prompt."""
        result = format_battle_state(mock_battle)
        assert "What should you do?" in result
