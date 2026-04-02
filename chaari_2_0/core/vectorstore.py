# CHAARI 2.0 – core/vectorstore.py — Numpy-based Vector Store with RAPTOR Tree Support
# Lightweight persistent vector store using numpy + JSON. No heavy dependencies.

import os
import json
import logging
import uuid
from typing import Optional

import numpy as np

from config.rag import (
    VECTORDB_DIR,
    COLLECTION_CHAARI_DOCS,
    META_LEVEL, META_PARENT_ID, META_SOURCE, META_CHUNK_ID,
    TOP_K_PER_LEVEL,
)

logger = logging.getLogger(__name__)

_collections: dict = {}


def _collection_dir(name: str) -> str:
    """Get the directory for a collection's persistent storage."""
    d = os.path.join(VECTORDB_DIR, name)
    os.makedirs(d, exist_ok=True)
    return d


def _load_collection(name: str) -> dict:
    """Load a collection from disk into memory."""
    if name in _collections:
        return _collections[name]

    cdir = _collection_dir(name)
    meta_path = os.path.join(cdir, "meta.json")
    emb_path = os.path.join(cdir, "embeddings.npy")

    if os.path.exists(meta_path) and os.path.exists(emb_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        embeddings = np.load(emb_path)
        col = {
            "ids": data["ids"],
            "texts": data["texts"],
            "metadatas": data["metadatas"],
            "embeddings": embeddings,
        }
    else:
        col = {
            "ids": [],
            "texts": [],
            "metadatas": [],
            "embeddings": np.empty((0, 0), dtype=np.float32),
        }

    _collections[name] = col
    return col


def _save_collection(name: str):
    """Persist a collection to disk."""
    col = _collections.get(name)
    if col is None:
        return
    cdir = _collection_dir(name)
    meta_path = os.path.join(cdir, "meta.json")
    emb_path = os.path.join(cdir, "embeddings.npy")

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "ids": col["ids"],
            "texts": col["texts"],
            "metadatas": col["metadatas"],
        }, f, ensure_ascii=False)

    if col["embeddings"].size > 0:
        np.save(emb_path, col["embeddings"])
    logger.debug(f"Saved collection '{name}' ({len(col['ids'])} nodes)")


