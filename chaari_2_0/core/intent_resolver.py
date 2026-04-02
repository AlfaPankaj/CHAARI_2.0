
import os
import toml
import tomli_w
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Tuple, Optional, List

# Intent Resolver (Layer 0.1) — Fast Semantic Matching
# Hits < 1ms on modern CPUs.

MAP_PATH = os.path.join("data", "intent_map.toml")

class IntentResolver:
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.vectorizer = TfidfVectorizer()
        self.intents: List[str] = []
        self.synonyms: List[str] = []
        self.matrix = None
        self.load_map()

    def load_map(self):
        """Load TOML map and compile the semantic matrix."""
        if not os.path.exists(MAP_PATH):
            return

        with open(MAP_PATH, "r", encoding="utf-8") as f:
            data = toml.load(f)

        self.intents = []
        self.synonyms = []
        
        for intent, info in data.items():
            for synonym in info.get("synonyms", []):
                self.intents.append(intent)
                self.synonyms.append(synonym.lower())

        if self.synonyms:
            self.matrix = self.vectorizer.fit_transform(self.synonyms)

    def resolve(self, text: str) -> Tuple[Optional[str], float]:
        """Match input text to a system intent using cosine similarity."""
        if self.matrix is None or not text:
            return None, 0.0

        query_vec = self.vectorizer.transform([text.lower()])
        similarities = cosine_similarity(query_vec, self.matrix).flatten()
        
        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]

        if best_score >= self.threshold:
            return self.intents[best_idx], best_score
        
        return None, best_score

    def learn(self, text: str, intent: str):
        """Auto-learn: Add a new synonym to the TOML file if it's not already there."""
        if not os.path.exists(MAP_PATH) or not text or not intent:
            return

        with open(MAP_PATH, "r", encoding="utf-8") as f:
            data = toml.load(f)

        if intent not in data:
            return

        synonyms = data[intent].get("synonyms", [])
        clean_text = text.lower().strip()
        
        if clean_text not in synonyms:
            synonyms.append(clean_text)
            data[intent]["synonyms"] = synonyms
            
            with open(MAP_PATH, "wb") as f:
                tomli_w.dump(data, f)
            
            self.load_map()
            print(f"[Layer 0.1] Auto-learned: '{clean_text}' -> {intent}")

    def extract_params(self, text: str, intent: str) -> dict:
        """Heuristic parameter extraction (Layer 0.15).
        Since we match intent semantically, we need to extract nouns/filenames.
        """
        import re
        params = {}
        
        if intent in ("CREATE_FILE", "DELETE_FILE", "OPEN_FILE"):
            words = text.split()
            for word in words:
                if "." in word and len(word) > 2:
                    params["file_path"] = word.strip(".,!?\"'")
                    return params
            pass
            
        return params
