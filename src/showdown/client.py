"""Pokemon Showdown client using poke-env."""

import asyncio
import logging
import uuid

from poke_env import (
    Player,
    RandomPlayer,
    MaxBasePowerPlayer,
    SimpleHeuristicsPlayer,
    AccountConfiguration,
    ServerConfiguration,
    ShowdownServerConfiguration,
)

from langgraph.graph.state import CompiledStateGraph

from src.config import Config
from src.agent import create_agent

logger = logging.getLogger(__name__)


class TailGlowPlayer(Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.battle_graph: CompiledStateGraph = create_agent()

        # Quiet the poke-env logger for this player (uses username as logger name)
        logging.getLogger(self.username).setLevel(logging.WARNING)

    def _build_initial_state(self, battle) -> dict:
        """Construct the graph's initial state for this turn.

        Factored out of `choose_move` so subclasses (e.g. the scenario
        RecordingPlayer) can run the graph and capture its result without
        duplicating the state-construction logic.
        """
        return {
            "username": self.username,
            "battle_tag": battle.battle_tag,
            "battle_object": battle,
            "turn": battle.turn,
            "formatted_state": "",
            "reasoning": None,
            "action_type": None,
            "action_target": None,
            "error": None,
            "trace_id": str(uuid.uuid4()),
        }

    async def choose_move(self, battle):
        """Called by poke-env when it's our turn."""
        initial_state = self._build_initial_state(battle)

        result = await asyncio.to_thread(self.battle_graph.invoke, initial_state)

        return self._execute_action(battle, result)

    def _execute_action(self, battle, result):
        """Execute the decided action."""
        if result.get("error"):
            logger.warning(f"Agent error: {result['error']}")

        action_type = result.get("action_type")
        action_target = result.get("action_target")

        logger.info(f"Turn {battle.turn}: {action_type} -> {action_target}")

        if action_type == "switch" and action_target:
            # Find matching Pokemon in available switches
            for pokemon in battle.available_switches:
                species_lower = pokemon.species.lower().replace("-", "")
                target_clean = action_target.lower().replace("-", "").replace(" ", "")
                if target_clean in species_lower or species_lower in target_clean:
                    logger.info(f"Switching to {pokemon.species}")
                    return self.create_order(pokemon)

            # Fallback: switch to first available
            if battle.available_switches:
                logger.warning(
                    f"Could not find switch target '{action_target}', using first available"
                )
                return self.create_order(battle.available_switches[0])

        # Default: use a move
        if action_target and battle.available_moves:
            target_clean = action_target.lower().replace("-", "").replace(" ", "")
            for move in battle.available_moves:
                move_id_clean = move.id.replace("-", "").replace(" ", "")
                if target_clean in move_id_clean or move_id_clean in target_clean:
                    logger.info(f"Using move {move.id}")
                    return self.create_order(move)

            # Try partial match
            for move in battle.available_moves:
                if action_target.lower().split()[0] in move.id.lower():
                    logger.info(f"Using move {move.id} (partial match)")
                    return self.create_order(move)

        # Fallback: use first available move
        if battle.available_moves:
            logger.warning(f"Could not find move '{action_target}', using first available")
            return self.create_order(battle.available_moves[0])

        # Last resort: switch if we can't move
        if battle.available_switches:
            logger.warning("No moves available, switching")
            return self.create_order(battle.available_switches[0])

        # Absolute last resort: random
        logger.warning("Using random move as last resort")
        return self.choose_random_move(battle)

    def teampreview(self, battle):
        """Team preview - just pick default order."""
        return "/team 123456"

    def _battle_finished_callback(self, battle):
        """Log the result when a battle ends."""
        result = "WON" if battle.won else "LOST"
        logger.info(
            f"Battle {battle.battle_tag} ended: {result} "
            f"(Record: {self.n_won_battles}/{self.n_finished_battles}, "
            f"Win rate: {self.win_rate * 100:.1f}%)"
        )


# poke-env baseline bots available as opponents in "bot" mode.
OPPONENT_BOTS = {
    "random": RandomPlayer,
    "maxpower": MaxBasePowerPlayer,
    "heuristic": SimpleHeuristicsPlayer,
}


def _build_server_config():
    """Resolve the poke-env server configuration from Config."""
    # Use ShowdownServerConfiguration for official server, or custom for local
    if "psim.us" in Config.SHOWDOWN_SERVER:
        return ShowdownServerConfiguration

    # Local server: construct websocket URL
    server_parts = Config.SHOWDOWN_SERVER.split(":")
    server_host = server_parts[0]
    server_port = server_parts[1] if len(server_parts) > 1 else "8000"
    ws_url = f"ws://{server_host}:{server_port}/showdown/websocket"
    return ServerConfiguration(ws_url, "")


def _make_tail_glow_player(username: str, password: str | None, server_config):
    """Create a TailGlowPlayer with the given account."""
    return TailGlowPlayer(
        account_configuration=AccountConfiguration(username, password or None),
        server_configuration=server_config,
        battle_format=Config.BATTLE_FORMAT,
        max_concurrent_battles=1,
    )


def _log_stats(player: Player, label: str):
    """Log final win/loss stats for a player."""
    logger.info("=" * 50)
    logger.info(f"Final Stats ({label}):")
    logger.info(f"  Battles: {player.n_finished_battles}")
    logger.info(f"  Wins: {player.n_won_battles}")
    logger.info(f"  Win Rate: {player.win_rate * 100:.1f}%")
    logger.info("=" * 50)


async def run_battles(
    n_battles: int = 1,
    mode: str = "ladder",
    opponent: str = "random",
):
    """Run N battles using the agent.

    Modes:
      - "ladder":   one bot queues on the ladder against server opponents.
      - "selfplay": two TailGlow bots battle each other.
      - "bot":      one TailGlow bot battles a poke-env baseline bot.
    """
    if mode not in ("ladder", "selfplay", "bot"):
        raise ValueError(f"Invalid mode '{mode}'. Choose from ladder, selfplay, bot")
    if mode == "bot" and opponent not in OPPONENT_BOTS:
        raise ValueError(f"Invalid opponent '{opponent}'. Choose from {list(OPPONENT_BOTS)}")

    server_config = _build_server_config()

    logger.info(f"Starting {n_battles} battle(s) in '{mode}' mode...")
    logger.info(f"Server: {Config.SHOWDOWN_SERVER}")
    logger.info(f"Format: {Config.BATTLE_FORMAT}")

    player = _make_tail_glow_player(
        Config.SHOWDOWN_USERNAME, Config.SHOWDOWN_PASSWORD, server_config
    )

    match mode:
        case "ladder":
            logger.info(f"Laddering as {player.username}...")
            await player.ladder(n_battles)
            _log_stats(player, "ladder")
            return player
        case "selfplay":
            opponent_player = _make_tail_glow_player(
                f"{Config.SHOWDOWN_USERNAME} B", Config.SHOWDOWN_PASSWORD, server_config
            )
        case "bot":
            opponent_player = OPPONENT_BOTS[opponent](
                account_configuration=AccountConfiguration(f"PokeEnv {opponent}", None),
                server_configuration=server_config,
                battle_format=Config.BATTLE_FORMAT,
                max_concurrent_battles=1,
            )

    logger.info(f"{player.username} vs {opponent_player.username}...")
    await player.battle_against(opponent_player, n_battles=n_battles)
    _log_stats(player, player.username)
    if mode == "selfplay":
        _log_stats(opponent_player, opponent_player.username)
    return player
