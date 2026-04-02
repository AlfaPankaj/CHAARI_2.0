"""
ExecutorPort - Layer 3 Command Execution Interface

Defines the formal contract for command execution.
Core depends on ports, not on adapters.
This port is implemented by OSExecutor (Layer 3.5) running on Dell.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any
from datetime import datetime


class ExecutionStatus(Enum):
    """Execution result status codes."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    INVALID_INTENT = "invalid_intent"
    NOT_AUTHORIZED = "not_authorized"
    SYSTEM_ERROR = "system_error"


@dataclass
class ExecutionResult:
    """Result of command execution."""
    status: ExecutionStatus
    intent: str
    command: Optional[str] = None
    exit_code: Optional[int] = None
    output: str = ""
    error: str = ""
    timestamp: datetime = None
    duration_ms: int = 0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            'status': self.status.value,
            'intent': self.intent,
            'command': self.command,
            'exit_code': self.exit_code,
            'output': self.output[:500],  # Truncate large output
            'error': self.error[:500],
            'timestamp': self.timestamp.isoformat(),
            'duration_ms': self.duration_ms
        }


class CommandExecutorPort(ABC):
    """
    Port interface for command execution.
    
    This is implemented by adapters (e.g., OSExecutor).
    Core does not depend on OS directly - only on this port.
    
    Design principle:
    - Only SystemIntent enum values allowed (type safety)
    - Hardcoded intent->command mapping (no dynamic input)
    - Adapter validates all inputs before execution
    - Returns detailed ExecutionResult
    """
    
    @abstractmethod
    def can_execute(self, intent: str) -> bool:
        """
        Check if executor can handle this intent.
        
        Args:
            intent: SystemIntent enum value as string
            
        Returns:
            True if intent is supported, False otherwise
        """
        pass
    
    @abstractmethod
    def execute(self, intent: str, context: Optional[dict] = None) -> ExecutionResult:
        """
        Execute command for given intent.
        
        Args:
            intent: SystemIntent enum value (e.g., 'SHUTDOWN', 'RESTART')
            context: Optional context dict with parameters (e.g., {'path': '/file.txt'})
            
        Returns:
            ExecutionResult with status, output, error details
            
        Raises:
            ValueError: If intent is not supported
            TimeoutError: If execution exceeds timeout
        """
        pass
    
    @abstractmethod
    def get_supported_intents(self) -> list[str]:
        """
        Get list of supported intent names.
        
        Returns:
            List of allowed intent strings
        """
        pass
    
    @abstractmethod
    def validate_context(self, intent: str, context: dict) -> tuple[bool, str]:
        """
        Validate context parameters for given intent.
        
        Args:
            intent: SystemIntent enum value
            context: Context parameters dict
            
        Returns:
            Tuple (is_valid, error_message)
        """
        pass


class NoOpExecutor(CommandExecutorPort):
    """
    Null object pattern - executor that does nothing.
    Used when OSExecutor is not available or in testing.
    """
    
    def can_execute(self, intent: str) -> bool:
        return True
    
    def execute(self, intent: str, context: Optional[dict] = None) -> ExecutionResult:
        """Return success without doing anything."""
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            intent=intent,
            command=f"[NO-OP] {intent}",
            output=f"[No-op mode] Intent {intent} accepted but not executed",
            exit_code=0
        )
    
    def get_supported_intents(self) -> list[str]:
        return [
            'SHUTDOWN',
            'RESTART',
            'DELETE_FILE',
            'FORMAT_DISK',
            'KILL_PROCESS',
            'MODIFY_REGISTRY',
            'CREATE_FILE',
            'COPY_FILE',
            'MOVE_FILE',
            'OPEN_APP',
            'OPEN_FILE',
            'CLOSE_APP',
            'MINIMIZE_APP',
            'MAXIMIZE_APP',
            'RESTORE_APP',
            'TYPE_TEXT',
            'SEND_MESSAGE',
            'MAKE_CALL',
            'MEDIA.CAPTURE.ANALYZE_SCREEN',
        ]
    
    def validate_context(self, intent: str, context: dict) -> tuple[bool, str]:
        return True, ""


class MockExecutor(CommandExecutorPort):
    """
    Mock executor for testing - tracks calls but doesn't execute.
    """
    
    def __init__(self):
        self.calls = []
        self.should_fail = False
    
    def can_execute(self, intent: str) -> bool:
        return True
    
    def execute(self, intent: str, context: Optional[dict] = None) -> ExecutionResult:
        """Record call and return mock result."""
        self.calls.append({'intent': intent, 'context': context})
        
        if self.should_fail:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                intent=intent,
                error="Mock failure"
            )
        
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            intent=intent,
            command=f"[MOCK] {intent}",
            output=f"Mock execution of {intent}",
            exit_code=0
        )
    
    def get_supported_intents(self) -> list[str]:
        return [
            'SHUTDOWN',
            'RESTART',
            'DELETE_FILE',
            'FORMAT_DISK',
            'KILL_PROCESS',
            'MODIFY_REGISTRY',
            'CREATE_FILE',
            'COPY_FILE',
            'MOVE_FILE',
            'OPEN_APP',
            'CLOSE_APP',
            'MINIMIZE_APP',
            'MAXIMIZE_APP',
            'RESTORE_APP',
            'TYPE_TEXT',
            'SEND_MESSAGE',
            'MAKE_CALL',
            'MEDIA.CAPTURE.ANALYZE_SCREEN',
        ]
    
    def validate_context(self, intent: str, context: dict) -> tuple[bool, str]:
        return True, ""
    
    def get_call_count(self) -> int:
        return len(self.calls)
    
    def get_calls(self) -> list[dict]:
        return self.calls
