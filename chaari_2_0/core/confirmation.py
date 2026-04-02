# CHAARI 2.0 – core/confirmation.py — Layer 2.5: ConfirmationEngine
# ══════════════════════════════════════════════════════════════════
# Manages one-time confirmation codes for Tier 3 (destructive) actions.
#
# Responsibilities:
#    Generate short, time-limited confirmation codes
#    Validate submitted codes
#    Expire codes after timeout
#    Enforce single-use (code invalidated after first successful verify)
#    Log all generate / verify / expire events
#
# Must NEVER:
#    Execute the action — it only validates clearance
#    Store creator credentials — that's PrivilegeManager
#    Modify safety thresholds
# ══════════════════════════════════════════════════════════════════

import json
import os
import random
import string
import threading
from datetime import datetime
from dataclasses import dataclass, field



CODE_TTL_SECONDS  = 120       
CODE_LENGTH       = 8         
MAX_ATTEMPTS      = 3         

LOG_DIR           = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
CONFIRM_LOG_PATH  = os.path.join(LOG_DIR, "confirmation_audit.jsonl")



INTENT_PREFIXES: dict[str, str] = {
    "shutdown":       "SHD",
    "restart":        "RST",
    "delete_file":    "DEL",
    "format_disk":    "FMT",
    "kill_process":   "KIL",
    "modify_registry":"REG",
    "open_app":       "OPN",
    "close_app":      "CLS",
    "create_file":    "CRT",
    "copy_file":      "CPY",
    "move_file":      "MOV",
    "minimize_app":   "MIN",
    "maximize_app":   "MAX",
    "restore_app":    "RSR",
    "type_text":      "TYP",
    "send_message":   "MSG",
    "make_call":      "CAL",
}
DEFAULT_PREFIX = "ACT"


@dataclass
class _PendingCode:
    code:           str
    intent:         str
    session_id:     str
    created_at:     float       
    expires_at:     float       
    attempts:       int   = 0
    used:           bool  = False
    voided:         bool  = False   


@dataclass
class ConfirmationResult:
    """Result contract returned to Brain layer after a verify attempt."""
    valid:      bool
    reason:     str         
    intent:     str | None
    session_id: str | None
    attempts_remaining: int = 0



