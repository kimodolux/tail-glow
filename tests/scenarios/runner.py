"""Orchestrate one scenario end-to-end on the local Showdown server."""

import logging
import uuid

from poke_env import AccountConfiguration, LocalhostServerConfiguration
from poke_env.data import GenData

from src.stats import NonRandomResolver, StatsResolver, load_common_spreads

from .graders import GradeResult, make_grader
from .recording_player import RecordingPlayer
from .scenario import Scenario
from .scripted_player import ScriptedPlayer
from .teams import build_team

logger = logging.getLogger(__name__)

DEFAULT_FORMAT = "gen9customgame"
DEFAULT_GEN = 9


class ScenarioRunner:
    """Run a single scenario and return a graded result."""

    def __init__(self, battle_format: str = DEFAULT_FORMAT):
        self.battle_format = battle_format

    async def run(self, scenario: Scenario) -> GradeResult:
        # Unique usernames per run so re-running doesn't collide on the server
        run_id = uuid.uuid4().hex[:6]
        player_name = f"tg-agent-{run_id}"
        opponent_name = f"tg-script-{run_id}"

        resolver_override = _build_resolver_override(scenario)

        agent = RecordingPlayer(
            account_configuration=AccountConfiguration(player_name, None),
            server_configuration=LocalhostServerConfiguration,
            battle_format=self.battle_format,
            team=build_team(scenario.player_team),
            max_concurrent_battles=1,
            start_timer_on_battle_start=False,
            stats_resolver_override=resolver_override,
        )

        opponent = ScriptedPlayer(
            account_configuration=AccountConfiguration(opponent_name, None),
            server_configuration=LocalhostServerConfiguration,
            battle_format=self.battle_format,
            team=build_team(scenario.opponent_team),
            script=scenario.opponent_script,
            max_concurrent_battles=1,
            start_timer_on_battle_start=False,
        )

        await agent.battle_against(opponent, n_battles=1)

        battle_won = _extract_battle_won(agent)

        grader = make_grader(scenario.evaluation)
        return grader.evaluate(agent.captured_decisions, battle_won=battle_won)


def _extract_battle_won(player) -> bool | None:
    """Pull win/loss from the only battle the player just played."""
    battles = getattr(player, "_battles", None) or {}
    if len(battles) != 1:
        return None
    (battle,) = battles.values()
    return getattr(battle, "won", None)


def _build_resolver_override(scenario: Scenario) -> StatsResolver | None:
    """Build a NonRandomResolver with scenario-specific opponent spreads merged
    on top of the global smogon-common.json. Returns None when the scenario
    has no overrides (the default global resolver is used).
    """
    if not scenario.opponent_spreads:
        return None
    common_db = load_common_spreads().with_overrides(scenario.opponent_spreads)
    return NonRandomResolver(common_db, GenData.from_gen(DEFAULT_GEN))
