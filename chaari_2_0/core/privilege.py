# CHAARI 2.0 – core/privilege.py — Layer 2.6: PrivilegeManager
# Manages creator privilege mode.
#
# Responsibilities:
#    Activate / deactivate creator mode via passphrase challenge
#    Auto-expire creator sessions after timeout
#    Expose privilege state to Brain and Safety layers
#    Log all privilege events
#
# Must NEVER:
#    Store the passphrase in plaintext — uses PBKDF2 hash comparison
#    Execute OS actions
#    Modify safety thresholds directly
#    Disable the SafetyKernel

import hashlib
import hmac
import json
import os
import threading
from datetime import datetime
from dataclasses import dataclass




CREATOR_SESSION_TTL = 300        
MAX_AUTH_ATTEMPTS   = 5          
LOCKOUT_DURATION    = 600        

LOG_DIR            = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
PRIVILEGE_LOG_PATH = os.path.join(LOG_DIR, "privilege_audit.jsonl")

_PBKDF2_SALT = b"chaari_creator_salt_v1"
_PBKDF2_ITERATIONS = 260_000



@dataclass
class PrivilegeState:
    """
    Snapshot of current privilege state.
    Safety layer reads this via evaluate_privilege(intent, privilege_state).
    Brain layer reads this to decide UI flow.
    """
    creator_mode_active: bool
    activated_at:        float | None   
    expires_at:          float | None   
    session_id:          str  | None


@dataclass
class PrivilegeResult:
    """Result contract returned to Brain after an auth attempt."""
    success:       bool
    reason:        str   
    creator_mode_active: bool
    lockout_remaining:   int  = 0   
    expires_in:          int  = 0   



