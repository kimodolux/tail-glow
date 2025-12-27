"""Run two TailGlow bots against each other on a local server."""

import asyncio
import argparse
import logging

from poke_env import AccountConfiguration, LocalhostServerConfiguration

from src.showdown.client import TailGlowPlayer
from src.config import Config


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


async def run_local_battles(n_battles: int = 10):
    """Run n battles between two TailGlow bots on localhost."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info(f"Starting {n_battles} local battle(s)...")
    logger.info(f"Format: {Config.BATTLE_FORMAT}")

    # Create two players with different usernames
    player1 = TailGlowPlayer(
        account_configuration=AccountConfiguration("TailGlow1", None),
        server_configuration=LocalhostServerConfiguration,
        battle_format=Config.BATTLE_FORMAT,
    )

    player2 = TailGlowPlayer(
        account_configuration=AccountConfiguration("TailGlow2", None),
        server_configuration=LocalhostServerConfiguration,
        battle_format=Config.BATTLE_FORMAT,
    )

    # Battle against each other
    await player1.battle_against(player2, n_battles=n_battles)

    # Print results
    logger.info("=" * 50)
    logger.info("Final Results:")
    logger.info(f"  TailGlow1: {player1.n_won_battles} wins")
    logger.info(f"  TailGlow2: {player2.n_won_battles} wins")
    logger.info("=" * 50)

    return player1, player2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run local bot vs bot battles")
    parser.add_argument(
        "-n", "--battles", type=int, default=10, help="Number of battles (default: 10)"
    )
    args = parser.parse_args()

    asyncio.run(run_local_battles(n_battles=args.battles))