def _cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between a query vector and a matrix of vectors."""
    if matrix.size == 0:
        return np.array([])
    query_norm = query / (np.linalg.norm(query) + 1e-10)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
    matrix_norm = matrix / norms
    return matrix_norm @ query_norm


def add_nodes(
    collection_name: str,
    texts: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
    ids: Optional[list[str]] = None,
) -> list[str]:
    """
    Add nodes (leaf chunks or summary nodes) to a collection.

    Returns:
        List of IDs that were added.
    """
    if not texts:
        return []

    col = _load_collection(collection_name)

    if ids is None:
        ids = [str(uuid.uuid4()) for _ in texts]

    clean_metas = []
    for m in metadatas:
        clean = {k: str(v) if v is not None else "" for k, v in m.items()}
        clean_metas.append(clean)

    new_emb = np.array(embeddings, dtype=np.float32)

    col["ids"].extend(ids)
    col["texts"].extend(texts)
    col["metadatas"].extend(clean_metas)

    if col["embeddings"].size == 0:
        col["embeddings"] = new_emb
    else:
        col["embeddings"] = np.vstack([col["embeddings"], new_emb])

    _save_collection(collection_name)
    logger.info(f"Added {len(texts)} nodes to collection '{collection_name}'")
    return ids


def clear_collection(collection_name: str):
    """Delete and recreate a collection (used for re-indexing)."""
    _collections.pop(collection_name, None)

    cdir = _collection_dir(collection_name)
    for fname in ("meta.json", "embeddings.npy"):
        fpath = os.path.join(cdir, fname)
        if os.path.exists(fpath):
            os.remove(fpath)

    _load_collection(collection_name)
    logger.info(f"Cleared collection '{collection_name}'")


def search_level(
    collection_name: str,
    query_embedding: list[float],
    level: int,
    top_k: int = TOP_K_PER_LEVEL,
) -> list[dict]:
    """
    Search within a specific tree level.

    Returns:
        List of dicts: [{"id", "text", "metadata", "distance"}, ...]
    """
    col = _load_collection(collection_name)
    if not col["ids"]:
        return []

    level_str = str(level)
    indices = [i for i, m in enumerate(col["metadatas"]) if m.get(META_LEVEL) == level_str]
    if not indices:
        return []

    query_vec = np.array(query_embedding, dtype=np.float32)
    subset_emb = col["embeddings"][indices]
    sims = _cosine_similarity(query_vec, subset_emb)

    k = min(top_k, len(indices))
    top_idx = np.argsort(sims)[::-1][:k]

    results = []
    for ti in top_idx:
        orig_i = indices[ti]
        results.append({
            "id": col["ids"][orig_i],
            "text": col["texts"][orig_i],
            "metadata": col["metadatas"][orig_i],
            "distance": float(1.0 - sims[ti]),  
        })
    return results


def search_collapsed(
    collection_name: str,
    query_embedding: list[float],
    top_k: int = TOP_K_PER_LEVEL,
) -> list[dict]:
    """
    Search across ALL tree levels simultaneously.
    """
    col = _load_collection(collection_name)
    if not col["ids"]:
        return []

    query_vec = np.array(query_embedding, dtype=np.float32)
    sims = _cosine_similarity(query_vec, col["embeddings"])

    k = min(top_k, len(col["ids"]))
    top_idx = np.argsort(sims)[::-1][:k]

    results = []
    for i in top_idx:
        results.append({
            "id": col["ids"][i],
            "text": col["texts"][i],
            "metadata": col["metadatas"][i],
            "distance": float(1.0 - sims[i]),
        })
    return results


def get_children(
    collection_name: str,
    parent_id: str,
    query_embedding: Optional[list[float]] = None,
    top_k: int = TOP_K_PER_LEVEL,
) -> list[dict]:
    """
    Get child nodes of a parent in the tree.
    If query_embedding is provided, results are ranked by relevance.
    """
    col = _load_collection(collection_name)
    if not col["ids"]:
        return []

    indices = [i for i, m in enumerate(col["metadatas"]) if m.get(META_PARENT_ID) == parent_id]
    if not indices:
        return []

    if query_embedding:
        query_vec = np.array(query_embedding, dtype=np.float32)
        subset_emb = col["embeddings"][indices]
        sims = _cosine_similarity(query_vec, subset_emb)
        k = min(top_k, len(indices))
        top_idx = np.argsort(sims)[::-1][:k]
        results = []
        for ti in top_idx:
            orig_i = indices[ti]
            results.append({
                "id": col["ids"][orig_i],
                "text": col["texts"][orig_i],
                "metadata": col["metadatas"][orig_i],
                "distance": float(1.0 - sims[ti]),
            })
        return results
    else:
        return [
            {
                "id": col["ids"][i],
                "text": col["texts"][i],
                "metadata": col["metadatas"][i],
                "distance": 0.0,
            }
            for i in indices
        ]


def get_node_by_id(collection_name: str, node_id: str) -> Optional[dict]:
    """Get a single node by its ID."""
    col = _load_collection(collection_name)
    try:
        idx = col["ids"].index(node_id)
        return {
            "id": col["ids"][idx],
            "text": col["texts"][idx],
            "metadata": col["metadatas"][idx],
        }
    except ValueError:
        return None


def get_collection_stats(collection_name: str) -> dict:
    """Get stats about a collection."""
    col = _load_collection(collection_name)
    total = len(col["ids"])

    level_counts = {}
    for level in range(4):
        level_str = str(level)
        count = sum(1 for m in col["metadatas"] if m.get(META_LEVEL) == level_str)
        level_counts[f"level_{level}"] = count

    return {
        "collection": collection_name,
        "total_nodes": total,
        **level_counts,
    }


def is_available() -> bool:
    """Always available — uses numpy only."""
    return True
