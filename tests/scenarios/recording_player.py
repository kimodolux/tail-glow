"""TailGlowPlayer subclass that records the agent's decision on every turn."""

import asyncio
from dataclasses import dataclass
from typing import Any

from src.showdown.client import TailGlowPlayer


@dataclass
class DecisionRecord:
    turn: int
    action_type: str | None
    action_target: str | None
    reasoning: str | None


class RecordingPlayer(TailGlowPlayer):
    """Wraps TailGlowPlayer to capture each turn's decision for grading.

    Runs the real battle graph unchanged, then records the action actually
    played (read back off the poke-env BattleOrder, so name-resolution and
    fallbacks are reflected) plus the LLM's reasoning for the failure message.

    `stats_resolver_override`, if provided, is injected into the graph state so
    the agent uses scenario-specific opponent priors. The state schema does not
    carry that field yet on this branch, so the override is only injected when
    present; it wires up automatically once the stats feature lands.
    """

    def __init__(
        self,
        *args,
        stats_resolver_override: Any | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.captured_decisions: list[DecisionRecord] = []
        self._stats_resolver_override = stats_resolver_override

    def _build_initial_state(self, battle) -> dict:
        state = super()._build_initial_state(battle)
        if self._stats_resolver_override is not None:
            state["stats_resolver_override"] = self._stats_resolver_override
        return state

    async def choose_move(self, battle):
        # Mirror the base client's invoke/execute so we can capture the graph
        # result alongside the order, without paying a second LLM call.
        initial_state = self._build_initial_state(battle)
        result = await asyncio.to_thread(self.battle_graph.invoke, initial_state)
        order = self._execute_action(battle, result)

        action_type, action_target = _infer_action(order)
        self.captured_decisions.append(
            DecisionRecord(
                turn=battle.turn,
                action_type=action_type,
                action_target=action_target,
                reasoning=result.get("reasoning"),
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
