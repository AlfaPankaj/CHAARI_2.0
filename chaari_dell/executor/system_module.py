# CHAARI 2.0 — Dell executor/system_module.py — SYSTEM Capability
# ═══════════════════════════════════════════════════════════
# Handles: FORMAT_DISK, KILL_PROCESS, MODIFY_REGISTRY
# These are Tier 3 (creator-only) — highest risk actions.
# ═══════════════════════════════════════════════════════════

import subprocess
import platform

from chaari_dell.models.packet_models import ExecutionResult

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class SystemModule:
    """
    Capability module for SYSTEM group (Tier 3 / critical).
    
    Supported intents:
        - SYSTEM.STORAGE.FORMAT   → format disk (blocked in current version)
        - SYSTEM.PROCESS.KILL     → kill process by PID
        - SYSTEM.REGISTRY.MODIFY  → registry modification (blocked in current version)
    """

    SUPPORTED_INTENTS = {
        "SYSTEM.STORAGE.FORMAT",
        "SYSTEM.PROCESS.KILL",
        "SYSTEM.REGISTRY.MODIFY",
    }

    def execute(self, intent: str, context: dict = None) -> ExecutionResult:
        context = context or {}

        if intent not in self.SUPPORTED_INTENTS:
            return ExecutionResult(intent=intent, status="rejected", error=f"Not supported: {intent}")

        if intent == "SYSTEM.STORAGE.FORMAT":
            return ExecutionResult(
                intent=intent,
                status="rejected",
                error="FORMAT_DISK is disabled in current version for safety",
            )

        if intent == "SYSTEM.REGISTRY.MODIFY":
            return ExecutionResult(
                intent=intent,
                status="rejected",
                error="REGISTRY modification is disabled in current version for safety",
            )

        if intent == "SYSTEM.PROCESS.KILL":
            return self._kill_process(context)

        return ExecutionResult(intent=intent, status="failure", error="Unhandled")

    def _kill_process(self, ctx: dict) -> ExecutionResult:
        """Kill a process by PID."""
        if not PSUTIL_AVAILABLE:
            return ExecutionResult(
                intent="SYSTEM.PROCESS.KILL",
                status="failure",
                error="psutil not available",
            )

        pid_str = ctx.get("process_name", ctx.get("pid", ""))
        try:
            pid = int(pid_str)
        except (ValueError, TypeError):
            return ExecutionResult(
                intent="SYSTEM.PROCESS.KILL",
                status="failure",
                error=f"Invalid PID: {pid_str}",
            )

        # Safety: never kill PID 0, 4, or system critical processes
        if pid in (0, 4):
            return ExecutionResult(
                intent="SYSTEM.PROCESS.KILL",
                status="rejected",
                error=f"Cannot kill system process PID {pid}",
            )

        try:
            proc = psutil.Process(pid)
            name = proc.name()
            proc.terminate()
            return ExecutionResult(
                intent="SYSTEM.PROCESS.KILL",
                status="success",
                output=f"Terminated PID {pid} ({name})",
                exit_code=0,
            )
        except psutil.NoSuchProcess:
            return ExecutionResult(
                intent="SYSTEM.PROCESS.KILL",
                status="failure",
                error=f"No process with PID {pid}",
            )
        except psutil.AccessDenied:
            return ExecutionResult(
                intent="SYSTEM.PROCESS.KILL",
                status="failure",
                error=f"Access denied for PID {pid}",
            )
        except Exception as e:
            return ExecutionResult(
                intent="SYSTEM.PROCESS.KILL",
                status="failure",
                error=str(e),
            )