class ConfirmationEngine:
    """
    Layer 2.5 — One-time code manager for Tier 3 destructive actions.

    Brain workflow:
        1. Safety returns SafetyResult(tier=3, requires_code=True)
        2. Brain calls: token = engine.generate(intent, session_id)
        3. Brain presents token to user and asks for confirmation
        4. User submits code
        5. Brain calls: result = engine.verify(token, submitted_code)
        6. If result.valid → proceed with action
    """

    def __init__(self):
        self._lock:    threading.Lock              = threading.Lock()
        self._pending: dict[str, _PendingCode]    = {}  
        self._current_token: str | None            = None  
        os.makedirs(LOG_DIR, exist_ok=True)

    def has_pending(self) -> bool:
        """Check if there's a pending confirmation waiting for input."""
        with self._lock:
            return self._current_token is not None

    def get_pending_token(self) -> str | None:
        """Get the current pending token (for displaying to user after wrong code)."""
        with self._lock:
            return self._current_token

    def verify_pending(self, submitted_code: str, session_id: str = "__default__") -> tuple[bool, str | None]:
        """
        Convenience method: Verify submitted code against the current pending token.
        
        Args:
            submitted_code: The code the user submitted
            session_id: Session identifier
            
        Returns:
            (verified: bool, intent: str | None)
        """
        with self._lock:
            token = self._current_token
            if not token:
                return False, None
        
        result = self.verify(token, submitted_code, session_id)
        
        if result.valid:
            with self._lock:
                self._current_token = None
        
        return result.valid, result.intent if result.valid else None

    def request(self, intent: str, requires_code: bool = True, session_id: str = "__default__") -> str:
        """
        Request confirmation for an action.
        
        Args:
            intent: The action intent (e.g. "shutdown", "delete_file")
            requires_code: Whether a confirmation code is required
            session_id: Session identifier
            
        Returns:
            Message to display to user asking for confirmation
        """
        token = self.generate(intent, session_id)
        
        with self._lock:
            self._current_token = token
        
        if requires_code:
            return f"⚠️ This action requires confirmation. Please type the code: {token}"
        else:
            return f"⚠️ Please confirm this action: {intent}"

    def verify(self, submitted_code: str, session_id: str = "__default__") -> tuple[bool, str | None]:
        """
        Verify a submitted confirmation code (for pending confirmations).
        
        Args:
            submitted_code: The code/response submitted by user
            session_id: Session identifier
            
        Returns:
            (verified: bool, intent: str | None)
        """
        with self._lock:
            token = self._current_token
            if not token:
                return False, None
            
            entry = self._pending.get(token)
            if not entry:
                return False, None
        
        now = datetime.now().timestamp()
        
        with self._lock:
            entry = self._pending.get(token)
            
            if entry is None:
                self._current_token = None
                return False, None
            
            if entry.session_id != session_id:
                self._current_token = None
                return False, None
            
            if entry.used:
                self._current_token = None
                return False, None
            
            if entry.voided:
                self._current_token = None
                return False, None
            
            if now > entry.expires_at:
                self._expire(token, entry)
                self._current_token = None
                return False, None
            
            user_code = submitted_code.strip()
            if user_code != entry.code and user_code != token:
                entry.attempts += 1
                if entry.attempts >= MAX_ATTEMPTS:
                    entry.voided = True
                    self._log("VOIDED", token, entry.intent, session_id, reason="too_many_wrong_attempts")
                    self._current_token = None
                return False, None
            
            entry.used = True
            intent = entry.intent
            del self._pending[token]
            self._current_token = None
        
        self._log("VERIFIED", token, intent, session_id, reason="code_accepted")
        return True, intent

    def generate(self, intent: str, session_id: str = "__default__") -> str:
        """
        Generate a one-time confirmation code for the given intent.

        Returns:
            token (str) — a unique request ID (e.g. "SHD-48219-XQ3")
                          This is what Brain presents to the user.

        The user must read back / type back the numeric portion to confirm.
        """
        now        = datetime.now().timestamp()
        prefix     = INTENT_PREFIXES.get(intent, DEFAULT_PREFIX)
        digits     = "".join(random.choices(string.digits, k=5))
        suffix     = "".join(random.choices(string.ascii_uppercase, k=3))
        code       = digits                         
        token      = f"{prefix}-{digits}-{suffix}"  

        entry = _PendingCode(
            code=code,
            intent=intent,
            session_id=session_id,
            created_at=now,
            expires_at=now + CODE_TTL_SECONDS,
        )

        with self._lock:
            self._void_existing(session_id, intent)
            self._pending[token] = entry

        self._log("GENERATED", token, intent, session_id, reason="new_code")
        return token

    def verify(self, token: str, submitted_code: str, session_id: str = "__default__") -> ConfirmationResult:
        """
        Verify a submitted code against the pending token.

        Args:
            token:          The full token (e.g. "SHD-48219-XQ3") Brain received from generate()
            submitted_code: What the user typed (should match the digit portion)
            session_id:     Must match the session that requested the code

        Returns:
            ConfirmationResult — Brain reads .valid to decide whether to proceed
        """
        now = datetime.now().timestamp()

        with self._lock:
            entry = self._pending.get(token)

            if entry is None:
                return ConfirmationResult(valid=False, reason="not_found", intent=None, session_id=None)

            if entry.session_id != session_id:
                return ConfirmationResult(valid=False, reason="not_found", intent=entry.intent, session_id=session_id)

            if entry.used:
                return ConfirmationResult(valid=False, reason="already_used", intent=entry.intent, session_id=session_id)

            if entry.voided:
                return ConfirmationResult(valid=False, reason="voided", intent=entry.intent,
                                          session_id=session_id, attempts_remaining=0)

            if now > entry.expires_at:
                self._expire(token, entry)
                return ConfirmationResult(valid=False, reason="expired", intent=entry.intent, session_id=session_id)

            user_code = submitted_code.strip()
            if user_code != entry.code and user_code != token:
                entry.attempts += 1
                remaining = MAX_ATTEMPTS - entry.attempts
                if entry.attempts >= MAX_ATTEMPTS:
                    entry.voided = True
                    self._log("VOIDED", token, entry.intent, session_id, reason="too_many_wrong_attempts")
                    return ConfirmationResult(valid=False, reason="voided", intent=entry.intent,
                                              session_id=session_id, attempts_remaining=0)
                self._log("WRONG_CODE", token, entry.intent, session_id, reason=f"attempt_{entry.attempts} submitted='{user_code}' expected='{entry.code}'")
                return ConfirmationResult(valid=False, reason="wrong_code", intent=entry.intent,
                                          session_id=session_id, attempts_remaining=remaining)

            entry.used = True
            del self._pending[token]  

        self._log("VERIFIED", token, entry.intent, session_id, reason="code_accepted")
        return ConfirmationResult(valid=True, reason="ok", intent=entry.intent, session_id=session_id)

    def cancel(self, token: str, session_id: str = "__default__"):
        """Explicitly cancel a pending confirmation (e.g. user said 'never mind')."""
        with self._lock:
            entry = self._pending.pop(token, None)
            if self._current_token == token:
                self._current_token = None
        if entry:
            self._log("CANCELLED", token, entry.intent, session_id, reason="user_cancelled")

    def purge_expired(self):
        """Remove all expired codes. Call periodically (e.g. from a background thread)."""
        now = datetime.now().timestamp()
        with self._lock:
            expired_tokens = [t for t, e in self._pending.items() if now > e.expires_at]
            for t in expired_tokens:
                entry = self._pending.pop(t)
                self._log("EXPIRED", t, entry.intent, entry.session_id, reason="ttl_exceeded")

    def _void_existing(self, session_id: str, intent: str):
        """Called inside lock. Voids any prior code for same session+intent."""
        to_void = [
            t for t, e in self._pending.items()
            if e.session_id == session_id and e.intent == intent and not e.used
        ]
        for t in to_void:
            self._pending[t].voided = True

    def _expire(self, token: str, entry: _PendingCode):
        """Called inside lock."""
        self._pending.pop(token, None)

    def _log(self, action: str, token: str, intent: str | None, session_id: str, reason: str = ""):
        entry = {
            "timestamp":  datetime.now().isoformat(),
            "action":     action,
            "token":      token,
            "intent":     intent,
            "session_id": session_id,
            "reason":     reason,
        }
        try:
            with open(CONFIRM_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
