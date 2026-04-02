# CHAARI 2.0 – core/embeddings.py — Embedding Provider
# Lazy-loaded sentence-transformers wrapper for RAPTOR tree + retrieval.

import logging
from typing import Optional

from config.rag import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_model_instance = None


def _get_model():
    """Lazy-load the embedding model on first use."""
    global _model_instance
    if _model_instance is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
            _model_instance = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("Embedding model loaded successfully.")
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    return _model_instance


def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a list of floats (384-dim)."""
    model = _get_model()
    embedding = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return embedding.tolist()


def embed_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Embed a batch of texts. Returns list of embedding vectors."""
    if not texts:
        return []
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 50,
    )
    return embeddings.tolist()


def is_available() -> bool:
    """Check if sentence-transformers is installed."""
    try:
        import sentence_transformers  
        return True
    except ImportError:
        return False
