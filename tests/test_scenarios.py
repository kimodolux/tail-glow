"""Pytest entry for scenario-based agent evaluation.

Each YAML file in `tests/scenarios/fixtures/` becomes one parametrized test.
Skipped by default in fast runs:

    pytest -m "not scenario"          # skip scenarios (CI default)
    pytest -m scenario                # run only scenarios
    pytest tests/test_scenarios.py    # run all scenarios explicitly

Requires the local Showdown container to be running (docker compose up -d).
"""

import pytest

from tests.scenarios.runner import ScenarioRunner
from tests.scenarios.scenario import Scenario, load_all_scenarios

_SCENARIOS: list[Scenario] = load_all_scenarios()


@pytest.mark.scenario
@pytest.mark.parametrize(
    "scenario",
    _SCENARIOS,
    ids=[s.name for s in _SCENARIOS] or None,
)
async def test_scenario(scenario: Scenario):
    if not _SCENARIOS:
        pytest.skip("no scenario fixtures found")
    result = await ScenarioRunner().run(scenario)
    assert result.passed, result.message
