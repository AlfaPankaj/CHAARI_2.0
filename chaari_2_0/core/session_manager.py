# CHAARI 2.0 — core/session_manager.py — Layer 2.7: SessionManager
# Responsibility: Track session state across requests

# Manages:
#   • Strike count (abuse detection)
#   • Confirmation state (pending codes)
#   • Creator mode state & privilege tokens
#   • Rate limiting
#   • Session lifecycle

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict



MAX_STRIKES = 5  
STRIKE_RESET_MINUTES = 15  
RATE_LIMIT_WINDOW = 5.0  
RATE_LIMIT_MAX_REQUESTS = 10  
PRIVILEGE_TOKEN_TTL_MINUTES = 10  



@dataclass
class Session:
    """Complete session state."""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    
    strike_count: int = 0
    max_strikes: int = MAX_STRIKES
    strike_reset_time: Optional[datetime] = None
    
    active_confirmation_token: Optional[str] = None
    confirmation_intent: Optional[str] = None
    confirmation_created_at: Optional[datetime] = None
    
    creator_mode_active: bool = False
    privilege_token: Optional[str] = None
    privilege_expires_at: Optional[datetime] = None
    
    request_count: int = 0
    rate_limit_window_start: datetime = field(default_factory=datetime.now)
    
    conversation_history: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize defaults after creation."""
        if not self.rate_limit_window_start:
            self.rate_limit_window_start = datetime.now()


class SessionManager:
    """
    Layer 2.7 — Session state tracker.
    
    Maintains session-specific state across requests:
    - Strike counting for abuse detection
    - Confirmation token management
    - Creator mode state
    - Rate limiting
    """
    
    def __init__(self):
        """Initialize session manager."""
        self._lock: threading.Lock = threading.Lock()
        self._sessions: dict[str, Session] = {} 
    
    def create_session(self, session_id: str, user_id: str = "unknown") -> Session:
        """
        Create a new session.
        
        Args:
            session_id: Unique session identifier
            user_id: User identifier (for multi-user scenarios)
            
        Returns:
            Session object
        """
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
            
            session = Session(
                session_id=session_id,
                user_id=user_id,
                created_at=datetime.now(),
                last_activity=datetime.now(),
            )
            self._sessions[session_id] = session
            return session
    
    def get_session(self, session_id: str) -> Session:
        """
        Get or create a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session object (creates if doesn't exist)
        """
        with self._lock:
            if session_id not in self._sessions:
                return self.create_session(session_id)
            return self._sessions[session_id]
    
    def update_activity(self, session_id: str):
        """Update last activity timestamp."""
        session = self.get_session(session_id)
        with self._lock:
            session.last_activity = datetime.now()
    
    def increment_strike(self, session_id: str) -> int:
        """
        Add a strike (abuse detection).
        
        Returns:
            Current strike count after increment
        """
        session = self.get_session(session_id)
        with self._lock:
            if session.strike_reset_time and datetime.now() > session.strike_reset_time:
                session.strike_count = 0
                session.strike_reset_time = None
            
            session.strike_count += 1
            
            if session.strike_count == 1:
                session.strike_reset_time = datetime.now() + timedelta(minutes=STRIKE_RESET_MINUTES)
            
            return session.strike_count
    
    def get_strike_count(self, session_id: str) -> int:
        """Get current strike count."""
        session = self.get_session(session_id)
        with self._lock:
            if session.strike_reset_time and datetime.now() > session.strike_reset_time:
                session.strike_count = 0
                session.strike_reset_time = None
            return session.strike_count
    
    def reset_strikes(self, session_id: str):
        """Reset strike count (for admins/creators)."""
        session = self.get_session(session_id)
        with self._lock:
            session.strike_count = 0
            session.strike_reset_time = None
    
    def is_strike_locked(self, session_id: str) -> bool:
        """Check if session is strike-locked (hit max strikes)."""
        session = self.get_session(session_id)
        with self._lock:
            if session.strike_reset_time and datetime.now() > session.strike_reset_time:
                session.strike_count = 0
                session.strike_reset_time = None
            return session.strike_count >= session.max_strikes
    
    def set_active_confirmation(
        self, 
        session_id: str, 
        confirmation_token: str, 
        intent: str
    ) -> None:
        """
        Set an active confirmation (waiting for user code submission).
        
        Args:
            session_id: Session ID
            confirmation_token: Token issued by ConfirmationEngine
            intent: The intent being confirmed
        """
        session = self.get_session(session_id)
        with self._lock:
            session.active_confirmation_token = confirmation_token
            session.confirmation_intent = intent
            session.confirmation_created_at = datetime.now()
    
    def get_active_confirmation(self, session_id: str) -> tuple[Optional[str], Optional[str]]:
        """
        Get active confirmation details.
        
        Returns:
            (confirmation_token, intent) or (None, None)
        """
        session = self.get_session(session_id)
        with self._lock:
            return (session.active_confirmation_token, session.confirmation_intent)
    
    def clear_confirmation(self, session_id: str) -> None:
        """Clear active confirmation (after success or cancel)."""
        session = self.get_session(session_id)
        with self._lock:
            session.active_confirmation_token = None
            session.confirmation_intent = None
            session.confirmation_created_at = None
    
    def has_active_confirmation(self, session_id: str) -> bool:
        """Check if session has pending confirmation."""
        session = self.get_session(session_id)
        with self._lock:
            return session.active_confirmation_token is not None
       
    def enable_creator_mode(self, session_id: str, privilege_token: str) -> bool:
        """
        Enable creator mode with privilege token.
        
        Args:
            session_id: Session ID
            privilege_token: Token issued by PrivilegeManager
            
        Returns:
            True if enabled, False if already active
        """
        session = self.get_session(session_id)
        with self._lock:
            if session.creator_mode_active:
                return False  
            
            session.creator_mode_active = True
            session.privilege_token = privilege_token
            session.privilege_expires_at = datetime.now() + timedelta(minutes=PRIVILEGE_TOKEN_TTL_MINUTES)
            return True
    
    def is_creator_mode_active(self, session_id: str) -> bool:
        """
        Check if creator mode is active and not expired.
        
        Returns:
            True if active and valid, False otherwise
        """
        session = self.get_session(session_id)
        with self._lock:
            if not session.creator_mode_active:
                return False
            
            if session.privilege_expires_at and datetime.now() > session.privilege_expires_at:
                session.creator_mode_active = False
                session.privilege_token = None
                session.privilege_expires_at = None
                return False
            
            return True
    
    def get_privilege_token(self, session_id: str) -> Optional[str]:
        """Get privilege token (if creator mode active)."""
        if self.is_creator_mode_active(session_id):
            session = self.get_session(session_id)
            with self._lock:
                return session.privilege_token
        return None
    
    def disable_creator_mode(self, session_id: str) -> None:
        """Disable creator mode."""
        session = self.get_session(session_id)
        with self._lock:
            session.creator_mode_active = False
            session.privilege_token = None
            session.privilege_expires_at = None
    
    def get_creator_mode_ttl(self, session_id: str) -> Optional[int]:
        """Get remaining seconds until creator mode expires."""
        if not self.is_creator_mode_active(session_id):
            return None
        
        session = self.get_session(session_id)
        with self._lock:
            if not session.privilege_expires_at:
                return None
            
            remaining = (session.privilege_expires_at - datetime.now()).total_seconds()
            return max(0, int(remaining))
    
    def check_rate_limit(self, session_id: str) -> bool:
        """
        Check if session is rate-limited.
        
        Returns:
            True if rate-limited, False if allowed
        """
        session = self.get_session(session_id)
        now = datetime.now()
        
        with self._lock:
            window_age = (now - session.rate_limit_window_start).total_seconds()
            if window_age > RATE_LIMIT_WINDOW:
                session.request_count = 1
                session.rate_limit_window_start = now
                return False
            
            session.request_count += 1
            
            return session.request_count > RATE_LIMIT_MAX_REQUESTS
    
    def reset_rate_limit(self, session_id: str) -> None:
        """Reset rate limit counter."""
        session = self.get_session(session_id)
        with self._lock:
            session.request_count = 0
            session.rate_limit_window_start = datetime.now()
    
    def get_request_count(self, session_id: str) -> int:
        """Get current request count in window."""
        session = self.get_session(session_id)
        with self._lock:
            return session.request_count
     
    def add_conversation_message(self, session_id: str, role: str, content: str) -> None:
        """Add message to session history."""
        session = self.get_session(session_id)
        with self._lock:
            session.conversation_history.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            })
    
    def get_conversation_history(self, session_id: str, limit: int = 50) -> list[dict]:
        """Get recent conversation history."""
        session = self.get_session(session_id)
        with self._lock:
            return session.conversation_history[-limit:]
    
    def clear_conversation_history(self, session_id: str) -> None:
        """Clear conversation history."""
        session = self.get_session(session_id)
        with self._lock:
            session.conversation_history.clear()
    
    def set_metadata(self, session_id: str, key: str, value) -> None:
        """Set session metadata."""
        session = self.get_session(session_id)
        with self._lock:
            session.metadata[key] = value
    
    def get_metadata(self, session_id: str, key: str, default=None):
        """Get session metadata."""
        session = self.get_session(session_id)
        with self._lock:
            return session.metadata.get(key, default)
    
    def get_session_status(self, session_id: str) -> dict:
        """Get complete session status (for debugging)."""
        session = self.get_session(session_id)
        with self._lock:
            return {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "strike_count": session.strike_count,
                "max_strikes": session.max_strikes,
                "strikes_locked": session.strike_count >= session.max_strikes,
                "active_confirmation": session.active_confirmation_token is not None,
                "creator_mode_active": session.creator_mode_active,
                "privilege_ttl_seconds": self.get_creator_mode_ttl(session_id),
                "request_count": session.request_count,
                "conversation_messages": len(session.conversation_history),
            }
