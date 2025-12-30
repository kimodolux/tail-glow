"""Strategy RAG node - retrieves relevant strategy documents."""

import logging

from ..state import AgentState

logger = logging.getLogger(__name__)


def lookup_strategy_node(state: AgentState) -> AgentState:
    """
    Look up relevant strategy documents from the vector store.
    Uses the current matchup and team context to find relevant advice.
    """
    battle = state.get("battle_object")
    if not battle or not battle.active_pokemon or not battle.opponent_active_pokemon:
        logger.warning("No active Pokemon in state, skipping strategy lookup")
        state["strategy_context"] = None
        return state

    try:
        from src.rag import StrategyRetriever, format_strategy_context

        retriever = StrategyRetriever(k=3)

        our_pokemon = battle.active_pokemon.species
        their_pokemon = battle.opponent_active_pokemon.species
        team_analysis = state.get("team_analysis")

        # Retrieve relevant strategy documents
        results = retriever.retrieve_for_matchup(
            our_pokemon=our_pokemon,
            their_pokemon=their_pokemon,
            team_context=team_analysis,
        )

        if results:
            strategy_text = format_strategy_context(results)
            state["strategy_context"] = strategy_text
            logger.info(f"Retrieved {len(results)} strategy documents")
        else:
            state["strategy_context"] = None
            logger.debug("No strategy documents found for matchup")

    except ImportError:
        # ChromaDB not installed - gracefully degrade
        logger.debug("RAG not available (chromadb not installed)")
        state["strategy_context"] = None
    except Exception as e:
        logger.warning(f"Strategy lookup failed: {e}")
        state["strategy_context"] = None
        state["tool_results"]["strategy_error"] = str(e)

    return state
