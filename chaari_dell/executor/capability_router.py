# CHAARI 2.0 — Dell executor/capability_router.py — Capability-Based Routing
# ═══════════════════════════════════════════════════════════
# Routes validated command packets to the correct capability module.
# Each capability group has its own isolated module.
#
# KEY DESIGN PRINCIPLE:
#   A FILESYSTEM command can NEVER reach the POWER module.
#   Routing is based on capability_group field, NOT intent string parsing.
# ═══════════════════════════════════════════════════════════

import time
from datetime import datetime

from chaari_dell.models.packet_models import ExecutionResult


class CapabilityRouter:
    """
    Routes packets to capability modules based on capability_group.
    
    Each module is registered with a group name.
    Router ONLY dispatches — it never executes directly.
    """

    def __init__(self):
        self._modules: dict[str, object] = {}

    def register(self, capability_group: str, module):
        """
        Register a capability module.
        
        Args:
            capability_group: e.g., "POWER", "FILESYSTEM"
            module: Object with execute(intent, context) -> ExecutionResult
        """
        self._modules[capability_group.upper()] = module

    def route(self, packet: dict) -> ExecutionResult:
        """
        Route a validated packet to the correct capability module.
        
        Args:
            packet: Validated command packet (already passed validation pipeline)
            
        Returns:
            ExecutionResult from the capability module
        """
        cap_group = packet.get("capability_group", "").upper()
        intent = packet.get("intent", "")
        context = packet.get("context", {})
        trace_id = packet.get("trace_id", "")

        module = self._modules.get(cap_group)
        if not module:
            return ExecutionResult(
                intent=intent,
                status="rejected",
                error=f"No module registered for capability group: {cap_group}",
                trace_id=trace_id,
            )

        start = time.time()
        try:
            result = module.execute(intent, context)
            result.trace_id = trace_id
            result.duration_ms = int((time.time() - start) * 1000)
            return result
        except Exception as e:
            return ExecutionResult(
                intent=intent,
                status="failure",
                error=f"Execution error: {str(e)}",
                trace_id=trace_id,
                duration_ms=int((time.time() - start) * 1000),
            )

    def list_modules(self) -> dict[str, str]:
        """List registered capability modules."""
        return {
            group: type(module).__name__
            for group, module in self._modules.items()
        }
