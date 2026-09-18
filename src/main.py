"""Main entry point for Tail Glow Pokemon battle bot."""

import asyncio
import logging
import argparse

from src.config import Config
from src.showdown.client import run_battles


def setup_logging():
    """Configure logging based on config."""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Quiet noisy libraries
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("poke_env").setLevel(logging.WARNING)


async def main(n_battles: int = 10, mode: str = "ladder", opponent: str = "random"):
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Tail Glow...")

    # Set config from environment
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        SystemExit(1)

    # Run battles
    await run_battles(n_battles=n_battles, mode=mode, opponent=opponent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tail Glow Pokemon Battle Bot")
    parser.add_argument(
        "-n", "--battles", type=int, default=10, help="Number of battles to play (default: 10)"
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=["ladder", "selfplay", "bot"],
        default="ladder",
        help=(
            "ladder: queue on the ladder; "
            "selfplay: two TailGlow bots fight; "
            "bot: fight a poke-env baseline bot (default: ladder)"
        ),
    )
    parser.add_argument(
        "-o",
        "--opponent",
        choices=["random", "maxpower", "heuristic"],
        default="maxpower",
        help="poke-env baseline bot to fight in 'bot' mode (default: maxpower)",
    )
    args = parser.parse_args()

    asyncio.run(main(n_battles=args.battles, mode=args.mode, opponent=args.opponent))
