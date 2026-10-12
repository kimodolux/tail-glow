"""Tests for the mechanical opponent-belief system."""

import logging

import pytest
from poke_env.battle import Battle, Move, PokemonType
from poke_env.data import GenData

from src.agent.belief import (
    BattleBelief,
    DamageObservation,
    Hypothesis,
    RandbatsPriorProvider,
    apply_locks,
    apply_observation,
    extract_damage_observations,
    get_provider,
    init_mon,
    normalized,
    summarize,
)
from src.agent.nodes.resolve_opponent import resolve_opponent_node

GEN9 = GenData.from_gen(9)


# --------------------------------------------------------------------------- #
# Prior provider / loader
# --------------------------------------------------------------------------- #


class TestRandbatsPriorProvider:
    def test_known_species_enumerates_role_ability_item(self):
        # Garchomp: 2 roles, 1 ability each, 1 item each -> 2 hypotheses.
        h = RandbatsPriorProvider().hypotheses("garchomp", 74, GEN9)
        assert len(h) == 2
        assert {c.label for c in h} == {"Fast Support", "Setup Sweeper"}
        assert all(c.weight == 1.0 for c in h)

    def test_ev_iv_override_lowers_stat(self):
        # Serperior's Fast Attacker role zeroes Atk EV/IV.
        h = RandbatsPriorProvider().hypotheses("serperior", 79, GEN9)
        fast = next(c for c in h if c.label == "Fast Attacker")
        tera = next(c for c in h if c.label == "Tera Blast user")
        assert fast.stats["atk"] < tera.stats["atk"]  # override took effect

    def test_move_pool_and_tera_populated(self):
        h = RandbatsPriorProvider().hypotheses("garchomp", 74, GEN9)
        sweeper = next(c for c in h if c.label == "Setup Sweeper")
        assert "swordsdance" in sweeper.move_pool
        assert PokemonType.FIRE in sweeper.tera_types

    def test_unknown_species_returns_empty(self):
        assert RandbatsPriorProvider().hypotheses("missingno", 100, GEN9) == []


class TestGetProvider:
    def test_randbattle_gets_randbats_provider(self):
        assert isinstance(get_provider("gen9randombattle"), RandbatsPriorProvider)

    def test_ou_gets_none_for_now(self):
        assert get_provider("gen9ou") is None

    def test_missing_format_gets_none(self):
        assert get_provider(None) is None


# --------------------------------------------------------------------------- #
# Locks
# --------------------------------------------------------------------------- #


class TestApplyLocks:
    def test_revealed_move_eliminates_roles_without_it(self):
        belief = init_mon("garchomp", 74, GEN9, RandbatsPriorProvider())
        # Swords Dance is only in the Setup Sweeper role.
        apply_locks(belief, {"swordsdance"}, None, None, None)
        alive = belief.alive()
        assert len(alive) == 1
        assert alive[0].label == "Setup Sweeper"

    def test_revealed_item_filters(self):
        belief = init_mon("garchomp", 74, GEN9, RandbatsPriorProvider())
        apply_locks(belief, set(), None, "rockyhelmet", None)
        assert all(h.item == "rockyhelmet" for h in belief.alive())

    def test_unknown_move_eliminates_everything(self):
        belief = init_mon("garchomp", 74, GEN9, RandbatsPriorProvider())
        apply_locks(belief, {"hyperbeam"}, None, None, None)  # not in any pool
        assert belief.alive() == []


# --------------------------------------------------------------------------- #
# Roll inversion
# --------------------------------------------------------------------------- #


def _attack_battle() -> Battle:
    """Battle where opponent Garchomp is active and can hit our Dragonite."""
    battle = Battle("battle-gen9randombattle-x", "me", logging.getLogger("t"), gen=9)
    battle._format = "gen9randombattle"
    req = {
        "side": {"name": "me", "id": "p1", "pokemon": [
            {"ident": "p1: Dragonite", "details": "Dragonite, L74, M", "condition": "300/300",
             "active": True, "stats": {"atk": 200, "def": 180, "spa": 170, "spd": 180, "spe": 160},
             "moves": ["earthquake"], "baseAbility": "multiscale", "item": "heavydutyboots",
             "pokeball": "pokeball"},
        ]},
        "rqid": 1,
    }
    battle.parse_request(req)
    # Both leads arrive via switch events in real logs; this seeds HP tracking.
    battle.parse_message(["", "switch", "p1a: Dragonite", "Dragonite, L74, M", "300/300"])
    battle.parse_message(["", "switch", "p2a: Garchomp", "Garchomp, L74, M", "100/100"])
    return battle


class TestRollInversion:
    def _two_item_hypotheses(self, battle):
        """Same stats, differing only by Choice Band vs no item."""
        base = RandbatsPriorProvider().hypotheses("garchomp", 74, GEN9)[0]
        no_item = Hypothesis("plain", 1.0, base.stats, "roughskin", None,
                             base.move_pool, base.tera_types)
        band = Hypothesis("band", 1.0, base.stats, "roughskin", "choiceband",
                          base.move_pool, base.tera_types)
        return no_item, band

    def test_observed_low_damage_downweights_choice_band(self):
        battle = _attack_battle()
        no_item, band = self._two_item_hypotheses(battle)
        belief = type("B", (), {})()  # simple holder with .alive()

        from src.agent.belief import MonBelief
        mb = MonBelief("garchomp", [no_item, band])

        # Compute the no-item damage range and feed its midpoint as observed.
        # Outrage (Dragon) actually damages Dragonite; Earthquake would be a
        # no-op (Flying-type ground immunity).
        from src.agent.belief import _apply_hypothesis
        from poke_env.calc import calculate_damage
        with _apply_hypothesis(battle.get_pokemon("p2: Garchomp"), no_item):
            lo, hi = calculate_damage("p2: Garchomp", "p1: Dragonite",
                                      Move("outrage", gen=9), battle)
        observed = (lo + hi) // 2

        obs = DamageObservation(1, "p2a: Garchomp", "p1a: Dragonite", "outrage", observed)
        apply_observation(mb, obs, battle)

        assert no_item.weight == 1.0            # consistent -> untouched
        assert band.weight < 1.0                # Choice Band overshoots -> penalised


