# CHAARI 2.0 – core/tree_builder.py — RAPTOR Tree Builder
# Builds a hierarchical tree of summaries from document chunks.
# Level 0 (leaves) → GMM cluster → summarize → Level 1 → ... → Level 3 (root)

import os
import uuid
import logging
import numpy as np
from typing import Optional

from config.rag import (
    TREE_DEPTH,
    GMM_MAX_CLUSTERS, GMM_COVARIANCE_TYPE, GMM_RANDOM_STATE, GMM_THRESHOLD,
    SUMMARY_MAX_TOKENS, SUMMARY_TEMPERATURE, SUMMARY_PROMPT,
    COLLECTION_CHAARI_DOCS,
    META_LEVEL, META_PARENT_ID, META_SOURCE, META_CHUNK_ID,
)
from core.embeddings import embed_batch
from core import vectorstore

logger = logging.getLogger(__name__)


def _gmm_cluster(embeddings: np.ndarray, max_clusters: int = GMM_MAX_CLUSTERS) -> list[list[int]]:
    """
    Soft-cluster embeddings using Gaussian Mixture Model.
    Uses PCA for dimensionality reduction before GMM (RAPTOR paper approach).

    Returns:
        List of clusters, where each cluster is a list of chunk indices.
        A chunk can appear in multiple clusters (soft assignment).
    """
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import normalize
    from sklearn.decomposition import PCA

    n_samples = len(embeddings)
    if n_samples <= 1:
        return [[i for i in range(n_samples)]]

    reduced_dim = min(10, n_samples - 1)
    pca = PCA(n_components=reduced_dim, random_state=GMM_RANDOM_STATE)
    reduced = pca.fit_transform(normalize(embeddings))

    best_n = 1
    best_bic = float("inf")

    min_k = max(2, n_samples // 100)
    max_k = min(max_clusters, n_samples // 3, n_samples - 1)
    max_k = max(max_k, min_k + 1)

    for k in range(min_k, max_k + 1):
        try:
            gmm = GaussianMixture(
                n_components=k,
                covariance_type="diag",   
                random_state=GMM_RANDOM_STATE,
                max_iter=200,
            )
            gmm.fit(reduced)
            bic = gmm.bic(reduced)
            if bic < best_bic:
                best_bic = bic
                best_n = k
        except Exception:
            continue

    gmm = GaussianMixture(
        n_components=best_n,
        covariance_type="diag",
        random_state=GMM_RANDOM_STATE,
        max_iter=200,
    )
    gmm.fit(reduced)

    probabilities = gmm.predict_proba(reduced)
    clusters = [[] for _ in range(best_n)]
    for i in range(n_samples):
        for j in range(best_n):
            if probabilities[i][j] >= GMM_THRESHOLD:
                clusters[j].append(i)

    clusters = [c for c in clusters if len(c) > 0]
    logger.info(f"GMM clustering: {n_samples} items → {len(clusters)} clusters (k={best_n}, dim_reduced={reduced_dim})")
    return clusters


def _summarize_cluster(
    texts: list[str],
    groq_provider=None,
) -> str:
    """
    Summarize a cluster of texts into a single summary node.
    Uses Groq (fast) with Ollama fallback.
    """
    combined = "\n---\n".join(texts[:10])  
    prompt = SUMMARY_PROMPT.format(chunks=combined)

    messages = [{"role": "user", "content": prompt}]

    if groq_provider and groq_provider.is_available():
        result = groq_provider.chat(
            messages, max_tokens=SUMMARY_MAX_TOKENS, temperature=SUMMARY_TEMPERATURE
        )
        if result:
            return result.strip()

    try:
        import requests
        payload = {
            "model": "llama3.2:3b",
            "messages": messages,
            "stream": False,
            "options": {"num_predict": SUMMARY_MAX_TOKENS, "temperature": SUMMARY_TEMPERATURE},
        }
        resp = requests.post("http://localhost:11434/api/chat", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error(f"Summarization failed (both Groq and Ollama): {e}")
        return " ".join(combined.split()[:80]) + "..."



class RaptorTreeBuilder:
    """
    Builds a RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval)
    tree from document chunks.

    Process:
        1. Accept Level 0 leaf chunks (from doc_loader)
        2. Embed all leaves
        3. GMM cluster leaves → groups of similar chunks
        4. Summarize each cluster → Level 1 nodes
        5. Embed Level 1 nodes
        6. Repeat clustering + summarization → Level 2, Level 3
        7. Store entire tree in ChromaDB with level metadata
    """

    def __init__(self, groq_provider=None, collection_name: str = COLLECTION_CHAARI_DOCS):
        self.groq = groq_provider
        self.collection_name = collection_name

    def build_tree(self, leaf_chunks: list[dict]) -> dict:
        """
        Build the full RAPTOR tree from leaf chunks.

        Args:
            leaf_chunks: List of dicts from doc_loader: [{"text", "source", "chunk_id"}, ...]

        Returns:
            Stats dict: {"level_0": count, "level_1": count, ..., "total": count}
        """
        if not leaf_chunks:
            logger.warning("No chunks provided. Skipping tree build.")
            return {"total_nodes": 0, "levels": 0}

        logger.info(f"Building RAPTOR tree from {len(leaf_chunks)} leaf chunks...")

        vectorstore.clear_collection(self.collection_name)

        logger.info("Level 0: Embedding and storing leaf chunks...")
        leaf_texts = [c["text"] for c in leaf_chunks]
        leaf_embeddings = embed_batch(leaf_texts)
        leaf_ids = [str(uuid.uuid4()) for _ in leaf_chunks]

        leaf_metas = [
            {
                META_LEVEL: "0",
                META_PARENT_ID: "",
                META_SOURCE: c["source"],
                META_CHUNK_ID: c["chunk_id"],
            }
            for c in leaf_chunks
        ]

        vectorstore.add_nodes(
            self.collection_name,
            texts=leaf_texts,
            embeddings=leaf_embeddings,
            metadatas=leaf_metas,
            ids=leaf_ids,
        )

        stats = {"level_0": len(leaf_chunks)}

        current_texts = leaf_texts
        current_embeddings = np.array(leaf_embeddings)
        current_ids = leaf_ids

        for level in range(1, TREE_DEPTH):
            logger.info(f"Level {level}: Clustering {len(current_texts)} nodes...")

            if len(current_texts) <= 1:
                logger.info(f"Only {len(current_texts)} node(s) at level {level - 1}. "
                            f"Creating root summary.")
                if current_texts:
                    root_summary = _summarize_cluster(current_texts, self.groq)
                    root_embedding = embed_batch([root_summary])
                    root_id = str(uuid.uuid4())
                    vectorstore.add_nodes(
                        self.collection_name,
                        texts=[root_summary],
                        embeddings=root_embedding,
                        metadatas=[{
                            META_LEVEL: str(level),
                            META_PARENT_ID: "",
                            META_SOURCE: "raptor_summary",
                            META_CHUNK_ID: f"root_level_{level}",
                        }],
                        ids=[root_id],
                    )
                    stats[f"level_{level}"] = 1
                break

            clusters = _gmm_cluster(current_embeddings)

            next_texts = []
            next_embeddings_list = []
            next_ids = []
            next_metas = []

            for cluster_idx, chunk_indices in enumerate(clusters):
                cluster_texts = [current_texts[i] for i in chunk_indices]
                cluster_child_ids = [current_ids[i] for i in chunk_indices]

                summary = _summarize_cluster(cluster_texts, self.groq)
                node_id = str(uuid.uuid4())

                next_texts.append(summary)
                next_ids.append(node_id)
                next_metas.append({
                    META_LEVEL: str(level),
                    META_PARENT_ID: "",
                    META_SOURCE: "raptor_summary",
                    META_CHUNK_ID: f"level_{level}_cluster_{cluster_idx}",
                })


            if not next_texts:
                break

            next_embeddings = embed_batch(next_texts)

            vectorstore.add_nodes(
                self.collection_name,
                texts=next_texts,
                embeddings=next_embeddings,
                metadatas=next_metas,
                ids=next_ids,
            )

            stats[f"level_{level}"] = len(next_texts)
            logger.info(f"Level {level}: Created {len(next_texts)} summary nodes")

            current_texts = next_texts
            current_embeddings = np.array(next_embeddings)
            current_ids = next_ids

        total = sum(stats.values())
        stats["total_nodes"] = total
        stats["levels"] = max(int(k.split("_")[1]) for k in stats if k.startswith("level_")) + 1
        logger.info(f"RAPTOR tree complete: {stats}")
        return stats
