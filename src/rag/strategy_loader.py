"""Load and cache the general strategy document for prompt inclusion.

The general strategy document is included in full in every prompt to provide
foundational competitive Pokemon knowledge.
"""

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to the general strategy documents directory
GENERAL_STRATEGY_DIR = Path(__file__).parent.parent.parent / "docs" / "strategy" / "general"

# Strategy files to load in order. Only the timeless / always-relevant docs
# go here. Conditional mechanics (weather, terrain, hazards, screens, priority,
# etc.) are loaded per-turn via src.rag.mechanics_resolver.
STRATEGY_FILES = [
    "mechanics_core.md",
    "team_archetypes.md",
    "core_strategy.md",
]


@lru_cache(maxsize=1)
def load_general_strategy() -> str:
    """Load all general strategy documents from disk and combine them.

    Uses LRU cache to avoid repeated file reads.

    Returns:
        The combined content of all strategy documents, or empty string if not found.
    """
    try:
        if not GENERAL_STRATEGY_DIR.exists():
            logger.warning(f"General strategy directory not found at {GENERAL_STRATEGY_DIR}")
            return ""

        contents = []
        for filename in STRATEGY_FILES:
            filepath = GENERAL_STRATEGY_DIR / filename
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                contents.append(content)
                logger.debug(f"Loaded {filename} ({len(content)} chars)")
            else:
                logger.warning(f"Strategy file not found: {filepath}")

        if not contents:
            logger.warning("No strategy files found")
            return ""

        combined = "\n\n---\n\n".join(contents)
        logger.debug(f"Loaded general strategy documents ({len(combined)} total chars)")
        return combined
    except Exception as e:
        logger.error(f"Failed to load general strategy documents: {e}")
        return ""


def get_general_strategy_section() -> str:
    """Get the general strategy formatted for prompt inclusion.

    Returns:
        Formatted strategy section with header, or empty string if unavailable.
    """
    content = load_general_strategy()
    if not content:
        return ""

    return f"""## General Strategy Principles

{content}"""


def clear_strategy_cache():
    """Clear the cached strategy document.

    Call this if the strategy document is updated and needs to be reloaded.
    """
    load_general_strategy.cache_clear()
    logger.info("Strategy document cache cleared")
