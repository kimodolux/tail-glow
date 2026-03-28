"""ChromaDB vector store for strategy document retrieval and self-learning.

Supports multiple collections:
- strategy_docs: Static strategy documentation
- matchup_learnings: Learned Pokemon matchup outcomes
- mistake_learnings: Learned mistakes to avoid
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

from .models import MatchupLearning, MistakeLearning

logger = logging.getLogger(__name__)

# Global store instance
_strategy_store: Optional["StrategyStore"] = None

# Collection names
COLLECTION_STRATEGY_DOCS = "strategy_docs"
COLLECTION_MATCHUP_LEARNINGS = "matchup_learnings"
COLLECTION_MISTAKE_LEARNINGS = "mistake_learnings"


class StrategyStore:
    """Vector store for Pokemon battle strategy documents and learnings.

    Manages three collections:
    - strategy_docs: Static strategy documentation from markdown files
    - matchup_learnings: Learned Pokemon matchup outcomes from battles
    - mistake_learnings: Learned mistakes to avoid in future battles
    """

    def __init__(self, persist_dir: str = "./data/chroma"):
        """Initialize the ChromaDB store.

        Args:
            persist_dir: Directory to persist the database
        """
        self.persist_dir = persist_dir
        self._client = None
        self._collections: dict = {}

    def _ensure_initialized(self):
        """Lazily initialize ChromaDB connection and all collections."""
        if self._collections:
            return

        try:
            import chromadb
            from chromadb.config import Settings

            # Create persist directory if needed
            Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                )
            )

            # Initialize all collections
            self._collections[COLLECTION_STRATEGY_DOCS] = self._client.get_or_create_collection(
                name=COLLECTION_STRATEGY_DOCS,
                metadata={"hnsw:space": "cosine", "description": "Static strategy documentation"}
            )

            self._collections[COLLECTION_MATCHUP_LEARNINGS] = self._client.get_or_create_collection(
                name=COLLECTION_MATCHUP_LEARNINGS,
                metadata={"hnsw:space": "cosine", "description": "Learned matchup outcomes"}
            )

            self._collections[COLLECTION_MISTAKE_LEARNINGS] = self._client.get_or_create_collection(
                name=COLLECTION_MISTAKE_LEARNINGS,
                metadata={"hnsw:space": "cosine", "description": "Learned mistakes to avoid"}
            )

            total_docs = sum(c.count() for c in self._collections.values())
            logger.info(
                f"ChromaDB initialized at {self.persist_dir} "
                f"with {total_docs} total documents across {len(self._collections)} collections"
            )

        except ImportError:
            logger.warning("chromadb not installed - RAG features disabled")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    @property
    def _collection(self):
        """Backward compatibility: return strategy_docs collection."""
        self._ensure_initialized()
        return self._collections[COLLECTION_STRATEGY_DOCS]

    def index_documents(self, docs_path: str) -> int:
        """Index all markdown files from a directory.

        Args:
            docs_path: Path to directory containing .md files

        Returns:
            Number of documents indexed
        """
        self._ensure_initialized()

        docs_dir = Path(docs_path)
        if not docs_dir.exists():
            logger.warning(f"Documents directory not found: {docs_path}")
            return 0

        indexed_count = 0
        for md_file in docs_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if not content.strip():
                    continue

                # Use relative path as document ID
                doc_id = str(md_file.relative_to(docs_dir))

                # Chunk long documents
                chunks = self._chunk_document(content, doc_id)

                for chunk_id, chunk_text in chunks:
                    # Check if already indexed
                    existing = self._collection.get(ids=[chunk_id])
                    if existing and existing["ids"]:
                        # Update existing
                        self._collection.update(
                            ids=[chunk_id],
                            documents=[chunk_text],
                            metadatas=[{"source": doc_id, "type": "strategy"}]
                        )
                    else:
                        # Add new
                        self._collection.add(
                            ids=[chunk_id],
                            documents=[chunk_text],
                            metadatas=[{"source": doc_id, "type": "strategy"}]
                        )

                indexed_count += 1
                logger.debug(f"Indexed: {doc_id}")

            except Exception as e:
                logger.warning(f"Failed to index {md_file}: {e}")

        logger.info(f"Indexed {indexed_count} documents from {docs_path}")
        return indexed_count

    def query(self, query: str, k: int = 3) -> list[str]:
        """Query the vector store for relevant documents.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of relevant document chunks
        """
        self._ensure_initialized()

        if self._collection.count() == 0:
            return []

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(k, self._collection.count()),
            )

            if results and results["documents"]:
                return results["documents"][0]
            return []

        except Exception as e:
            logger.warning(f"Query failed: {e}")
            return []

    def add_learning(
        self,
        content: str,
        battle_id: str,
        turn: int,
        outcome: Optional[str] = None,
    ) -> bool:
        """Add a bot-generated learning to the store (legacy method).

        Args:
            content: The learning content
            battle_id: ID of the battle this learning came from
            turn: Turn number where the learning occurred
            outcome: Optional outcome description (win/loss/lesson)

        Returns:
            True if successfully added
        """
        self._ensure_initialized()

        try:
            doc_id = f"learning_{battle_id}_{turn}"

            self._collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[{
                    "type": "learning",
                    "battle_id": battle_id,
                    "turn": turn,
                    "outcome": outcome or "unknown",
                }]
            )

            logger.info(f"Added learning: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add learning: {e}")
            return False

    def add_matchup_learning(self, learning: MatchupLearning) -> bool:
        """Add a matchup learning to the dedicated collection.

        Args:
            learning: MatchupLearning object with full context

        Returns:
            True if successfully added
        """
        self._ensure_initialized()

        try:
            # Generate unique ID based on content hash
            content = learning.to_document()
            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            doc_id = f"matchup_{learning.pokemon}_{learning.opponent}_{content_hash}"

            collection = self._collections[COLLECTION_MATCHUP_LEARNINGS]

            # Check if similar learning already exists
            existing = collection.get(ids=[doc_id])
            if existing and existing["ids"]:
                logger.debug(f"Matchup learning already exists: {doc_id}")
                return True

            collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[learning.to_metadata()]
            )

            logger.info(f"Added matchup learning: {learning.pokemon} vs {learning.opponent} ({learning.outcome.value})")
            return True

        except Exception as e:
            logger.error(f"Failed to add matchup learning: {e}")
            return False

    def add_mistake_learning(self, learning: MistakeLearning) -> bool:
        """Add a mistake learning to the dedicated collection.

        Args:
            learning: MistakeLearning object with full context

        Returns:
            True if successfully added
        """
        self._ensure_initialized()

        try:
            # Generate unique ID based on content hash
            content = learning.to_document()
            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            doc_id = f"mistake_{learning.mistake_type.value}_{content_hash}"

            collection = self._collections[COLLECTION_MISTAKE_LEARNINGS]

            # Check if similar learning already exists
            existing = collection.get(ids=[doc_id])
            if existing and existing["ids"]:
                logger.debug(f"Mistake learning already exists: {doc_id}")
                return True

            collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[learning.to_metadata()]
            )

            logger.info(f"Added mistake learning: {learning.mistake_type.value} ({learning.our_pokemon} vs {learning.opponent})")
            return True

        except Exception as e:
            logger.error(f"Failed to add mistake learning: {e}")
            return False

    def query_matchups(
        self,
        pokemon: str,
        opponent: Optional[str] = None,
        role: Optional[str] = None,
        format: str = "gen9randombattle",
        k: int = 3,
    ) -> list[dict]:
        """Query matchup learnings with optional filtering.

        Args:
            pokemon: Our Pokemon species (required)
            opponent: Opponent Pokemon species (optional filter)
            role: Our Pokemon's role (optional filter)
            format: Battle format (default: gen9randombattle)
            k: Number of results to return

        Returns:
            List of dicts with 'document' and 'metadata' keys
        """
        self._ensure_initialized()

        collection = self._collections[COLLECTION_MATCHUP_LEARNINGS]
        if collection.count() == 0:
            return []

        try:
            # Build query text
            query_text = f"{pokemon} matchup"
            if opponent:
                query_text += f" vs {opponent}"
            if role:
                query_text += f" {role}"

            # Build where clause for filtering
            where_clause = {"format": format}
            if opponent:
                where_clause = {"$and": [{"format": format}, {"opponent": opponent}]}

            results = collection.query(
                query_texts=[query_text],
                n_results=min(k, collection.count()),
                where=where_clause if opponent else {"format": format},
            )

            return self._format_query_results(results)

        except Exception as e:
            logger.warning(f"Matchup query failed: {e}")
            return []

    def query_mistakes(
        self,
        situation: str,
        pokemon: Optional[str] = None,
        mistake_type: Optional[str] = None,
        k: int = 3,
    ) -> list[dict]:
        """Query mistake learnings with optional filtering.

        Args:
            situation: Description of current situation
            pokemon: Our Pokemon involved (optional filter)
            mistake_type: Type of mistake to look for (optional filter)
            k: Number of results to return

        Returns:
            List of dicts with 'document' and 'metadata' keys
        """
        self._ensure_initialized()

        collection = self._collections[COLLECTION_MISTAKE_LEARNINGS]
        if collection.count() == 0:
            return []

        try:
            # Build where clause
            where_conditions = []
            if pokemon:
                where_conditions.append({"pokemon": pokemon})
            if mistake_type:
                where_conditions.append({"mistake_type": mistake_type})

            where_clause = None
            if len(where_conditions) == 1:
                where_clause = where_conditions[0]
            elif len(where_conditions) > 1:
                where_clause = {"$and": where_conditions}

            results = collection.query(
                query_texts=[situation],
                n_results=min(k, collection.count()),
                where=where_clause,
            )

            return self._format_query_results(results)

        except Exception as e:
            logger.warning(f"Mistake query failed: {e}")
            return []

    def _format_query_results(self, results: dict) -> list[dict]:
        """Format ChromaDB query results into a list of dicts.

        Args:
            results: Raw ChromaDB query results

        Returns:
            List of dicts with 'document' and 'metadata' keys
        """
        if not results or not results.get("documents"):
            return []

        formatted = []
        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(documents)
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(documents)

        for doc, meta, dist in zip(documents, metadatas, distances):
            formatted.append({
                "document": doc,
                "metadata": meta,
                "distance": dist,
            })

        return formatted

    def _chunk_document(
        self,
        content: str,
        doc_id: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> list[tuple[str, str]]:
        """Split a document into chunks for better retrieval.

        Args:
            content: Document content
            doc_id: Document identifier
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks

        Returns:
            List of (chunk_id, chunk_text) tuples
        """
        # Simple chunking by paragraphs first
        paragraphs = content.split("\n\n")

        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_size = len(para)

            if current_size + para_size > chunk_size and current_chunk:
                # Save current chunk
                chunk_text = "\n\n".join(current_chunk)
                chunk_id = f"{doc_id}_chunk_{len(chunks)}"
                chunks.append((chunk_id, chunk_text))

                # Start new chunk with overlap
                if len(current_chunk) > 1:
                    current_chunk = current_chunk[-1:]  # Keep last paragraph for overlap
                    current_size = len(current_chunk[0])
                else:
                    current_chunk = []
                    current_size = 0

            current_chunk.append(para)
            current_size += para_size

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunk_id = f"{doc_id}_chunk_{len(chunks)}"
            chunks.append((chunk_id, chunk_text))

        # If no chunks created, return whole document
        if not chunks:
            return [(f"{doc_id}_chunk_0", content)]

        return chunks

    def get_stats(self) -> dict:
        """Get statistics about the store.

        Returns:
            Dictionary with store statistics
        """
        self._ensure_initialized()

        stats = {
            "persist_dir": self.persist_dir,
            "collections": {},
            "total_documents": 0,
        }

        for name, collection in self._collections.items():
            count = collection.count()
            stats["collections"][name] = count
            stats["total_documents"] += count

        return stats


def get_strategy_store(persist_dir: str = "./data/chroma") -> StrategyStore:
    """Get or create the global strategy store instance.

    Args:
        persist_dir: Directory to persist the database

    Returns:
        StrategyStore instance
    """
    global _strategy_store

    if _strategy_store is None:
        _strategy_store = StrategyStore(persist_dir)

    return _strategy_store


def init_strategy_store(docs_path: str = "./docs/strategy", persist_dir: str = "./data/chroma"):
    """Initialize the strategy store and index documents.

    Call this at application startup.

    Args:
        docs_path: Path to strategy documents
        persist_dir: Path to persist ChromaDB data
    """
    store = get_strategy_store(persist_dir)

    # Index documents if the path exists
    if Path(docs_path).exists():
        store.index_documents(docs_path)
        logger.info(f"Strategy store initialized with documents from {docs_path}")
    else:
        logger.info(f"Strategy store initialized (no documents at {docs_path})")
