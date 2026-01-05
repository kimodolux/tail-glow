"""Pokemon Showdown client using poke-env."""

import logging

from poke_env import Player, AccountConfiguration, ServerConfiguration, ShowdownServerConfiguration

from src.config import Config
from src.agent import create_agent
from src.agent.graph import create_team_analysis_graph, create_battle_graph
from src.data import get_randbats_data, init_randbats_data
from .formatter import format_battle_state

logger = logging.getLogger(__name__)


class TailGlowPlayer(Player):
    """
    Custom poke-env player using LangGraph agent.

    Architecture:
    - Turn 1: Run team analysis graph (LLM Call #1) to catalog team roles
    - Every turn: Run battle graph with parallel info gathering + 2 LLM calls
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Create both graphs
        self.team_analysis_graph = create_team_analysis_graph()
        self.battle_graph = create_battle_graph()
        # Legacy single graph for backward compat
        self.agent = create_agent()

        # Battle context storage (persists team analysis across turns)
        self.battle_context: dict[str, dict] = {}

        # Stats
        self.battles_played = 0
        self.battles_won = 0

        # Randbats data initialization flag
        self._randbats_initialized = False

        # Quiet the poke-env logger for this player (uses username as logger name)
        logging.getLogger(self.username).setLevel(logging.WARNING)

    async def choose_move(self, battle):
        """
        Called by poke-env when it's our turn.

        Flow:
        1. Turn 1: Run team analysis (LLM Call #1)
        2. Every turn: Run battle graph with parallel nodes + LLM Calls #2 & #3
        3. Send reasoning as chat message
        4. Execute decided action
        """
        # Initialize randbats data on first use (lazy loading)
        if not self._randbats_initialized:
            self._randbats_initialized = True
            if not get_randbats_data():
                logger.info("Initializing randbats data...")
                await init_randbats_data(Config.BATTLE_FORMAT)

        # Initialize battle context if this is a new battle
        if battle.battle_tag not in self.battle_context:
            self.battle_context[battle.battle_tag] = {
                "team_analysis": None,
            }

        # Turn 1: Run team analysis first
        if battle.turn == 1:
            await self._run_team_analysis(battle)

        # Format state
        formatted_state = format_battle_state(battle)
        logger.debug(f"Formatted state:\n{formatted_state}")

        # Build initial state with all new fields
        initial_state = self._build_battle_state(battle, formatted_state)

        # Run main battle graph
        result = self.battle_graph.invoke(initial_state)

        # Send reasoning as chat message before executing move
        await self._send_reasoning_chat(battle, result)

        # Execute action
        return self._execute_action(battle, result)

    async def _run_team_analysis(self, battle):
        """Run team analysis graph on turn 1."""
        logger.info(f"Running team analysis for battle {battle.battle_tag}")

        # Build minimal state for team analysis
        analysis_state = {
            "username": self.username,
            "battle_tag": battle.battle_tag,
            "battle_object": battle,
            "turn": battle.turn,
            "formatted_state": "",
            "tool_results": {},
            "llm_response": "",
            "reasoning": None,
            "action_type": None,
            "action_target": None,
            "error": None,
            "team_analysis": None,
            "opponent_sets": {},
            "damage_calculations": None,
            "damage_calc_raw": None,
            "speed_analysis": None,
            "speed_calc_raw": None,
            "type_matchups": None,
            "effects_analysis": None,
            "strategy_context": None,
        }

        try:
            result = self.team_analysis_graph.invoke(analysis_state)
            team_analysis = result.get("team_analysis")

            if team_analysis:
                self.battle_context[battle.battle_tag]["team_analysis"] = team_analysis
                logger.info("Team analysis completed successfully")
                logger.debug(f"Team analysis:\n{team_analysis}")
            else:
                logger.warning("Team analysis returned empty result")

        except Exception as e:
            logger.error(f"Team analysis failed: {e}", exc_info=True)

    def _build_battle_state(self, battle, formatted_state: str) -> dict:
        """Build the complete battle state dictionary."""
        # Get persisted team analysis
        team_analysis = self.battle_context.get(battle.battle_tag, {}).get("team_analysis")

        return {
            # Player context
            "username": self.username,
            # Core battle info
            "battle_tag": battle.battle_tag,
            "battle_object": battle,
            "turn": battle.turn,
            "formatted_state": formatted_state,
            "tool_results": {},
            "llm_response": "",
            "reasoning": None,
            "action_type": None,
            "action_target": None,
            "error": None,
            # Team analysis (from turn 1)
            "team_analysis": team_analysis,
            # Parallel node outputs (will be populated by graph)
            "opponent_sets": {},
            "damage_calculations": None,
            "damage_calc_raw": None,
            "speed_analysis": None,
            "speed_calc_raw": None,
            "type_matchups": None,
            "effects_analysis": None,
            "strategy_context": None,
        }

    async def _send_reasoning_chat(self, battle, result):
        """Send AI reasoning as a chat message in the battle room."""
        reasoning = result.get("reasoning")

        if reasoning:
            try:
                # Format message with turn context
                chat_message = f"[T{battle.turn}] {reasoning}"
                await self.ps_client.send_message(chat_message, battle.battle_tag)
                logger.debug(f"Sent reasoning chat: {chat_message}")
            except Exception as e:
                # Don't fail the move if chat fails
                logger.warning(f"Failed to send reasoning chat: {e}")
        else:
            logger.debug("No reasoning to send")

    def _execute_action(self, battle, result):
        """Execute the decided action."""

        if result["error"]:
            logger.warning(f"Agent error: {result['error']}")

        action_type = result["action_type"]
        action_target = result["action_target"]

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
        """Team preview - MVP just picks default order."""
        return "/team 123456"

    def _battle_finished_callback(self, battle):
        """Track win rate when battle ends."""
        self.battles_played += 1
        won = battle.won

        if won:
            self.battles_won += 1

        win_rate = self.battles_won / self.battles_played * 100
        result = "WON" if won else "LOST"
        logger.info(
            f"Battle {battle.battle_tag} ended: {result} "
            f"(Record: {self.battles_won}/{self.battles_played}, Win rate: {win_rate:.1f}%)"
        )

        # Clean up battle context
        if battle.battle_tag in self.battle_context:
            del self.battle_context[battle.battle_tag]


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

    # Create player
    player = TailGlowPlayer(
        account_configuration=AccountConfiguration(
            Config.SHOWDOWN_USERNAME, Config.SHOWDOWN_PASSWORD or None
        ),
        server_configuration=server_config,
        battle_format=Config.BATTLE_FORMAT,
        max_concurrent_battles=1,
    )

    # Play battles on ladder
    logger.info(f"Starting {n_battles} battle(s) as {Config.SHOWDOWN_USERNAME}...")
    logger.info(f"Server: {Config.SHOWDOWN_SERVER}")
    logger.info(f"Format: {Config.BATTLE_FORMAT}")

    await player.ladder(n_battles)

    # Print final stats
    logger.info("=" * 50)
    logger.info("Final Stats:")
    logger.info(f"  Battles: {player.battles_played}")
    logger.info(f"  Wins: {player.battles_won}")
    win_rate = player.battles_won / max(player.battles_played, 1) * 100
    logger.info(f"  Win Rate: {win_rate:.1f}%")
    logger.info("=" * 50)

    return player
