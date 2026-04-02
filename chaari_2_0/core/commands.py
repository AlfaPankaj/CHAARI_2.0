# CHAARI 2.0 – System Command Registry
# Executes Tier 1-3 system actions after privilege verification

from core.executor_port import CommandExecutorPort, ExecutionStatus


class SystemCommandRegistry:
    """
    Manages execution of system commands after privilege verification.
    
    Routes validated system intents to the CommandExecutorPort for actual execution.
    Never executes directly - always delegates to executor adapter.
    """

    def __init__(self, executor: CommandExecutorPort):
        """
        Initialize the command registry with an executor adapter.
        
        Args:
            executor: CommandExecutorPort implementation (e.g., OSExecutor, NoOpExecutor)
        """
        self.executor = executor

    def execute(self, intent: str, context: dict = None) -> str:
        """
        Execute a system command based on the intent via executor adapter.
        
        Args:
            intent: The system intent to execute (e.g., "SHUTDOWN", "RESTART")
            context: Optional context dict with parameters (e.g., {'path': '/file.txt'})
            
        Returns:
            Human-readable result message from the executed command
        """
        if context is None:
            context = {}
        
        result = self.executor.execute(intent, context)
        
        if result.status == ExecutionStatus.SUCCESS:
            return f"✅ {intent} completed successfully: {result.output}"
        else:
            error_msg = result.error or "Unknown error"
            return f"❌ {intent} failed: {error_msg}"
