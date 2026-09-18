"""Scenario definition + YAML loader."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@dataclass
class Scenario:
    name: str
    player_team: str
    opponent_team: str
    opponent_script: list[str] = field(default_factory=list)
    evaluation: dict[str, Any] = field(default_factory=dict)
    # Optional per-scenario opponent spread overrides. Same shape as the
    # `pokemon` section of src/data/smogon-common.json — entries here
    # replace any same-species entries from the global JSON for this
    # scenario only. Use when you want the agent's prior to match the
    # opponent's actual spread (e.g. to test reasoning given perfect intel).
    opponent_spreads: dict[str, Any] = field(default_factory=dict)
    source_path: Path | None = None

    @classmethod
    def from_yaml(cls, path: Path) -> "Scenario":
        data = yaml.safe_load(path.read_text())
        missing = {"name", "player_team", "opponent_team", "evaluation"} - data.keys()
        if missing:
            raise ValueError(f"{path}: missing required fields: {sorted(missing)}")
        return cls(
            name=data["name"],
            player_team=data["player_team"],
            opponent_team=data["opponent_team"],
            opponent_script=list(data.get("opponent_script", [])),
            evaluation=dict(data["evaluation"]),
            opponent_spreads=dict(data.get("opponent_spreads", {})),
            source_path=path,
        )


def load_all_scenarios(directory: Path | None = None) -> list[Scenario]:
    directory = directory or FIXTURES_DIR
    if not directory.exists():
        return []
    return [Scenario.from_yaml(p) for p in sorted(directory.glob("*.yaml"))]
