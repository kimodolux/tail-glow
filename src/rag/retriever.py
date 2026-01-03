"""Strategy retriever - queries the vector store for relevant strategy documents."""

import logging
from typing import Optional

from .store import get_strategy_store

logger = logging.getLogger(__name__)


class StrategyRetriever:
    """Retrieves relevant strategy documents for battle decisions."""

    def __init__(self, k: int = 3):
        """Initialize the retriever.

        Args:
            k: Default number of results to retrieve per query
        """
        self.k = k
        self._store = None

    def _ensure_store(self):
        """Lazily get the strategy store."""
        if self._store is None:
            try:
                self._store = get_strategy_store()
            except ImportError:
                logger.warning("ChromaDB not available - retriever disabled")
                return None
        return self._store

    def retrieve_for_matchup(
        self,
        our_pokemon: str,
        their_pokemon: str,
        team_context: Optional[str] = None,
    ) -> list[str]:
        """Retrieve strategy documents relevant to the current matchup.

        Args:
            our_pokemon: Our active Pokemon species
            their_pokemon: Opponent's active Pokemon species
            team_context: Optional team analysis for context

        Returns:
            List of relevant strategy document chunks
        """
        store = self._ensure_store()
        if not store:
            return []

        # Build multiple queries for comprehensive retrieval
        queries = [
            f"{our_pokemon} strategy",
            f"how to beat {their_pokemon}",
            f"{our_pokemon} vs {their_pokemon}",
            f"dealing with {their_pokemon}",
        ]

        all_results = []
        seen_texts = set()

        for query in queries:
            try:
                results = store.query(query, k=2)
                for result in results:
                    # Deduplicate by text content
                    text_hash = hash(result[:100])  # Hash first 100 chars
                    if text_hash not in seen_texts:
                        seen_texts.add(text_hash)
                        all_results.append(result)
            except Exception as e:
                logger.warning(f"Query failed for '{query}': {e}")

        # Limit total results
        return all_results[:self.k * 2]

    def retrieve_general(self, query: str) -> list[str]:
        """Retrieve documents matching a general query.

        Args:
            query: Search query

        Returns:
            List of relevant document chunks
        """
        store = self._ensure_store()
        if not store:
            return []

        try:
            return store.query(query, k=self.k)
        except Exception as e:
            logger.warning(f"General query failed: {e}")
            return []


def format_strategy_context(results: list[str]) -> str:
    """Format retrieved strategy documents for LLM consumption.

    Args:
        results: List of retrieved document chunks

    Returns:
        Formatted string for inclusion in prompts
    """
    if not results:
        return ""

    lines = ["## Strategy Notes"]
    lines.append("")

    for i, result in enumerate(results, 1):
        # Trim whitespace and limit length
        text = result.strip()
        if len(text) > 300:
            text = text[:297] + "..."

        lines.append(f"**Note {i}:**")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)
