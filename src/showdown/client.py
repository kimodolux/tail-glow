"""Pokemon Showdown client using poke-env."""

import asyncio
import logging
import uuid

from poke_env import Player, AccountConfiguration, ServerConfiguration, ShowdownServerConfiguration

from src.config import Config
from src.agent import create_agent
from .formatter import format_battle_state

logger = logging.getLogger(__name__)


class TailGlowPlayer(Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.battle_graph = create_agent()

        # Quiet the poke-env logger for this player (uses username as logger name)
        logging.getLogger(self.username).setLevel(logging.WARNING)

    async def choose_move(self, battle):
        """Called by poke-env when it's our turn."""
        formatted_state = format_battle_state(battle)
        logger.debug(f"Formatted state:\n{formatted_state}")

        initial_state = {
            "username": self.username,
            "battle_tag": battle.battle_tag,
            "battle_object": battle,
            "turn": battle.turn,
            "formatted_state": formatted_state,
            "llm_response": "",
            "reasoning": None,
            "action_type": None,
            "action_target": None,
            "error": None,
            "trace_id": str(uuid.uuid4()),
        }

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
                target_clean = action_target.replace("-", "").replace(" ", "")
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
            target_clean = action_target.replace("-", "").replace(" ", "")
            for move in battle.available_moves:
                move_id_clean = move.id.replace("-", "").replace(" ", "")
                if target_clean in move_id_clean or move_id_clean in target_clean:
                    logger.info(f"Using move {move.id}")
                    return self.create_order(move)

            # Try partial match
            for move in battle.available_moves:
                if action_target.split()[0] in move.id.lower():
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


async def run_battles(n_battles: int = 1):
    """Run N battles using the agent."""

    # Use ShowdownServerConfiguration for official server, or custom for local
    if "psim.us" in Config.SHOWDOWN_SERVER:
        server_config = ShowdownServerConfiguration
    else:
        # Local server: construct websocket URL
        server_parts = Config.SHOWDOWN_SERVER.split(":")
        server_host = server_parts[0]
        server_port = server_parts[1] if len(server_parts) > 1 else "8000"
        ws_url = f"ws://{server_host}:{server_port}/showdown/websocket"
        server_config = ServerConfiguration(ws_url, "")

    player = TailGlowPlayer(
        account_configuration=AccountConfiguration(
            Config.SHOWDOWN_USERNAME, Config.SHOWDOWN_PASSWORD or None
        ),
        server_configuration=server_config,
        battle_format=Config.BATTLE_FORMAT,
        max_concurrent_battles=1,
    )

    logger.info(f"Starting {n_battles} battle(s) as {Config.SHOWDOWN_USERNAME}...")
    logger.info(f"Server: {Config.SHOWDOWN_SERVER}")
    logger.info(f"Format: {Config.BATTLE_FORMAT}")

    await player.ladder(n_battles)

    logger.info("=" * 50)
    logger.info("Final Stats:")
    logger.info(f"  Battles: {player.n_finished_battles}")
    logger.info(f"  Wins: {player.n_won_battles}")
    logger.info(f"  Win Rate: {player.win_rate * 100:.1f}%")
    logger.info("=" * 50)

    return player
