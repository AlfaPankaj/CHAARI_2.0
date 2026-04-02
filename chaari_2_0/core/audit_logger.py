# CHAARI 2.0 — core/audit_logger.py — Layer 0.5: Audit Trail
# Responsibility: Append-only audit logging for all security events

# Logs ALL decisions made by:
#   • SafetyKernel (input checks, intent detection, tier assignment)
#   • PolicyEngine (governance decisions)
#   • ConfirmationEngine (code generation, verification)
#   • PrivilegeManager (creator mode activation)
#   • ExecutorPort (command execution results)
#   • SessionManager (strike tracking, rate limits)

# Design Principle: Tamper-resistant append-only logging
#    Never overwrites existing logs
#    All entries timestamped and trace-bound
#    Session-bound for forensic linking
#    JSON format for querying
#
# Must NEVER:
#    Delete entries
#    Modify existing entries
#    Leak sensitive data (passwords, codes) — logs code generation events ONLY

import json
import os
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Optional, Any
from collections import defaultdict



LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
AUDIT_LOG_PATH = os.path.join(LOG_DIR, "audit_trail.jsonl")

Path(LOG_DIR).mkdir(parents=True, exist_ok=True)



class AuditEventType(Enum):
    """Types of audit events."""
    INPUT_RECEIVED = "input_received"
    
    SAFETY_CHECK = "safety_check"
    INJECTION_DETECTED = "injection_detected"
    INTENT_CLASSIFIED = "intent_classified"
    TIER_ASSIGNED = "tier_assigned"
    
    CODE_GENERATED = "code_generated"
    CODE_VERIFIED_SUCCESS = "code_verified_success"
    CODE_VERIFIED_FAILED = "code_verified_failed"
    CODE_EXPIRED = "code_expired"
    CODE_ATTEMPT = "code_attempt"
    
    PRIVILEGE_CHECK = "privilege_check"
    CREATOR_MODE_ACTIVATED = "creator_mode_activated"
    CREATOR_MODE_EXPIRED = "creator_mode_expired"
    PRIVILEGE_DENIED = "privilege_denied"
    PRIVILEGE_GRANTED = "privilege_granted"
    
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    STRIKE_RECORDED = "strike_recorded"
    STRIKE_RESET = "strike_reset"
    RATE_LIMITED = "rate_limited"
    
    EXECUTION_STARTED = "execution_started"
    EXECUTION_SUCCESS = "execution_success"
    EXECUTION_FAILURE = "execution_failure"
    EXECUTION_TIMEOUT = "execution_timeout"


class AuditSeverity(Enum):
    """Severity of audit event."""
    INFO = "info"          
    WARNING = "warning"    
    CRITICAL = "critical"  



@dataclass
class AuditEntry:
    """
    Single audit log entry.
    
    Immutable once created. All entries include:
    - Timestamp (ISO 8601, UTC)
    - Trace ID (unique per request)
    - Session ID (per-session binding)
    - Event type (structured enum)
    - Severity (info/warning/critical)
    """
    timestamp: str                          
    trace_id: str                          
    session_id: str                        
    event_type: str                         
    severity: str                          
    
    intent: Optional[str] = None
    tier: Optional[int] = None
    risk_score: Optional[int] = None
    input_hash: Optional[str] = None       
    error: Optional[str] = None
    status: Optional[str] = None           
    user_agent: Optional[str] = None      
    
    command_executed: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None
    
    metadata: dict = field(default_factory=dict)
    
    def to_json(self) -> str:
        """Convert to JSON string for logging."""
        return json.dumps(asdict(self), separators=(',', ':'))



