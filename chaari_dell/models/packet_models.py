# CHAARI 2.0 — Dell models/packet_models.py — Packet Data Models
# ═══════════════════════════════════════════════════════════
# Shared packet models used by Dell verifier + executor
# ═══════════════════════════════════════════════════════════

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PacketType(Enum):
    COMMAND = "command"
    RESULT = "result"


class ValidationStatus(Enum):
    VALID = "valid"
    INVALID_STRUCTURE = "invalid_structure"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_TIMESTAMP = "invalid_timestamp"
    REPLAY_DETECTED = "replay_detected"
    UNAUTHORIZED_IP = "unauthorized_ip"
    UNAUTHORIZED_CAPABILITY = "unauthorized_capability"
    INVALID_PRIVILEGE = "invalid_privilege"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ValidationResult:
    """Result of packet validation pipeline."""
    valid: bool
    status: ValidationStatus
    reason: str = ""
    packet: dict = field(default_factory=dict)

    def __str__(self):
        return f"ValidationResult(valid={self.valid}, status={self.status.value}, reason={self.reason})"


@dataclass
class ExecutionResult:
    """Result of command execution on Dell."""
    intent: str
    status: str             # "success" | "failure" | "rejected"
    output: str = ""
    error: str = ""
    exit_code: int = None
    trace_id: str = ""
    duration_ms: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"

    def is_success(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "status": self.status,
            "output": self.output[:500],
            "error": self.error[:500],
            "exit_code": self.exit_code,
            "trace_id": self.trace_id,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }
