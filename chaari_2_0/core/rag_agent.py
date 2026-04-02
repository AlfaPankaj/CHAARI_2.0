# CHAARI 2.0 – core/rag_agent.py — Agentic RAG with RAPTOR Tree Navigation
# The intelligent retrieval loop: Route → Select Level → Retrieve → Evaluate → Self-Correct
# Max 3 iterations. Returns rag_context string or empty if RAG not needed.
#
# Optimization: Internal RAG decisions (routing, level selection, evaluation)
# use local Ollama (llama3.2:3b, already loaded for chat) instead of burning Groq quota.
# Groq is preserved for the final user-facing answer generation.

import re
import logging
import requests
from typing import Optional

from config.rag import (
    MAX_RAG_ITERATIONS, TOP_K_PER_LEVEL, RELEVANCE_THRESHOLD,
    COLLECTION_CHAARI_DOCS, COLLECTION_USER_DOCS,
    RAG_TRIGGER_KEYWORDS, RAG_SKIP_KEYWORDS,
    LEVEL_BROAD_KEYWORDS, LEVEL_SPECIFIC_KEYWORDS,
    TREE_DEPTH,
    OLLAMA_BASE_URL, ROUTER_MODEL, LEVEL_SELECTOR_MODEL, EVALUATOR_MODEL,
)
from core.embeddings import embed_text, is_available as embeddings_available
from core import vectorstore

logger = logging.getLogger(__name__)



class _OllamaLight:
    """Minimal Ollama client for fast classification tasks.
    Uses tiny local models to avoid burning Groq API quota on YES/NO decisions."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self._base_url = base_url
        self._available = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                r = requests.get(f"{self._base_url}/api/tags", timeout=2)
                self._available = r.status_code == 200
            except Exception:
                self._available = False
        return self._available

    def generate(self, model: str, prompt: str, max_tokens: int = 10) -> Optional[str]:
        """Quick local chat generation. Returns response text or None."""
        if not self.is_available():
            return None
        try:
            resp = requests.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": max_tokens, "temperature": 0.0},
                },
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.debug(f"OllamaLight call failed ({model}): {e}")
        return None


_ollama_light = _OllamaLight()



class _Router:
    """
    Rule-based router with optional LLM fallback.
    Decides if a query needs document retrieval.
    """

    def __init__(self):
        self._trigger = [re.compile(p) for p in RAG_TRIGGER_KEYWORDS]
        self._skip = [re.compile(p) for p in RAG_SKIP_KEYWORDS]

    def needs_rag(self, query: str, groq=None) -> bool:
        """Returns True if the query should trigger RAG retrieval."""
        text = query.strip()
        if not text or len(text) < 5:
            return False

        skip_hits = sum(1 for p in self._skip if p.search(text))
        if skip_hits > 0:
            return False

        trigger_hits = sum(1 for p in self._trigger if p.search(text))
        if trigger_hits >= 1:
            return True

        if len(text.split()) <= 3 and trigger_hits == 0:
            return False

        if len(text.split()) >= 4:
            return self._llm_route(text, groq)

        return False

    def _llm_route(self, query: str, groq=None) -> bool:
        """Use lightweight local model for routing. Falls back to Groq if Ollama unavailable."""
        prompt = (
            "Classify: does this query need a knowledge base search about CHAARI AI system?\n"
            "Examples:\n"
            '"How does encryption work?" → YES\n'
            '"open notepad" → NO\n'
            '"hello bhai" → NO\n'
            '"explain the security pipeline" → YES\n'
            '"play music on youtube" → NO\n\n'
            f'"{query}" →'
        )

        result = _ollama_light.generate(ROUTER_MODEL, prompt, max_tokens=20)
        if result:
            return "yes" in result.lower()

        if groq and groq.is_available():
            messages = [{"role": "user", "content": prompt}]
            result = groq.chat(messages, max_tokens=5, temperature=0.0)
            if result:
                return "yes" in result.strip().lower()

        return False


class _LevelSelector:
    """
    Determines the starting tree level based on query depth.
    Level 3 (root) for broad, Level 0 (leaves) for specific.
    """

    def __init__(self):
        self._broad = [re.compile(p) for p in LEVEL_BROAD_KEYWORDS]
        self._specific = [re.compile(p) for p in LEVEL_SPECIFIC_KEYWORDS]

    def select_level(self, query: str, groq=None) -> int:
        """Returns the starting tree level (0-3)."""
        broad_hits = sum(1 for p in self._broad if p.search(query))
        specific_hits = sum(1 for p in self._specific if p.search(query))

        if broad_hits > 0 and specific_hits == 0:
            return min(TREE_DEPTH - 1, 3)  
        if specific_hits > 0 and broad_hits == 0:
            return 0  

        return self._llm_select(query, groq)

    def _llm_select(self, query: str, groq=None) -> int:
        """Use lightweight local model for level selection. Falls back to Groq."""
        prompt = (
            "Pick search depth for a document tree. Reply with ONLY a number.\n"
            "3=broad overview, 2=architecture themes, 1=specific components, 0=exact values\n\n"
            "Examples:\n"
            '"What is CHAARI?" → 3\n'
            '"Explain the architecture areas" → 2\n'
            '"How does the brain module work?" → 1\n'
            '"What port number does executor use?" → 0\n\n'
            f'"{query}" →'
        )

        result = _ollama_light.generate(LEVEL_SELECTOR_MODEL, prompt, max_tokens=10)
        if result:
            for ch in result.strip():
                if ch.isdigit() and int(ch) <= 3:
                    return int(ch)

        if groq and groq.is_available():
            messages = [{"role": "user", "content": prompt}]
            result = groq.chat(messages, max_tokens=3, temperature=0.0)
            if result:
                for ch in result.strip():
                    if ch.isdigit() and int(ch) <= 3:
                        return int(ch)

        return 1 



class _Evaluator:
    """
    Evaluates whether retrieved results are sufficient to answer the query.
    Returns action: 'sufficient', 'drill_down', 'go_up', 'retry_different'.
    """

    def evaluate(self, query: str, results: list[dict], current_level: int, groq=None) -> str:
        """
        Evaluate retrieval results.

        Returns:
            'sufficient' — results are good enough
            'drill_down' — go to lower level for more detail
            'go_up' — go to higher level for broader context
            'retry_different' — try collapsed search
        """
        if not results:
            return "retry_different"

        avg_distance = sum(r["distance"] for r in results) / len(results)

        if avg_distance < RELEVANCE_THRESHOLD and len(results) >= 2:
            return "sufficient"

        if avg_distance > 0.8:
            return "retry_different"

        if groq and groq.is_available():
            return self._llm_evaluate(query, results, current_level, groq)

        if current_level > 1 and avg_distance > 0.5:
            return "drill_down"
        if current_level == 0 and avg_distance > 0.5:
            return "go_up"

        return "sufficient"

    def _llm_evaluate(self, query: str, results: list[dict], current_level: int, groq) -> str:
        """Use local llama3.2:1b for evaluation. Falls back to Groq."""
        context = "\n".join([f"- {r['text'][:200]}" for r in results[:3]])
        prompt = (
            f'Query: "{query}"\n\n'
            f"Retrieved context (level {current_level}):\n{context}\n\n"
            "Is this context enough to answer the query? Reply with ONE word:\n"
            "SUFFICIENT / DRILL_DOWN / GO_UP / RETRY\n\n"
            "Answer:"
        )

        result = _ollama_light.generate(EVALUATOR_MODEL, prompt, max_tokens=10)
        if result:
            r = result.upper()
            if "SUFFICIENT" in r:
                return "sufficient"
            if "DRILL" in r or "DOWN" in r:
                return "drill_down"
            if "UP" in r:
                return "go_up"
            if "RETRY" in r:
                return "retry_different"

        if groq and groq.is_available():
            messages = [{"role": "user", "content": prompt}]
            result = groq.chat(messages, max_tokens=10, temperature=0.0)
            if result:
                r = result.strip().upper()
                if "SUFFICIENT" in r:
                    return "sufficient"
                if "DRILL" in r or "DOWN" in r:
                    return "drill_down"
                if "UP" in r:
                    return "go_up"
                if "RETRY" in r:
                    return "retry_different"

        return "sufficient"  


def _assemble_context(all_results: list[dict], query: str) -> str:
    """
    Assemble retrieved results into a formatted rag_context string.
    Deduplicates, ranks, and formats for prompt injection.
    """
    if not all_results:
        return ""

    seen_texts = set()
    unique = []
    for r in all_results:
        text_key = r["text"][:100]
        if text_key not in seen_texts:
            seen_texts.add(text_key)
            unique.append(r)

    unique.sort(key=lambda r: r.get("distance", 0.0))

    parts = ["## RETRIEVED KNOWLEDGE (from CHAARI knowledge base — use this to answer)"]

    for r in unique[:8]:  
        level = r.get("metadata", {}).get("tree_level", "?")
        source = r.get("metadata", {}).get("source", "unknown")
        text = r["text"].strip()
        level_label = {
            "0": "Detail", "1": "Section", "2": "Theme", "3": "Overview"
        }.get(str(level), "Info")
        parts.append(f"[{level_label} | {source}]\n{text}")

    parts.append(
        "Use the above knowledge to answer accurately. "
        "Do NOT say 'according to the knowledge base'. Answer naturally as Chaari."
    )

    return "\n\n".join(parts)



class RAGAgent:
    """
    Agentic RAG with RAPTOR tree navigation.

    The iterative loop:
        1. ROUTER — Does this query need RAG? (rule-based + optional LLM)
        2. LEVEL SELECTOR — Which tree level to start? (keyword + optional LLM)
        3. RETRIEVER — Search at selected level (tree traversal or collapsed)
        4. EVALUATOR — Sufficient? Or drill down / go up / retry? (heuristic + LLM)
        5. Repeat up to MAX_RAG_ITERATIONS times.
        6. ASSEMBLER — Format results into rag_context string.
    """

    def __init__(self, groq=None, collection_name: str = COLLECTION_CHAARI_DOCS):
        self.groq = groq
        self.collection_name = collection_name
        self._router = _Router()
        self._level_selector = _LevelSelector()
        self._evaluator = _Evaluator()
        self._available = None

    _CHAARI_TERMS = re.compile(
        r"(?i)\b(chaari|cherry|architecture|pipeline|executor|brain|groq|ollama|"
        r"security|safety|crypto|dell|asus|node|tts|stt|wake\s*word|guardrail|privilege)\b"
    )

    def is_available(self) -> bool:
        """Check if RAG system is operational (embeddings + vectorstore ready)."""
        if self._available is None:
            self._available = embeddings_available() and vectorstore.is_available()
        return self._available

    def _get_collections(self, query: str) -> list[str]:
        """Determine which collections to search based on query content."""
        collections = []
        try:
            chaari_stats = vectorstore.get_collection_stats(COLLECTION_CHAARI_DOCS)
            if chaari_stats.get("total_nodes", 0) > 0:
                collections.append(COLLECTION_CHAARI_DOCS)
        except Exception:
            pass

        try:
            user_stats = vectorstore.get_collection_stats(COLLECTION_USER_DOCS)
            if user_stats.get("total_nodes", 0) > 0:
                collections.append(COLLECTION_USER_DOCS)
        except Exception:
            pass

        if not self._CHAARI_TERMS.search(query) and COLLECTION_USER_DOCS in collections:
            collections = [COLLECTION_USER_DOCS] + [c for c in collections if c != COLLECTION_USER_DOCS]

        return collections if collections else [self.collection_name]

    def retrieve(self, query: str) -> str:
        """
        Main entry point. Returns rag_context string or empty string.

        This is called by brain.py between _pre_process() and _build_messages().
        Searches across relevant collections (chaari_docs + user_docs).
        """
        if not self.is_available():
            return ""

        collections = self._get_collections(query)
        if not collections:
            return ""

        if not self._router.needs_rag(query, self.groq):
            return ""

        logger.info(f"RAG triggered for: '{query[:60]}...' → collections: {collections}")

        current_level = self._level_selector.select_level(query, self.groq)
        logger.info(f"Starting at tree level {current_level}")

        query_embedding = embed_text(query)

        all_results = []
        tried_collapsed = False

        for iteration in range(MAX_RAG_ITERATIONS):
            logger.info(f"Iteration {iteration + 1}: Searching level {current_level}")

            results = []
            for coll in collections:
                try:
                    stats = vectorstore.get_collection_stats(coll)
                    if stats.get("total_nodes", 0) == 0:
                        continue
                except Exception:
                    continue

                if current_level == -1:
                    coll_results = vectorstore.search_collapsed(
                        coll, query_embedding, TOP_K_PER_LEVEL
                    )
                    tried_collapsed = True
                else:
                    coll_results = vectorstore.search_level(
                        coll, query_embedding, current_level, TOP_K_PER_LEVEL
                    )
                results.extend(coll_results)

            results.sort(key=lambda r: r.get("distance", 1.0))
            results = results[:TOP_K_PER_LEVEL]

            all_results.extend(results)

            action = self._evaluator.evaluate(query, results, current_level, self.groq)
            logger.info(f"Evaluator decision: {action}")

            if action == "sufficient":
                break

            if action == "drill_down":
                if current_level > 0:
                    current_level -= 1
                else:
                    break  

            elif action == "go_up":
                if current_level < TREE_DEPTH - 1:
                    current_level += 1
                else:
                    break  

            elif action == "retry_different":
                if not tried_collapsed:
                    current_level = -1  
                else:
                    break  

        rag_context = _assemble_context(all_results, query)

        if rag_context:
            logger.info(f"RAG returned context ({len(all_results)} chunks, "
                        f"{len(rag_context)} chars)")
        else:
            logger.info("RAG found no relevant results")

        return rag_context
