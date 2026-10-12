"""Tests for the deterministic damage calculator node.

These build a real poke-env ``Battle`` (rather than a mock) because the damage
calculator reads concrete stats, types and moves off the battle object.
"""

import logging

import pytest
from poke_env.battle import Battle

from src.agent.belief import BattleBelief
from src.agent.damage import compute_damage_report
from src.agent.nodes.damage_calc import damage_calc_node
from src.agent.nodes.resolve_opponent import resolve_opponent_node


def _belief_for(battle: Battle) -> BattleBelief:
    """Populate a belief the way the graph does (resolve_opponent then read)."""
    belief = BattleBelief(format_id=battle.format)
    resolve_opponent_node({"battle_object": battle, "opponent_belief": belief})
    return belief


def _report(battle: Battle) -> str:
    """Damage report with opponent stats sourced from the belief (as in the graph)."""
    return compute_damage_report(battle, _belief_for(battle))


def _build_battle() -> Battle:
    """A gen9 battle: our Dragonite (+ Skarmory switch) vs opponent Garchomp."""
    battle = Battle("battle-gen9ou-test", "me", logging.getLogger("test"), gen=9)

    request = {
        "active": [
            {
                "moves": [
                    {"move": "Outrage", "id": "outrage", "pp": 16, "maxpp": 16,
                     "target": "randomNormal", "disabled": False},
                    {"move": "Earthquake", "id": "earthquake", "pp": 16, "maxpp": 16,
                     "target": "allAdjacent", "disabled": False},
                    {"move": "Fire Punch", "id": "firepunch", "pp": 24, "maxpp": 24,
                     "target": "normal", "disabled": False},
                ]
            }
        ],
        "side": {
            "name": "me",
            "id": "p1",
            "pokemon": [
                {
                    "ident": "p1: Dragonite",
                    "details": "Dragonite, L50, M",
                    "condition": "180/180",
                    "active": True,
                    "stats": {"atk": 160, "def": 110, "spa": 120, "spd": 110, "spe": 100},
                    "moves": ["outrage", "earthquake", "firepunch"],
                    "baseAbility": "multiscale",
                    "item": "leftovers",
                    "pokeball": "pokeball",
                },
                {
                    "ident": "p1: Skarmory",
                    "details": "Skarmory, L50, M",
                    "condition": "160/160",
                    "active": False,
                    "stats": {"atk": 90, "def": 180, "spa": 60, "spd": 100, "spe": 90},
                    "moves": ["bravebird", "roost"],
                    "baseAbility": "sturdy",
                    "item": "rockyhelmet",
                    "pokeball": "pokeball",
                },
            ],
        },
        "rqid": 1,
    }
    battle.parse_request(request)

    battle.parse_message(["", "switch", "p2a: Garchomp", "Garchomp, L50, M", "200/200"])
    battle.parse_message(["", "move", "p2a: Garchomp", "Earthquake", "p1a: Dragonite"])
    battle.parse_message(["", "move", "p2a: Garchomp", "Dragon Claw", "p1a: Dragonite"])
    return battle


@pytest.fixture
def battle() -> Battle:
    return _build_battle()


class TestComputeDamageReport:
    """Tests for compute_damage_report."""

    def test_has_both_sections(self, battle):
        report = _report(battle)
        assert "Your moves vs Garchomp" in report
        assert "Incoming damage" in report

    def test_outgoing_moves_have_percentages(self, battle):
        report = _report(battle)
        # Outrage (Dragon STAB) into Garchomp is a big hit and can KO.
        assert "Outrage" in report
        assert "%" in report
        assert "KO" in report

    def test_ground_immunity_shows_no_damage(self, battle):
        """Garchomp's Earthquake can't hit our Flying-type Dragonite/Skarmory."""
        report = _report(battle)
        # Only inspect the incoming section (our Dragonite also carries Earthquake).
        incoming = report.split("### Incoming damage")[1]
        eq_lines = [
            line for line in incoming.splitlines()
            if line.startswith("- Earthquake")
        ]
        assert eq_lines
        assert all("no damage" in line for line in eq_lines)

    def test_incoming_lists_active_and_switch(self, battle):
        report = _report(battle)
        assert "your active Dragonite" in report
        assert "your switch Skarmory" in report

    def test_does_not_mutate_opponent_stats(self, battle):
        """Estimated opponent stats must be restored after calculation."""
        _report(battle)
        assert all(v is None for v in battle.opponent_active_pokemon.stats.values())

    def test_no_opponent_moves_revealed(self):
        battle = _build_battle()
        battle.opponent_active_pokemon._moves = {}
        report = _report(battle)
        assert "No opponent moves revealed" in report

    def test_missing_active_pokemon_is_graceful(self):
        battle = Battle("battle-gen9ou-empty", "me", logging.getLogger("test"), gen=9)
        report = _report(battle)
        assert "Unavailable" in report


class TestDamageCalcNode:
    """Tests for the graph node wrapper."""

    def test_node_sets_damage_report(self, battle):
        state = {"battle_object": battle}
        result = damage_calc_node(state)
        assert result["damage_report"]
        assert "Damage Calculations" in result["damage_report"]

    def test_node_handles_missing_battle(self):
        result = damage_calc_node({"battle_object": None})
        assert result["damage_report"] is None
