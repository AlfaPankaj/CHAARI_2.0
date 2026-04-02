# CHAARI 2.0 – core/ - Intent Parser
# Keyword-based intent classification from LLM responses
# Phase 1: Rule-based keyword matching
# Phase 3+: Upgrade to structured JSON outputs from LLM

import re


INTENT_MAP = {
    "open_app": {
        "patterns": [
            r"(?i)\b(open|launch|start|run)\s+(app|application|program|software|\w+\.exe)",
            r"(?i)\b(kholna|khol\s+do|chalu\s+karo)\b",
        ],
        "category": "system",
        "risk": "low",
    },
    "close_app": {
        "patterns": [
            r"(?i)\b(close|exit|quit|kill|stop)\s+(app|application|program|\w+\.exe)",
            r"(?i)\b(band\s+karo|band\s+kar\s+do)\b",
        ],
        "category": "system",
        "risk": "medium",
    },
    "delete_file": {
        "patterns": [
            r"(?i)\b(delete|remove|erase)\s+(file|folder|directory)",
            r"(?i)\b(file\s+delete|hatao|mita\s+do)\b",
        ],
        "category": "system",
        "risk": "destructive",
    },
    "create_file": {
        "patterns": [
            r"(?i)\b(create|make|new)\s+(file|folder|directory)",
            r"(?i)\b(banao|bana\s+do)\s+(file|folder)\b",
        ],
        "category": "system",
        "risk": "low",
    },
    "shutdown": {
        "patterns": [
            r"(?i)\b(shutdown|shut\s+down|restart|reboot|power\s+off)\b",
            r"(?i)\b(band\s+karo\s+pc|computer\s+off)\b",
        ],
        "category": "system",
        "risk": "destructive",
    },
    "browse_web": {
        "patterns": [
            r"(?i)\b(open|browse|go\s+to|visit)\s+(website|url|http|www|browser)",
            r"(?i)\b(google|search\s+for|search\s+karo)\b",
        ],
        "category": "system",
        "risk": "low",
    },

    "ask_time": {
        "patterns": [
            r"(?i)\b(what\s+time|kya\s+time|kitne\s+baje|time\s+batao)\b",
        ],
        "category": "info",
        "risk": "none",
    },
    "ask_system": {
        "patterns": [
            r"(?i)\b(cpu|ram|memory|disk|system\s+status|battery)\b",
        ],
        "category": "info",
        "risk": "none",
    },

    "greeting": {
        "patterns": [
            r"(?i)^(hi|hello|hey|namaste|kya\s+haal|good\s+morning|good\s+evening)\b",
        ],
        "category": "conversation",
        "risk": "none",
    },
    "farewell": {
        "patterns": [
            r"(?i)\b(bye|goodbye|see\s+you|alvida|chal\s+bye|tata)\b",
        ],
        "category": "conversation",
        "risk": "none",
    },
    "gratitude": {
        "patterns": [
            r"(?i)\b(thank|thanks|shukriya|dhanyavaad)\b",
        ],
        "category": "conversation",
        "risk": "none",
    },
}


class IntentParser:
    """
    Rule-based intent parser.
    Classifies user input into intents using keyword matching.
    Does NOT use LLM for classification (by design).
    """

    def __init__(self):
        self._compiled = {}
        for intent_name, intent_def in INTENT_MAP.items():
            self._compiled[intent_name] = {
                "patterns": [re.compile(p) for p in intent_def["patterns"]],
                "category": intent_def["category"],
                "risk": intent_def["risk"],
            }

    def parse_intent(self, user_input: str) -> dict | None:
        """
        Parse user input and return detected intent.

        Returns:
            {
                "intent": str,         # Intent name
                "category": str,       # system, info, conversation
                "risk": str,           # none, low, medium, destructive
                "confidence": float,   # 0.0 to 1.0
            }
            or None if no intent detected.
        """
        text = user_input.strip()
        if not text:
            return None

        best_match = None
        best_score = 0

        for intent_name, intent_def in self._compiled.items():
            matches = sum(1 for p in intent_def["patterns"] if p.search(text))
            if matches > 0:
                confidence = min(1.0, 0.6 + (matches * 0.2))
                if confidence > best_score:
                    best_score = confidence
                    best_match = {
                        "intent": intent_name,
                        "category": intent_def["category"],
                        "risk": intent_def["risk"],
                        "confidence": confidence,
                    }

        return best_match

    def is_destructive(self, intent_result: dict | None) -> bool:
        """Check if a parsed intent is destructive."""
        if intent_result is None:
            return False
        return intent_result["risk"] == "destructive"

    def is_system_action(self, intent_result: dict | None) -> bool:
        """Check if a parsed intent is a system action."""
        if intent_result is None:
            return False
        return intent_result["category"] == "system"

    def requires_confirmation(self, intent_result: dict | None) -> bool:
        """Check if intent needs user confirmation before execution."""
        if intent_result is None:
            return False
        return intent_result["risk"] in ("medium", "destructive")