class AuditLogger:
    """
    Layer 0.5 — Append-only audit trail system.
    
    Provides thread-safe logging of all security events.
    Never deletes or modifies entries - write-only append.
    """
    
    def __init__(self, log_path: str = AUDIT_LOG_PATH):
        """
        Initialize audit logger.
        
        Args:
            log_path: Path to audit log file (JSONL format)
        """
        self.log_path = log_path
        self._lock = threading.RLock()
        self._session_traces: dict[str, list[str]] = defaultdict(list)
        
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
        if not os.path.exists(self.log_path):
            Path(self.log_path).touch()
    
    def log(
        self,
        event_type: AuditEventType,
        session_id: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        **kwargs
    ) -> str:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event (AuditEventType enum)
            session_id: Session identifier
            severity: Event severity level
            **kwargs: Additional event details (intent, tier, error, etc.)
            
        Returns:
            trace_id for request tracking
        """
        trace_id = kwargs.pop('trace_id', None) or self._generate_trace_id()
        
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            trace_id=trace_id,
            session_id=session_id,
            event_type=event_type.value,
            severity=severity.value,
            **kwargs
        )
        
        self._append_to_log(entry)
        
        self._session_traces[session_id].append(trace_id)
        
        return trace_id
    
    def get_session_audit(self, session_id: str) -> list[dict]:
        """
        Retrieve all audit entries for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of audit entries (dicts)
        """
        entries = []
        
        with self._lock:
            try:
                with open(self.log_path, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry_dict = json.loads(line)
                        if entry_dict.get('session_id') == session_id:
                            entries.append(entry_dict)
            except FileNotFoundError:
                pass
        
        return entries
    
    def get_trace(self, trace_id: str) -> Optional[dict]:
        """
        Retrieve audit entry by trace ID.
        
        Args:
            trace_id: Unique request trace ID
            
        Returns:
            Audit entry dict or None
        """
        with self._lock:
            try:
                with open(self.log_path, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry_dict = json.loads(line)
                        if entry_dict.get('trace_id') == trace_id:
                            return entry_dict
            except FileNotFoundError:
                pass
        
        return None
    
    def get_events_by_type(self, event_type: AuditEventType, session_id: Optional[str] = None) -> list[dict]:
        """
        Retrieve audit entries by event type.
        
        Args:
            event_type: Type of event to filter
            session_id: Optional session filter
            
        Returns:
            List of matching audit entries
        """
        entries = []
        event_value = event_type.value
        
        with self._lock:
            try:
                with open(self.log_path, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry_dict = json.loads(line)
                        if entry_dict.get('event_type') == event_value:
                            if session_id is None or entry_dict.get('session_id') == session_id:
                                entries.append(entry_dict)
            except FileNotFoundError:
                pass
        
        return entries
    
    def log_input(
        self,
        session_id: str,
        input_text: str,
        trace_id: Optional[str] = None,
        user_agent: str = "unknown"
    ) -> str:
        """Log input received."""
        import hashlib
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()
        
        return self.log(
            AuditEventType.INPUT_RECEIVED,
            session_id,
            AuditSeverity.INFO,
            trace_id=trace_id,
            input_hash=input_hash,
            user_agent=user_agent
        )
    
    def log_safety_check(
        self,
        session_id: str,
        intent: str,
        tier: int,
        risk_score: int,
        trace_id: Optional[str] = None,
        blocked: bool = False
    ) -> str:
        """Log SafetyKernel check result."""
        severity = AuditSeverity.CRITICAL if blocked else AuditSeverity.INFO
        
        return self.log(
            AuditEventType.SAFETY_CHECK,
            session_id,
            severity,
            trace_id=trace_id,
            intent=intent,
            tier=tier,
            risk_score=risk_score,
            status="blocked" if blocked else "allowed"
        )
    
    def log_confirmation_code(
        self,
        session_id: str,
        intent: str,
        trace_id: Optional[str] = None
    ) -> str:
        """Log confirmation code generation (NOT the code itself)."""
        return self.log(
            AuditEventType.CODE_GENERATED,
            session_id,
            AuditSeverity.WARNING,
            trace_id=trace_id,
            intent=intent
        )
    
    def log_confirmation_verify(
        self,
        session_id: str,
        intent: str,
        success: bool,
        trace_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> str:
        """Log confirmation code verification."""
        event_type = AuditEventType.CODE_VERIFIED_SUCCESS if success else AuditEventType.CODE_VERIFIED_FAILED
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
        
        return self.log(
            event_type,
            session_id,
            severity,
            trace_id=trace_id,
            intent=intent,
            error=reason
        )
    
    def log_privilege_check(
        self,
        session_id: str,
        intent: str,
        granted: bool,
        trace_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> str:
        """Log privilege check result."""
        event_type = AuditEventType.PRIVILEGE_GRANTED if granted else AuditEventType.PRIVILEGE_DENIED
        severity = AuditSeverity.CRITICAL if not granted else AuditSeverity.WARNING
        
        return self.log(
            event_type,
            session_id,
            severity,
            trace_id=trace_id,
            intent=intent,
            error=reason
        )
    
    def log_execution(
        self,
        session_id: str,
        intent: str,
        success: bool,
        trace_id: Optional[str] = None,
        exit_code: Optional[int] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> str:
        """Log command execution result."""
        event_type = AuditEventType.EXECUTION_SUCCESS if success else AuditEventType.EXECUTION_FAILURE
        severity = AuditSeverity.CRITICAL if not success else AuditSeverity.INFO
        
        return self.log(
            event_type,
            session_id,
            severity,
            trace_id=trace_id,
            intent=intent,
            status="success" if success else "failure",
            exit_code=exit_code,
            error=error,
            duration_ms=duration_ms
        )
    
    def log_strike(
        self,
        session_id: str,
        reason: str,
        strike_count: int,
        trace_id: Optional[str] = None
    ) -> str:
        """Log a strike against session."""
        return self.log(
            AuditEventType.STRIKE_RECORDED,
            session_id,
            AuditSeverity.WARNING,
            trace_id=trace_id,
            error=reason,
            metadata={"strike_count": strike_count}
        )
    
    def _append_to_log(self, entry: AuditEntry):
        """Append entry to log file (thread-safe)."""
        with self._lock:
            try:
                with open(self.log_path, 'a') as f:
                    f.write(entry.to_json() + '\n')
            except IOError as e:
                import sys
                print(f"[ERROR] Failed to write audit log: {e}", file=sys.stderr)
    
    @staticmethod
    def _generate_trace_id() -> str:
        """Generate unique trace ID for request."""
        return f"req-{uuid.uuid4().hex[:12]}"
    
    def get_log_file_size(self) -> int:
        """Get audit log file size in bytes."""
        try:
            return os.path.getsize(self.log_path)
        except FileNotFoundError:
            return 0
    
    def get_log_entry_count(self) -> int:
        """Count total audit log entries."""
        count = 0
        with self._lock:
            try:
                with open(self.log_path, 'r') as f:
                    for line in f:
                        if line.strip():
                            count += 1
            except FileNotFoundError:
                pass
        return count
    
    def get_stats(self) -> dict:
        """Get audit log statistics."""
        stats = {
            "file_path": self.log_path,
            "file_size_bytes": self.get_log_file_size(),
            "total_entries": self.get_log_entry_count(),
            "sessions_tracked": len(self._session_traces),
        }
        
        event_counts = defaultdict(int)
        with self._lock:
            try:
                with open(self.log_path, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry_dict = json.loads(line)
                        event_counts[entry_dict.get('event_type', 'unknown')] += 1
            except FileNotFoundError:
                pass
        
        stats["events_by_type"] = dict(event_counts)
        return stats


_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def set_audit_logger(logger: AuditLogger):
    """Set custom audit logger instance (for testing)."""
    global _audit_logger
    _audit_logger = logger
