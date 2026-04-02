# CHAARI 2.0 — Dell crypto/nonce_store.py — Dell-side Nonce Tracking
# ═══════════════════════════════════════════════════════════
# Identical logic to ASUS nonce_store but Dell-specific instance.
# Tracks nonces of incoming commands to prevent replay attacks.
# ═══════════════════════════════════════════════════════════

import threading
import time
from datetime import datetime, timezone
from collections import OrderedDict


TIMESTAMP_WINDOW_SECONDS = 60
NONCE_TTL_SECONDS = 300
MAX_NONCES = 10000


class DellNonceStore:
    """Dell-side nonce tracker. Rejects replayed command packets."""

    def __init__(self, timestamp_window: int = None, nonce_ttl: int = None):
        self._lock = threading.Lock()
        self._seen: OrderedDict[str, float] = OrderedDict()
        self.timestamp_window = timestamp_window or TIMESTAMP_WINDOW_SECONDS
        self.nonce_ttl = nonce_ttl or NONCE_TTL_SECONDS

    def check_and_record(self, nonce: str) -> tuple[bool, str]:
        """Check nonce. Returns (is_new, reason)."""
        if not nonce or not nonce.strip():
            return False, "empty"
        now = time.time()
        with self._lock:
            if len(self._seen) >= MAX_NONCES:
                self._purge_expired(now)
            if nonce in self._seen:
                return False, "replay"
            self._seen[nonce] = now
            return True, "ok"

    def validate_timestamp(self, packet_timestamp: str) -> tuple[bool, str]:
        """Validate packet timestamp is within window."""
        try:
            packet_time = datetime.fromisoformat(packet_timestamp)
            if packet_time.tzinfo is None:
                packet_time = packet_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = (now - packet_time).total_seconds()
            if delta > self.timestamp_window:
                return False, "expired"
            if delta < -self.timestamp_window:
                return False, "future"
            return True, "ok"
        except (ValueError, TypeError):
            return False, "invalid"

    def validate_freshness(self, nonce: str, timestamp: str) -> tuple[bool, str]:
        """Combined nonce + timestamp check."""
        ts_ok, ts_reason = self.validate_timestamp(timestamp)
        if not ts_ok:
            return False, f"timestamp_{ts_reason}"
        nonce_ok, nonce_reason = self.check_and_record(nonce)
        if not nonce_ok:
            return False, f"nonce_{nonce_reason}"
        return True, "ok"

    def purge_expired(self) -> int:
        now = time.time()
        with self._lock:
            return self._purge_expired(now)

    def _purge_expired(self, now: float) -> int:
        cutoff = now - self.nonce_ttl
        purged = 0
        while self._seen:
            oldest_nonce, oldest_time = next(iter(self._seen.items()))
            if oldest_time < cutoff:
                del self._seen[oldest_nonce]
                purged += 1
            else:
                break
        return purged