# --------------------------------------------------------------------------- #
# Damage-observation extraction
# --------------------------------------------------------------------------- #


class TestExtractObservations:
    def test_extracts_move_damage_on_our_mon(self):
        battle = _attack_battle()
        # Simulate turn 1: opponent hits us for 60 (300 -> 240). poke-env commits
        # a turn's events only when the *next* turn message arrives.
        battle.parse_message(["", "turn", "1"])
        battle.parse_message(["", "move", "p2a: Garchomp", "Outrage", "p1a: Dragonite"])
        battle.parse_message(["", "-damage", "p1a: Dragonite", "240/300"])
        battle.parse_message(["", "turn", "2"])

        obs = extract_damage_observations(battle)
        assert len(obs) == 1
        assert obs[0].attacker_id == "p2: Garchomp"
        assert obs[0].defender_id == "p1: Dragonite"
        assert obs[0].move_id == "outrage"
        assert obs[0].damage == 60

    def test_ignores_item_chip_damage(self):
        battle = _attack_battle()
        battle.parse_message(["", "turn", "1"])
        # Life Orb recoil style event carries a [from] tag -> not a move hit.
        battle.parse_message(["", "-damage", "p1a: Dragonite", "270/300", "[from] item: Life Orb"])
        battle.parse_message(["", "turn", "2"])
        assert extract_damage_observations(battle) == []


# --------------------------------------------------------------------------- #
# Node integration
# --------------------------------------------------------------------------- #


class TestResolveOpponentNode:
    def test_initialises_and_narrows_from_reveals(self):
        battle = _attack_battle()
        belief = BattleBelief(format_id="gen9randombattle")
        state = {"battle_object": battle, "opponent_belief": belief}

        resolve_opponent_node(state)
        assert "garchomp" in belief.mons
        assert len(belief.mons["garchomp"].alive()) == 2

        # Reveal a Setup-Sweeper-only move; belief should collapse to one role.
        battle.parse_message(["", "move", "p2a: Garchomp", "Swords Dance", ""])
        resolve_opponent_node(state)
        assert len(belief.mons["garchomp"].alive()) == 1
        assert state["opponent_summary"] is not None

    def test_non_randbats_format_uses_neutral_fallback(self):
        battle = _attack_battle()
        belief = BattleBelief(format_id="gen9ou")  # no randbats provider
        state = {"battle_object": battle, "opponent_belief": belief}
        resolve_opponent_node(state)
        # Still populated so damage_calc has opponent stats, but as one neutral set.
        assert list(belief.mons) == ["garchomp"]
        alive = belief.mons["garchomp"].alive()
        assert len(alive) == 1 and alive[0].label == "neutral"

    def test_processed_turns_guard_prevents_double_penalty(self):
        battle = _attack_battle()
        battle.parse_message(["", "turn", "1"])
        battle.parse_message(["", "move", "p2a: Garchomp", "Outrage", "p1a: Dragonite"])
        battle.parse_message(["", "-damage", "p1a: Dragonite", "240/300"])
        battle.parse_message(["", "turn", "2"])
        belief = BattleBelief(format_id="gen9randombattle")
        state = {"battle_object": battle, "opponent_belief": belief}

        resolve_opponent_node(state)
        weights_after_first = [h.weight for h in belief.mons["garchomp"].hypotheses]
        resolve_opponent_node(state)  # same turn again
        weights_after_second = [h.weight for h in belief.mons["garchomp"].hypotheses]
        assert weights_after_first == weights_after_second  # not re-penalised


class TestNeutralFallback:
    def test_neutral_hypothesis_has_stats_and_empty_pool(self):
        from src.agent.belief import neutral_hypothesis
        h = neutral_hypothesis("garchomp", 74, GEN9, ability="roughskin", item=None)
        assert h.label == "neutral"
        assert all(h.stats[s] > 0 for s in ("hp", "atk", "def", "spa", "spd", "spe"))
        assert h.move_pool == frozenset()  # unknown pool

    def test_neutral_hypothesis_survives_move_reveals(self):
        """An empty (unknown) move pool must never be eliminated by reveals."""
        from src.agent.belief import MonBelief, neutral_hypothesis, apply_locks
        belief = MonBelief("garchomp", [neutral_hypothesis("garchomp", 74, GEN9)])
        apply_locks(belief, {"earthquake", "outrage"}, None, None, None)
        assert len(belief.alive()) == 1


class TestReduce:
    def test_normalized_sums_to_one(self):
        belief = init_mon("garchomp", 74, GEN9, RandbatsPriorProvider())
        dist = normalized(belief)
        assert abs(sum(w for _, w in dist) - 1.0) < 1e-9

    def test_summarize_mentions_species(self):
        belief = init_mon("garchomp", 74, GEN9, RandbatsPriorProvider())
        assert "garchomp" in summarize(belief)
