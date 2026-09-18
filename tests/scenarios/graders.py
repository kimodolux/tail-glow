"""Grade a scenario's captured decisions against its evaluation criteria."""

from dataclasses import dataclass
from typing import Any, Protocol

from .recording_player import DecisionRecord


@dataclass
class GradeResult:
    passed: bool
    message: str


def _normalize(name: str) -> str:
    return name.lower().replace("-", "").replace(" ", "").replace("'", "")


class Grader(Protocol):
    def evaluate(
        self,
        captures: list[DecisionRecord],
        battle_won: bool | None,
    ) -> GradeResult: ...


class ActionMatchGrader:
    """Pass if the agent's action on a specific turn matches the expected
    type and target.

    Config:
        turn: int               # turn to inspect (1-indexed)
        action_type: str        # "move" or "switch"
        expected: list[str]     # canonical correct move id(s) or species; any match passes
    """

    def __init__(self, config: dict[str, Any]):
        self.turn = int(config.get("turn", 1))
        self.action_type = config["action_type"]
        if self.action_type not in ("move", "switch"):
            raise ValueError(
                f"action_type must be 'move' or 'switch', got {self.action_type!r}"
            )
        expected = config["expected"]
        if isinstance(expected, str):
            noun = "move" if self.action_type == "move" else "species"
            raise ValueError(
                f"'expected' must be a list, got string {expected!r}. "
                f"Use [{expected!r}] for a single {noun}."
            )
        if not expected:
            noun = "move id" if self.action_type == "move" else "species"
            raise ValueError(f"'expected' must contain at least one {noun}")
        self.expected = list(expected)

    def evaluate(self, captures, battle_won=None) -> GradeResult:
        record = next((c for c in captures if c.turn == self.turn), None)
        if record is None:
            return GradeResult(
                passed=False,
                message=(
                    f"no decision captured for turn {self.turn} "
                    f"(captured turns: {[c.turn for c in captures]})"
                ),
            )

        if record.action_type != self.action_type:
            return GradeResult(
                passed=False,
                message=(
                    f"turn {self.turn}: expected a {self.action_type}, got "
                    f"{record.action_type}={record.action_target!r}"
                ),
            )

        target_norm = _normalize(record.action_target or "")
        expected_norm = {_normalize(m) for m in self.expected}
        if target_norm in expected_norm:
            return GradeResult(
                passed=True,
                message=f"turn {self.turn}: picked {self.action_type} {record.action_target!r}",
            )

        return GradeResult(
            passed=False,
            message=(
                f"turn {self.turn}: agent picked {self.action_type} "
                f"{record.action_target!r}, expected one of {self.expected}. "
                f"reasoning: {record.reasoning!r}"
            ),
        )


def make_grader(evaluation: dict[str, Any]) -> Grader:
    eval_type = evaluation.get("type")
    if eval_type == "move_match":
        return ActionMatchGrader({**evaluation, "action_type": "move"})
    if eval_type == "switch_match":
        return ActionMatchGrader({**evaluation, "action_type": "switch"})
    raise ValueError(f"unknown evaluation type: {eval_type!r}")
