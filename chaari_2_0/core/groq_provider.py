# CHAARI 2.0 – core/ - Groq LLM Provider
# Fast cloud LLM via Groq API with automatic daily limit tracking.
# When Groq daily quota is exhausted, signals Brain to fallback to Ollama.

import os
import json
import time
import threading
from datetime import datetime, date
from typing import Generator, Optional

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False



GROQ_MODEL = "llama-3.1-8b-instant"       
GROQ_MODEL_FALLBACK = "llama3-8b-8192"     

DAILY_REQUEST_LIMIT = 14400    
RATE_LIMIT_RPM = 30            

_TRACKING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_TRACKING_FILE = os.path.join(_TRACKING_DIR, "groq_usage.json")
os.makedirs(_TRACKING_DIR, exist_ok=True)



class GroqUsageTracker:
    """Tracks daily Groq API usage to know when to fallback to Ollama."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        try:
            if os.path.exists(_TRACKING_FILE):
                with open(_TRACKING_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"date": str(date.today()), "count": 0}

    def _save(self):
        try:
            with open(_TRACKING_FILE, 'w') as f:
                json.dump(self._data, f)
        except Exception:
            pass

    def _reset_if_new_day(self):
        today = str(date.today())
        if self._data.get("date") != today:
            self._data = {"date": today, "count": 0}

    def increment(self):
        with self._lock:
            self._reset_if_new_day()
            self._data["count"] += 1
            self._save()

    def get_count(self) -> int:
        with self._lock:
            self._reset_if_new_day()
            return self._data.get("count", 0)

    def remaining(self) -> int:
        return max(0, DAILY_REQUEST_LIMIT - self.get_count())

    def is_limit_reached(self) -> bool:
        return self.get_count() >= DAILY_REQUEST_LIMIT



class GroqProvider:
    """Groq API provider for fast LLM inference.
    
    Usage:
        provider = GroqProvider()
        if provider.is_available():
            response = provider.chat(messages)
            # or streaming:
            for token in provider.chat_stream(messages):
                print(token)
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self._client = None
        self._model = GROQ_MODEL
        self._tracker = GroqUsageTracker()
        self._rate_limited = False
        self._rate_limit_until = 0.0

        if GROQ_AVAILABLE and self._api_key:
            try:
                self._client = Groq(api_key=self._api_key)
            except Exception:
                self._client = None

    def is_available(self) -> bool:
        """Check if Groq can be used right now (has key + not at daily limit)."""
        if not self._client:
            return False
        if self._tracker.is_limit_reached():
            return False
        if self._rate_limited and time.time() < self._rate_limit_until:
            return False
        return True

    def get_status(self) -> dict:
        """Return current Groq status for display."""
        return {
            "available": self.is_available(),
            "has_key": bool(self._api_key),
            "sdk_installed": GROQ_AVAILABLE,
            "model": self._model,
            "today_used": self._tracker.get_count(),
            "today_remaining": self._tracker.remaining(),
            "daily_limit": DAILY_REQUEST_LIMIT,
            "rate_limited": self._rate_limited,
        }

    def chat(self, messages: list[dict], max_tokens: int = 150, temperature: float = 0.7) -> Optional[str]:
        """Non-streaming chat. Returns response text or None on failure."""
        if not self.is_available():
            return None

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False,
            )
            self._tracker.increment()
            self._rate_limited = False
            return response.choices[0].message.content.strip()

        except Exception as e:
            return self._handle_error(e)

    def chat_stream(self, messages: list[dict], max_tokens: int = 150, temperature: float = 0.7) -> Generator[str, None, None]:
        """Streaming chat. Yields tokens. Empty on failure."""
        if not self.is_available():
            return

        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            self._tracker.increment()
            self._rate_limited = False

            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content

        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, e: Exception) -> None:
        """Handle Groq API errors — detect rate limits and quota exhaustion."""
        err_str = str(e).lower()
        if "rate_limit" in err_str or "429" in err_str:
            self._rate_limited = True
            self._rate_limit_until = time.time() + 60  
        if "quota" in err_str or "limit" in err_str:
            self._tracker._data["count"] = DAILY_REQUEST_LIMIT
            self._tracker._save()
        return None
