# CHAARI 2.0 — crypto/nonce_store.py — Nonce & Replay Protection
# Responsibility:
# Track used nonces (prevent replay attacks)
# Validate timestamp windows (±60 seconds)
# Auto-purge expired nonces
# Must NEVER:
# Sign/verify — that's signer.py
# Build packets — that's packet_builder.py

import threading
import time
from datetime import datetime, timezone
from collections import OrderedDict


TIMESTAMP_WINDOW_SECONDS = 60      
NONCE_TTL_SECONDS = 300             
MAX_NONCES = 10000          



class NonceStore:
    """
    Thread-safe nonce tracker for replay protection.
    
    Every command packet has a unique nonce (UUID).
    Once a nonce is seen, it's recorded.
    If the same nonce appears again → REPLAY ATTACK → reject.
    
    Also validates timestamp windows to prevent delayed replay.
    """

    def __init__(self, timestamp_window: int = None, nonce_ttl: int = None):
        self._lock = threading.Lock()
        self._seen: OrderedDict[str, float] = OrderedDict()
        self.timestamp_window = timestamp_window or TIMESTAMP_WINDOW_SECONDS
        self.nonce_ttl = nonce_ttl or NONCE_TTL_SECONDS

    def check_and_record(self, nonce: str) -> tuple[bool, str]:
        """
        Check if nonce has been seen before. If new, record it.
        
        Args:
            nonce: The packet nonce (UUID string)
            
        Returns:
            (is_valid, reason)
            - (True, "ok") — new nonce, recorded
            - (False, "replay") — nonce already seen
            - (False, "empty") — empty nonce
        """
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
        """
        Validate that packet timestamp is within acceptable window.
        
        Args:
            packet_timestamp: ISO-8601 timestamp string from packet
            
        Returns:
            (is_valid, reason)
            - (True, "ok") — within window
            - (False, "expired") — too old
            - (False, "future") — too far in the future
            - (False, "invalid") — can't parse timestamp
        """
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

    def validate_packet_freshness(self, nonce: str, timestamp: str) -> tuple[bool, str]:
        """
        Combined nonce + timestamp validation.
        
        Args:
            nonce: Packet nonce
            timestamp: Packet timestamp (ISO-8601)
            
        Returns:
            (is_valid, reason)
        """
        ts_valid, ts_reason = self.validate_timestamp(timestamp)
        if not ts_valid:
            return False, f"timestamp_{ts_reason}"

        nonce_valid, nonce_reason = self.check_and_record(nonce)
        if not nonce_valid:
            return False, f"nonce_{nonce_reason}"

        return True, "ok"

    def purge_expired(self) -> int:
        """
        Remove expired nonces. Call periodically.
        
        Returns:
            Number of nonces purged
        """
        now = time.time()
        with self._lock:
            return self._purge_expired(now)

    def get_stats(self) -> dict:
        """Get nonce store statistics."""
        with self._lock:
            return {
                "total_nonces": len(self._seen),
                "max_nonces": MAX_NONCES,
                "timestamp_window_seconds": self.timestamp_window,
                "nonce_ttl_seconds": self.nonce_ttl,
            }

    def _purge_expired(self, now: float) -> int:
        """Remove nonces older than TTL. Called inside lock."""
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
