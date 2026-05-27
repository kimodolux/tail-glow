"""TailGlowPlayer subclass that records the agent's decision on every turn."""

from dataclasses import dataclass

from src.showdown.client import TailGlowPlayer
from src.stats import StatsResolver


@dataclass
class DecisionRecord:
    turn: int
    action_type: str | None
    action_target: str | None
    reasoning: str | None


class RecordingPlayer(TailGlowPlayer):
    """Wraps TailGlowPlayer to capture each turn's decision for grading.

    `stats_resolver_override`, if provided, is injected into AgentState so the
    agent uses scenario-specific opponent priors (curated spreads + nature
    + item) instead of the global smogon-common.json defaults.
    """

    def __init__(self, *args, stats_resolver_override: StatsResolver | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.captured_decisions: list[DecisionRecord] = []
        self._stats_resolver_override = stats_resolver_override

    def _build_battle_state(self, battle, formatted_state: str) -> dict:
        state = super()._build_battle_state(battle, formatted_state)
        if self._stats_resolver_override is not None:
            state["stats_resolver_override"] = self._stats_resolver_override
        return state

    def _battle_finished_callback(self, battle):
        # Skip game-end analysis: scenarios shouldn't pay the extra LLM call
        # or mutate the shared strategy store between runs.
        self.battles_played += 1
        if battle.won:
            self.battles_won += 1
        self.battle_context.pop(battle.battle_tag, None)

    async def choose_move(self, battle):
        order = await super().choose_move(battle)

        ctx = self.battle_context.get(battle.battle_tag, {})
        reasoning = ctx.get("turn_reasoning", {}).get(battle.turn)

        # Walk back through battle_context to recover action_type/target. The
        # parent stores reasoning but not action_type/target, so we infer from
        # the BattleOrder we're about to return.
        action_type, action_target = _infer_action(order)

        self.captured_decisions.append(
            DecisionRecord(
                turn=battle.turn,
                action_type=action_type,
                action_target=action_target,
                reasoning=reasoning,
            )
        )
        return order


def _infer_action(order) -> tuple[str | None, str | None]:
    """Read action_type / action_target back off a poke-env BattleOrder."""
    if order is None or getattr(order, "order", None) is None:
        return None, None
    target = order.order
    # poke-env: Move has .id, Pokemon has .species
    if hasattr(target, "id"):
        return "move", target.id
    if hasattr(target, "species"):
        return "switch", target.species
    return None, None
