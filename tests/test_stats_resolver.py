"""Unit tests for the meta-aware StatsResolver."""

from unittest.mock import MagicMock

import pytest

from src.stats import (
    NonRandomResolver,
    RandbatsResolver,
    Spread,
    load_common_spreads,
    make_resolver,
)
from src.stats.factory import is_random_format


def _mock_pokemon(species: str, stats=None, level=100, item=None, ability=None):
    pk = MagicMock()
    pk.species = species
    pk.stats = stats
    pk.level = level
    pk.item = item
    pk.ability = ability
    return pk


class TestFactory:
    def test_random_format_dispatches_to_randbats_resolver(self):
        resolver = make_resolver("gen9randombattle", randbats_data=None)
        assert isinstance(resolver, RandbatsResolver)

    def test_non_random_format_dispatches_to_non_random_resolver(self):
        resolver = make_resolver("gen9customgame", randbats_data=None)
        assert isinstance(resolver, NonRandomResolver)

    def test_ou_format_dispatches_to_non_random_resolver(self):
        resolver = make_resolver("gen9ou", randbats_data=None)
        assert isinstance(resolver, NonRandomResolver)

    @pytest.mark.parametrize(
        "fmt,expected",
        [
            ("gen9randombattle", True),
            ("Gen9RandomBattle", True),
            ("gen8randombattle", True),
            ("gen9ou", False),
            ("gen9customgame", False),
            ("gen9vgc2024regh", False),
        ],
    )
    def test_is_random_format(self, fmt, expected):
        assert is_random_format(fmt) is expected


class TestNonRandomResolverOwnSide:
    def test_trusts_server_stats_for_own_pokemon(self):
        resolver = make_resolver("gen9customgame", randbats_data=None)
        pk = _mock_pokemon(
            "pikachu",
            stats={"hp": 211, "atk": 132, "def": 116, "spa": 199, "spd": 136, "spe": 306},
            item="lightball",
            ability="static",
        )
        spread = resolver.get_spread(pk, is_opponent=False)
        assert spread.stats == pk.stats
        assert spread.stats_are_exact is True
        assert spread.item == "lightball"

    def test_falls_back_to_curated_when_own_stats_missing(self):
        resolver = make_resolver("gen9customgame", randbats_data=None)
        pk = _mock_pokemon("pikachu", stats=None)
        spread = resolver.get_spread(pk, is_opponent=False)
        assert spread.stats_are_exact is False
        assert spread.stats.get("spa", 0) > 0  # came from curated spread


class TestNonRandomResolverOpponentSide:
    def test_returns_curated_spread_for_known_species(self):
        resolver = make_resolver("gen9customgame", randbats_data=None)
        pk = _mock_pokemon("pikachu", stats=None)
        spread = resolver.get_spread(pk, is_opponent=True)
        assert spread.item == "lightball"
        assert spread.nature == "timid"
        # 252 SpA EVs + Timid nature on base 50 SpA Pikachu at L100 = 199
        assert spread.stats["spa"] == 199
        # 252 Spe EVs + Timid (+10%) on base 90 Spe Pikachu at L100 = 306
        assert spread.stats["spe"] == 306

    def test_falls_back_to_role_based_for_uncovered_species(self):
        resolver = make_resolver("gen9customgame", randbats_data=None)
        pk = _mock_pokemon("tinkaton", stats=None)
        spread = resolver.get_spread(pk, is_opponent=True)
        # Role-based heuristic: 252 in two highest base stats, 4 in third
        assert sum(spread.evs.values()) == 508
        assert max(spread.evs.values()) == 252

    def test_curated_spread_lists_full_move_pool(self):
        resolver = make_resolver("gen9customgame", randbats_data=None)
        pk = _mock_pokemon("garchomp", stats=None)
        spread = resolver.get_spread(pk, is_opponent=True)
        # Union across the two garchomp spreads in the JSON
        assert "earthquake" in spread.possible_moves
        assert "swordsdance" in spread.possible_moves  # only in SD spread
        assert "outrage" in spread.possible_moves  # only in Scarf spread


class TestRandbatsResolver:
    def test_uses_randbats_data_when_available(self):
        fake_randbats = MagicMock()
        fake_randbats.get_evs.return_value = {
            "hp": 84, "atk": 84, "def": 84, "spa": 84, "spd": 84, "spe": 84,
        }
        fake_randbats.get_ivs.return_value = {
            "hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31,
        }
        fake_randbats.get_level.return_value = 79
        fake_randbats.get_possible_moves.return_value = {"earthquake", "dragonclaw"}
        fake_randbats.get_possible_items.return_value = ["lifeorb", "choicescarf"]
        fake_randbats.get_possible_abilities.return_value = ["roughskin"]
        fake_randbats.get_pokemon.return_value = MagicMock(roles={})

        resolver = make_resolver("gen9randombattle", randbats_data=fake_randbats)
        pk = _mock_pokemon("garchomp", stats=None, level=79)
        spread = resolver.get_spread(pk, is_opponent=True)

        assert spread.level == 79
        assert spread.evs == {
            "hp": 84, "atk": 84, "def": 84, "spa": 84, "spd": 84, "spe": 84,
        }
        assert "earthquake" in spread.possible_moves
        assert "lifeorb" in spread.possible_items

    def test_handles_missing_randbats_data_gracefully(self):
        resolver = make_resolver("gen9randombattle", randbats_data=None)
        pk = _mock_pokemon("garchomp", stats=None)
        spread = resolver.get_spread(pk, is_opponent=True)
        # Falls back to default 84/31 spread
        assert all(ev == 84 for ev in spread.evs.values())
        assert spread.possible_moves == frozenset()


class TestSpread:
    def test_spread_carries_provenance(self):
        spread = Spread(
            level=100,
            stats={"hp": 100},
            evs={"hp": 252},
            nature="adamant",
        )
        assert spread.level == 100
        assert spread.evs["hp"] == 252
        assert spread.nature == "adamant"
        assert spread.stats_are_exact is False


class TestCuratedFile:
    def test_seed_species_are_loadable(self):
        db = load_common_spreads()
        assert db.lookup_all("pikachu")
        assert db.lookup_all("snorlax")
        assert db.lookup_all("garchomp")
        assert db.lookup_all("nonexistentspecies") == ()