class PrivilegeManager:
    """
    Layer 2.6 — Creator privilege gatekeeper.

    Brain workflow (creator mode activation):
        1. User says something that triggers Tier 4
        2. Safety returns SafetyResult(creator_only=True, blocked=True)
        3. Brain calls: result = privilege.activate(passphrase, session_id)
        4. If result.success → Brain calls Safety.evaluate_privilege() again
           → now creator_mode_active=True → Safety allows with confirmation

    Brain workflow (creator mode deactivation):
        privilege.deactivate(session_id)

    Note: passphrase is NEVER stored — only its PBKDF2 hash is kept in memory.
          On restart, call set_passphrase_hash() to reload from your secrets store.
    """

    def __init__(self):
        self._lock            = threading.Lock()
        self._passphrase_hash: bytes | None   = None  

        self._active_session_id: str | None   = None
        self._activated_at:      float | None = None
        self._expires_at:        float | None = None

        self._failed_attempts:   int          = 0
        self._lockout_until:     float        = 0.0

        os.makedirs(LOG_DIR, exist_ok=True)

    def set_passphrase_hash(self, passphrase_hash: bytes):
        """
        Load the pre-computed PBKDF2 hash of the creator passphrase.
        Call this during app init — load the hash from your secrets manager.
        Never pass the raw passphrase to this method.

        To generate the hash at setup time (run once, store the result):
            from privilege import PrivilegeManager
            h = PrivilegeManager.hash_passphrase("your-secret-passphrase")
            # Store h (bytes) in your secrets manager
        """
        with self._lock:
            self._passphrase_hash = passphrase_hash

    @staticmethod
    def hash_passphrase(passphrase: str) -> bytes:
        """
        One-way hash a passphrase using PBKDF2-HMAC-SHA256.
        Use this once during setup to generate the stored hash.
        Never call this on every auth attempt — use _verify_passphrase() instead.
        """
        return hashlib.pbkdf2_hmac(
            "sha256",
            passphrase.encode("utf-8"),
            _PBKDF2_SALT,
            _PBKDF2_ITERATIONS,
        )

    def activate(self, passphrase: str, session_id: str = "__default__") -> PrivilegeResult:
        """
        Attempt to activate creator mode for the given session.

        Args:
            passphrase:  Raw passphrase from user (compared via constant-time hash)
            session_id:  Current session identifier

        Returns:
            PrivilegeResult — Brain reads .success and .reason
        """
        now = datetime.now().timestamp()

        with self._lock:
            if now < self._lockout_until:
                remaining = int(self._lockout_until - now)
                self._log("ACTIVATE_BLOCKED", session_id, reason=f"locked_out_{remaining}s")
                return PrivilegeResult(
                    success=False, reason="locked_out",
                    creator_mode_active=False,
                    lockout_remaining=remaining,
                )

            if self._active_session_id and now < (self._expires_at or 0):
                self._log("ACTIVATE_SKIPPED", session_id, reason="already_active")
                return PrivilegeResult(
                    success=True, reason="already_active",
                    creator_mode_active=True,
                    expires_in=int((self._expires_at or now) - now),
                )

            if self._passphrase_hash is None:
                self._log("ACTIVATE_FAILED", session_id, reason="passphrase_not_configured")
                return PrivilegeResult(
                    success=False, reason="not_configured",
                    creator_mode_active=False,
                )

            if not self._verify_passphrase(passphrase):
                self._failed_attempts += 1
                if self._failed_attempts >= MAX_AUTH_ATTEMPTS:
                    self._lockout_until = now + LOCKOUT_DURATION
                    self._failed_attempts = 0
                    self._log("LOCKED_OUT", session_id, reason="too_many_failed_attempts")
                    return PrivilegeResult(
                        success=False, reason="locked_out",
                        creator_mode_active=False,
                        lockout_remaining=LOCKOUT_DURATION,
                    )
                self._log("ACTIVATE_FAILED", session_id, reason=f"wrong_passphrase_attempt_{self._failed_attempts}")
                return PrivilegeResult(
                    success=False, reason="wrong_passphrase",
                    creator_mode_active=False,
                )

            self._failed_attempts    = 0
            self._active_session_id  = session_id
            self._activated_at       = now
            self._expires_at         = now + CREATOR_SESSION_TTL

        self._log("ACTIVATED", session_id, reason="passphrase_accepted")
        return PrivilegeResult(
            success=True, reason="ok",
            creator_mode_active=True,
            expires_in=CREATOR_SESSION_TTL,
        )

    def deactivate(self, session_id: str = "__default__") -> PrivilegeResult:
        """Explicitly end creator mode."""
        with self._lock:
            if self._active_session_id != session_id:
                return PrivilegeResult(
                    success=False, reason="not_active",
                    creator_mode_active=False,
                )
            self._clear_session()

        self._log("DEACTIVATED", session_id, reason="explicit_deactivate")
        return PrivilegeResult(success=True, reason="ok", creator_mode_active=False)

    def get_state(self, session_id: str = "__default__") -> PrivilegeState:
        """
        Return current privilege state snapshot.
        Safety.evaluate_privilege() accepts this object.
        """
        now = datetime.now().timestamp()
        with self._lock:
            if self._active_session_id and self._expires_at and now >= self._expires_at:
                prev_session = self._active_session_id
                self._clear_session()
                self._log("AUTO_EXPIRED", prev_session, reason="ttl_exceeded")
                return PrivilegeState(
                    creator_mode_active=False,
                    activated_at=None,
                    expires_at=None,
                    session_id=None,
                )

            active = (
                self._active_session_id == session_id
                and self._expires_at is not None
                and now < self._expires_at
            )
            return PrivilegeState(
                creator_mode_active=active,
                activated_at=self._activated_at if active else None,
                expires_at=self._expires_at   if active else None,
                session_id=self._active_session_id if active else None,
            )

    def get_status(self) -> dict:
        """Return a safe status dict (no secrets exposed)."""
        now = datetime.now().timestamp()
        with self._lock:
            active = (
                self._active_session_id is not None
                and self._expires_at is not None
                and now < self._expires_at
            )
            return {
                "creator_mode_active": active,
                "session_id":          self._active_session_id if active else None,
                "expires_in_seconds":  int(self._expires_at - now) if active and self._expires_at else 0,
                "failed_attempts":     self._failed_attempts,
                "locked_out":          now < self._lockout_until,
                "lockout_remaining":   max(0, int(self._lockout_until - now)),
            }

    def _verify_passphrase(self, passphrase: str) -> bool:
        """Constant-time PBKDF2 comparison — prevents timing attacks."""
        candidate_hash = hashlib.pbkdf2_hmac(
            "sha256",
            passphrase.encode("utf-8"),
            _PBKDF2_SALT,
            _PBKDF2_ITERATIONS,
        )
        return hmac.compare_digest(candidate_hash, self._passphrase_hash)  

    def _clear_session(self):
        """Called inside lock."""
        self._active_session_id = None
        self._activated_at      = None
        self._expires_at        = None

    def _log(self, action: str, session_id: str, reason: str = ""):
        entry = {
            "timestamp":  datetime.now().isoformat(),
            "action":     action,
            "session_id": session_id,
            "reason":     reason,
        }
        try:
            with open(PRIVILEGE_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
