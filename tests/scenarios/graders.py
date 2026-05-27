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


class MoveMatchGrader:
    """Pass if the agent's action_target on a specific turn matches expected.

    Config:
        turn: int               # turn to inspect (1-indexed)
        expected: list[str]     # canonical correct move id(s); any match passes
    """

    def __init__(self, config: dict[str, Any]):
        self.turn = int(config.get("turn", 1))
        expected = config["expected"]
        if isinstance(expected, str):
            raise ValueError(
                f"'expected' must be a list, got string {expected!r}. "
                f"Use [{expected!r}] for a single move."
            )
        if not expected:
            raise ValueError("'expected' must contain at least one move id")
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

        if record.action_type != "move":
            return GradeResult(
                passed=False,
                message=(
                    f"turn {self.turn}: expected a move, got "
                    f"{record.action_type}={record.action_target!r}"
                ),
            )

        target_norm = _normalize(record.action_target or "")
        expected_norm = {_normalize(m) for m in self.expected}
        if target_norm in expected_norm:
            return GradeResult(
                passed=True,
                message=f"turn {self.turn}: picked {record.action_target!r}",
            )

        return GradeResult(
            passed=False,
            message=(
                f"turn {self.turn}: agent picked {record.action_target!r}, "
                f"expected one of {self.expected}. "
                f"reasoning: {record.reasoning!r}"
            ),
        )


def make_grader(evaluation: dict[str, Any]) -> Grader:
    eval_type = evaluation.get("type")
    if eval_type == "move_match":
        return MoveMatchGrader(evaluation)
    raise ValueError(f"unknown evaluation type: {eval_type!r}")
