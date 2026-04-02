# CHAARI 2.0 – Persistent Memory
# Stores user details and conversation context across sessions

import json
import os
from datetime import datetime



_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_FILE = os.path.join(_BASE_DIR, "data", "memory_store.json")



DEFAULT_MEMORY = {
    "user": {
        "name": None,
        "city": None,
        "hobby": None,
        "favorite_color": None,
        "profession": None,
        "preferences": {},
        "notes": [],
    },
    "session": {
        "last_active": None,
        "total_sessions": 0,
        "mood_history": [],
    },
    "facts": [],          
    "conversation_log": [],  
}

PROFILE_FIELDS = ["name", "city", "hobby", "favorite_color", "profession"]



class Memory:
    """Persistent memory layer — stores user details across sessions."""

    def __init__(self, filepath: str = MEMORY_FILE):
        self.filepath = filepath
        self.data: dict = {}
        self._load()

    def _load(self):
        """Load memory from disk. Create default if missing or empty."""
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        self.data = json.loads(content)
                    else:
                        self.data = {}
            else:
                self.data = {}
        except (json.JSONDecodeError, IOError):
            self.data = {}

        for key, value in DEFAULT_MEMORY.items():
            if key not in self.data:
                self.data[key] = value if not isinstance(value, (dict, list)) else type(value)(value)

    def _save(self):
        """Write memory to disk."""
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def set_user_name(self, name: str):
        """Store the user's name."""
        self.data["user"]["name"] = name
        self._save()

    def get_user_name(self) -> str | None:
        """Return the user's name, or None if unknown."""
        return self.data["user"].get("name")

    def set_preference(self, key: str, value: str):
        """Store a user preference (e.g., 'music' -> 'lofi')."""
        self.data["user"]["preferences"][key] = value
        self._save()

    def get_preference(self, key: str) -> str | None:
        """Retrieve a user preference."""
        return self.data["user"]["preferences"].get(key)

    def set_profile_field(self, key: str, value: str):
        """Set a structured profile field (name, city, hobby, etc.)."""
        if key in PROFILE_FIELDS:
            self.data["user"][key] = value
            self._save()

    def get_profile_field(self, key: str) -> str | None:
        """Get a structured profile field."""
        return self.data["user"].get(key)

    def get_profile(self) -> dict:
        """Return the full user profile (structured fields only)."""
        return {k: self.data["user"].get(k) for k in PROFILE_FIELDS}

    def is_returning_user(self) -> bool:
        """Check if this is a returning user (has a name set)."""
        return self.data["user"].get("name") is not None

    def add_fact(self, fact: str):
        """Store a learned fact about the user."""
        if fact not in self.data["facts"]:
            self.data["facts"].append(fact)
            self._save()

    def get_facts(self) -> list[str]:
        """Return all known facts."""
        return self.data["facts"]

    def start_session(self):
        """Mark the start of a new session."""
        self.data["session"]["last_active"] = datetime.now().isoformat()
        self.data["session"]["total_sessions"] += 1
        self._save()

    def get_session_count(self) -> int:
        """Return total session count."""
        return self.data["session"]["total_sessions"]

    def get_last_active(self) -> str | None:
        """Return the last active timestamp."""
        return self.data["session"].get("last_active")

    def log_mood(self, mood: str):
        """Log a detected mood for tracking."""
        entry = {
            "mood": mood,
            "timestamp": datetime.now().isoformat(),
        }
        self.data["session"]["mood_history"].append(entry)
        self.data["session"]["mood_history"] = self.data["session"]["mood_history"][-50:]
        self._save()

    def get_recent_moods(self, count: int = 5) -> list[dict]:
        """Return last N mood entries."""
        return self.data["session"]["mood_history"][-count:]

    def log_conversation_summary(self, summary: str):
        """Store a brief summary of a conversation session."""
        entry = {
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        }
        self.data["conversation_log"].append(entry)
        self.data["conversation_log"] = self.data["conversation_log"][-20:]
        self._save()

    def get_conversation_log(self) -> list[dict]:
        """Return all stored conversation summaries."""
        return self.data["conversation_log"]

    def build_memory_context(self) -> str:
        """Build a memory injection string for the system prompt."""
        parts = []

        if self.is_returning_user():
            name = self.get_user_name()
            parts.append(f"This is a RETURNING user. Their name is {name}. Greet them warmly.")
        else:
            parts.append("This is a NEW user. You don't know their name yet. Ask for it naturally.")

        profile = self.get_profile()
        profile_parts = []
        for key, val in profile.items():
            if val and key != "name":  
                profile_parts.append(f"{key}: {val}")
        if profile_parts:
            parts.append("User profile: " + "; ".join(profile_parts))

        facts = self.get_facts()
        if facts:
            parts.append("Known facts: " + "; ".join(facts[-10:]))

        prefs = self.data["user"].get("preferences", {})
        if prefs:
            pref_str = "; ".join(f"{k}: {v}" for k, v in list(prefs.items())[-10:])
            parts.append(f"Preferences: {pref_str}")

        session_count = self.get_session_count()
        if session_count > 1:
            parts.append(f"This is session #{session_count}.")

        last_active = self.get_last_active()
        if last_active:
            parts.append(f"Last session: {last_active}")

        recent_moods = self.get_recent_moods(3)
        if recent_moods:
            mood_str = ", ".join(m["mood"] for m in recent_moods)
            parts.append(f"Recent moods: {mood_str}")

        if not parts:
            return ""

        return "\n## MEMORY CONTEXT\n" + "\n".join(f"- {p}" for p in parts)

    def reset(self):
        """Clear all memory."""
        self.data = json.loads(json.dumps(DEFAULT_MEMORY))
        self._save()
