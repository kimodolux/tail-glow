"""TailGlowPlayer subclass that records the agent's decision on every turn."""

from dataclasses import dataclass

from src.showdown.client import TailGlowPlayer


@dataclass
class DecisionRecord:
    turn: int
    action_type: str | None
    action_target: str | None
    reasoning: str | None


class RecordingPlayer(TailGlowPlayer):
    """Wraps TailGlowPlayer to capture each turn's decision for grading."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.captured_decisions: list[DecisionRecord] = []

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
