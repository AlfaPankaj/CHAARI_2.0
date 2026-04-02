# CHAARI 2.0 — Dell executor/power_module.py — POWER Capability
# ═══════════════════════════════════════════════════════════
# Handles: SYSTEM.POWER.SHUTDOWN, SYSTEM.POWER.RESTART
#
# HARDCODED commands only. No dynamic parameters from packets.
# Shutdown always has a 10-second delay for safety.
# ═══════════════════════════════════════════════════════════

import subprocess
import platform

from chaari_dell.models.packet_models import ExecutionResult


class PowerModule:
    """
    Capability module for POWER group.
    
    Supported intents:
        - SYSTEM.POWER.SHUTDOWN → shutdown /s /t 10
        - SYSTEM.POWER.RESTART  → shutdown /r /t 10
    """

    SUPPORTED_INTENTS = {
        "SYSTEM.POWER.SHUTDOWN",
        "SYSTEM.POWER.RESTART",
    }

    def execute(self, intent: str, context: dict = None) -> ExecutionResult:
        """Execute a power command."""
        if intent not in self.SUPPORTED_INTENTS:
            return ExecutionResult(
                intent=intent,
                status="rejected",
                error=f"PowerModule does not support intent: {intent}",
            )

        if intent == "SYSTEM.POWER.SHUTDOWN":
            return self._shutdown()
        elif intent == "SYSTEM.POWER.RESTART":
            return self._restart()

        return ExecutionResult(intent=intent, status="failure", error="Unhandled intent")

    def _shutdown(self) -> ExecutionResult:
        """Shutdown with 10-second delay."""
        if platform.system() == "Windows":
            cmd = ["shutdown", "/s", "/t", "10"]
        else:
            cmd = ["shutdown", "-h", "+0.17"]  # ~10 seconds

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return ExecutionResult(
                    intent="SYSTEM.POWER.SHUTDOWN",
                    status="success",
                    output="Shutdown initiated (10s delay). Use 'shutdown /a' to cancel.",
                    exit_code=0,
                )
            return ExecutionResult(
                intent="SYSTEM.POWER.SHUTDOWN",
                status="failure",
                error=result.stderr or "Shutdown command failed",
                exit_code=result.returncode,
            )
        except Exception as e:
            return ExecutionResult(
                intent="SYSTEM.POWER.SHUTDOWN",
                status="failure",
                error=str(e),
            )

    def _restart(self) -> ExecutionResult:
        """Restart with 10-second delay."""
        if platform.system() == "Windows":
            cmd = ["shutdown", "/r", "/t", "10"]
        else:
            cmd = ["shutdown", "-r", "+0.17"]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return ExecutionResult(
                    intent="SYSTEM.POWER.RESTART",
                    status="success",
                    output="Restart initiated (10s delay). Use 'shutdown /a' to cancel.",
                    exit_code=0,
                )
            return ExecutionResult(
                intent="SYSTEM.POWER.RESTART",
                status="failure",
                error=result.stderr or "Restart command failed",
                exit_code=result.returncode,
            )
        except Exception as e:
            return ExecutionResult(
                intent="SYSTEM.POWER.RESTART",
                status="failure",
                error=str(e),
            )
