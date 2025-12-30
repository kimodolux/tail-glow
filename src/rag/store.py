"""ChromaDB vector store for strategy document retrieval.

Supports both reading (querying) and writing (adding learnings) for
future bot self-improvement capabilities.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Global store instance
_strategy_store: Optional["StrategyStore"] = None


class StrategyStore:
    """Vector store for Pokemon battle strategy documents."""

    def __init__(self, persist_dir: str = "./data/chroma"):
        """Initialize the ChromaDB store.

        Args:
            persist_dir: Directory to persist the database
        """
        self.persist_dir = persist_dir
        self._client = None
        self._collection = None

    def _ensure_initialized(self):
        """Lazily initialize ChromaDB connection."""
        if self._collection is not None:
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

            self._collection = self._client.get_or_create_collection(
                name="strategy_docs",
                metadata={"hnsw:space": "cosine"}
            )

            logger.info(
                f"ChromaDB initialized at {self.persist_dir} "
                f"with {self._collection.count()} documents"
            )

        except ImportError:
            logger.warning("chromadb not installed - RAG features disabled")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

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
        """Add a bot-generated learning to the store.

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

        return {
            "total_documents": self._collection.count(),
            "persist_dir": self.persist_dir,
        }


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
