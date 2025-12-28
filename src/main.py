"""Main entry point for Tail Glow Pokemon battle bot."""

import asyncio
import logging
import argparse

from src.config import Config
from src.data import init_randbats_data
from src.showdown.client import run_battles


def setup_logging():
    """Configure logging based on config."""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


async def main(n_battles: int = 10):
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Tail Glow MVP...")

    # Validate config
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return

    logger.info(f"LLM Provider: {Config.LLM_PROVIDER}")
    if Config.LLM_PROVIDER == "ollama":
        logger.info(f"Ollama Model: {Config.OLLAMA_MODEL}")
    else:
        logger.info(f"Anthropic Model: {Config.ANTHROPIC_MODEL}")

    # Fetch and cache randbats data (accessible via get_randbats_data() anywhere)
    logger.info(f"Fetching randbats data for {Config.BATTLE_FORMAT}...")
    randbats_data = await init_randbats_data(
        Config.BATTLE_FORMAT,
        url_template=Config.RANDBATS_DATA_URL,
    )
    if randbats_data:
        logger.info(f"Loaded randbats data for {len(randbats_data)} Pokemon")
    else:
        logger.warning("Failed to fetch randbats data, using fallback estimates")

    # Run battles
    await run_battles(n_battles=n_battles)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tail Glow Pokemon Battle Bot")
    parser.add_argument(
        "-n", "--battles", type=int, default=10, help="Number of battles to play (default: 10)"
    )
    args = parser.parse_args()

    asyncio.run(main(n_battles=args.battles))
