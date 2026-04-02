# CHAARI 2.0 – config/ - Security Configuration
# API key authentication, CORS, network security
# NON-OPTIONAL when server runs on 0.0.0.0

import os
import secrets
import hashlib



API_KEY = os.environ.get("CHAARI_API_KEY", None)

if API_KEY is None:
    API_KEY = secrets.token_hex(32)
    _GENERATED = True
else:
    _GENERATED = False

API_KEY_HEADER = "X-API-Key"



ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
]

CORS_ALLOW_ALL = False

SERVER_HOST = "127.0.0.1"  

SERVER_PORT = 8000

MAX_REQUESTS_PER_MINUTE = 60


class SecurityGuard:
    """
    Handles API authentication and request validation.
    Must be used when server is exposed on network.
    """

    def __init__(self, api_key: str = API_KEY):
        self._api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        self._raw_key = api_key
        self._request_counts: dict[str, list] = {}

    def validate_api_key(self, provided_key: str) -> bool:
        """Validate an API key against the stored hash."""
        provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
        return provided_hash == self._api_key_hash

    def validate_origin(self, origin: str) -> bool:
        """Check if a request origin is allowed."""
        if CORS_ALLOW_ALL:
            return True
        return origin in ALLOWED_ORIGINS

    def get_cors_headers(self, origin: str = "") -> dict:
        """Return CORS headers for a response."""
        if CORS_ALLOW_ALL:
            allowed = "*"
        elif origin in ALLOWED_ORIGINS:
            allowed = origin
        else:
            allowed = ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else ""

        return {
            "Access-Control-Allow-Origin": allowed,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": f"Content-Type, {API_KEY_HEADER}",
            "Access-Control-Max-Age": "3600",
        }

    def get_api_key(self) -> str:
        """Return the raw API key (for display at boot only)."""
        return self._raw_key

    def is_network_exposed(self) -> bool:
        """Check if server is exposed beyond localhost."""
        return SERVER_HOST == "0.0.0.0"


def print_security_status():
    """Print security configuration at boot."""
    print(f"  [Security] Server: {SERVER_HOST}:{SERVER_PORT}")

    if SERVER_HOST == "0.0.0.0":
        print("  [Security] ⚠ Network exposed — API key REQUIRED")
        if _GENERATED:
            print(f"  [Security] Auto-generated API key: {API_KEY}")
            print("  [Security] Set CHAARI_API_KEY env var for a persistent key.")
        else:
            print("  [Security] API key loaded from environment.")
        print(f"  [Security] CORS: {'ALL (dev mode)' if CORS_ALLOW_ALL else 'Restricted'}")
    else:
        print("  [Security] Localhost only — safe mode.")
