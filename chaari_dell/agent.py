# CHAARI 2.0 — Dell Execution Node — agent.py (Main Entry Point)
# ═══════════════════════════════════════════════════════════
# Wires together:
#   - Crypto verification (ASUS commands)
#   - Validation pipeline (7-step)
#   - Capability router (routes to modules)
#   - Result signing (Dell private key)
#
# Usage:
#   python agent.py                 — Start Dell agent
#   python agent.py --test-local    — Self-test with synthetic packets
# ═══════════════════════════════════════════════════════════

import os
import sys
import json
import time
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chaari_dell.config import (
    NODE_ID, NODE_NAME, KEY_DIR, LOG_DIR,
    DELL_PRIVATE_KEY_NAME, ASUS_PUBLIC_KEY_NAME,
    AUTHORIZED_CAPABILITIES,
)
from chaari_dell.crypto.signature_verifier import SignatureVerifier
from chaari_dell.crypto.validation_pipeline import ValidationPipeline
from chaari_dell.crypto.nonce_store import DellNonceStore
from chaari_dell.executor.capability_router import CapabilityRouter
from chaari_dell.executor.power_module import PowerModule
from chaari_dell.executor.filesystem_module import FilesystemModule
from chaari_dell.executor.application_module import ApplicationModule
from chaari_dell.executor.system_module import SystemModule
from chaari_dell.executor.communication_module import CommunicationModule
from chaari_dell.executor.media_module import MediaModule
from chaari_dell.models.packet_models import ExecutionResult


class DellAgent:
    """
    Dell Execution Node — receives signed commands, validates, executes, signs results.
    
    Lifecycle:
        1. Boot: Load keys, init validation pipeline, register capability modules
        2. Receive: Accept signed command packet
        3. Validate: Run 7-step validation pipeline
        4. Route: Send to correct capability module
        5. Execute: Module runs hardcoded OS command
        6. Sign: Sign result with Dell private key
        7. Return: Signed result packet back to ASUS
    """

    def __init__(self):
        self._verifier: SignatureVerifier = None
        self._pipeline: ValidationPipeline = None
        self._router: CapabilityRouter = None
        self._nonce_store: DellNonceStore = None
        self._booted = False
        self._boot_time: str = None

    def boot(self) -> bool:
        """Initialize all subsystems. Returns True if successful."""
        print(f"\n{'═' * 60}")
        print(f"  CHAARI 2.0 — Dell Execution Node")
        print(f"  Node: {NODE_ID} ({NODE_NAME})")
        print(f"{'═' * 60}\n")

        # ── Step 1: Ensure directories ──
        os.makedirs(KEY_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        print(f"  [✓] Directories ready")

        # ── Step 2: Load crypto keys ──
        try:
            self._verifier = SignatureVerifier(KEY_DIR)
            print(f"  [✓] Crypto keys loaded")
        except Exception as e:
            print(f"  [✗] Crypto init failed: {e}")
            print(f"      → Copy asus_public.pem and dell keys to {KEY_DIR}")
            return False

        # ── Step 3: Init nonce store ──
        self._nonce_store = DellNonceStore()
        print(f"  [✓] Nonce store initialized")

        # ── Step 4: Init validation pipeline ──
        self._pipeline = ValidationPipeline(self._verifier, self._nonce_store)
        print(f"  [✓] Validation pipeline ready (7-step)")

        # ── Step 5: Register capability modules ──
        self._router = CapabilityRouter()
        self._router.register("POWER", PowerModule())
        self._router.register("FILESYSTEM", FilesystemModule())
        self._router.register("APPLICATION", ApplicationModule())
        self._router.register("SYSTEM", SystemModule())
        self._router.register("COMMUNICATION", CommunicationModule())
        self._router.register("MEDIA", MediaModule())
        print(f"  [✓] Capability modules registered:")
        for group, mod_name in self._router.list_modules().items():
            marker = "✓" if group in AUTHORIZED_CAPABILITIES else "✗"
            print(f"      [{marker}] {group} → {mod_name}")

        self._booted = True
        self._boot_time = datetime.now(timezone.utc).isoformat()
        print(f"\n  ✅ Dell Agent READY — {self._boot_time}")
        print(f"{'═' * 60}\n")
        return True

    def process_packet(self, packet: dict, source_ip: str = "127.0.0.1") -> dict:
        """
        Process an incoming signed command packet.
        
        Full flow: Validate → Route → Execute → Sign Result
        
        Args:
            packet: Signed command packet from ASUS
            source_ip: IP of sender
            
        Returns:
            Signed result packet (dict)
        """
        if not self._booted:
            return self._error_result("Dell agent not booted", packet)

        trace_id = packet.get("trace_id", "unknown")
        intent = packet.get("intent", "unknown")

        # ── VALIDATE ──
        validation = self._pipeline.validate(packet, source_ip)
        if not validation.valid:
            return self._build_result_packet(ExecutionResult(
                intent=intent,
                status="rejected",
                error=f"Validation failed: {validation.reason}",
                trace_id=trace_id,
            ))

        # ── ROUTE + EXECUTE ──
        exec_result = self._router.route(packet)

        # ── SIGN RESULT ──
        return self._build_result_packet(exec_result)

    def _build_result_packet(self, result: ExecutionResult) -> dict:
        """Build and sign a result packet."""
        packet = {
            "version": "2.0",
            "type": "result",
            "node_id": NODE_ID,
            "intent": result.intent,
            "trace_id": result.trace_id or "unknown",
            "status": result.status,
            "output": result.output or "",
            "error": result.error or "",
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Sign with Dell private key
        if self._verifier:
            try:
                signed = self._verifier.sign_result(packet)
                if signed:
                    packet = signed
            except Exception:
                pass  # Return unsigned if signing fails

        self._log_result(packet)
        return packet

    def _error_result(self, error: str, packet: dict = None) -> dict:
        """Build error result without execution."""
        return {
            "version": "2.0",
            "type": "result",
            "node_id": NODE_ID,
            "intent": (packet or {}).get("intent", "unknown"),
            "trace_id": (packet or {}).get("trace_id", "unknown"),
            "status": "failure",
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _log_result(self, result_packet: dict):
        """Append to execution audit log."""
        log_path = os.path.join(LOG_DIR, "execution_audit.jsonl")
        try:
            entry = {
                "timestamp": result_packet.get("timestamp"),
                "intent": result_packet.get("intent"),
                "trace_id": result_packet.get("trace_id"),
                "status": result_packet.get("status"),
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def status(self) -> dict:
        """Get agent status."""
        return {
            "node_id": NODE_ID,
            "booted": self._booted,
            "boot_time": self._boot_time,
            "modules": self._router.list_modules() if self._router else {},
            "authorized": list(AUTHORIZED_CAPABILITIES),
        }


# ══════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════

def main():
    agent = DellAgent()
    success = agent.boot()

    if not success:
        print("\n⚠️  Dell agent failed to boot. Check key files.")
        sys.exit(1)

    if "--test-local" in sys.argv:
        print("Running local self-test...\n")
        _run_self_test(agent)
        return

    # ── Start network server ──
    if "--no-network" not in sys.argv:
        from chaari_dell.network.server import DellServer
        server = DellServer(agent)
        print("Starting network server...")

        # ── Start voice interface if requested ──
        voice_iface = None
        if "--voice" in sys.argv or "-v" in sys.argv:
            try:
                from chaari_dell.audio.voice_interface import DellVoiceInterface
                voice_iface = DellVoiceInterface()
                if voice_iface.boot():
                    voice_iface.start()
                else:
                    voice_iface = None
            except Exception as e:
                print(f"  [Voice] Failed to start: {e}")

        try:
            server.start()  # blocking
        except KeyboardInterrupt:
            print("\n  Shutting down...")
            if voice_iface:
                voice_iface.stop()
            server.stop()
    else:
        # ── Voice-only mode (no network) ──
        if "--voice" in sys.argv or "-v" in sys.argv:
            try:
                from chaari_dell.audio.voice_interface import DellVoiceInterface
                voice_iface = DellVoiceInterface()
                if voice_iface.boot():
                    voice_iface.start()
                    print("Dell agent running in voice-only mode. Press Ctrl+C to stop.")
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        voice_iface.stop()
                        print("\n  Shutting down.")
                    return
            except Exception as e:
                print(f"  [Voice] Failed to start: {e}")

        print("Dell agent is running (no-network mode).")
        status = agent.status()
        print(f"Status: {json.dumps(status, indent=2)}")


def _run_self_test(agent: DellAgent):
    """Quick self-test with a synthetic packet."""
    # This is unsigned, so validation will reject it (as expected)
    test_packet = {
        "version": "2.0",
        "type": "command",
        "node_id": "asus-01",
        "intent": "FILESYSTEM.FILE.CREATE",
        "capability_group": "FILESYSTEM",
        "tier": 1,
        "context": {"path": os.path.join(os.path.dirname(__file__), "test_self_test.tmp")},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": f"test-{int(time.time())}",
        "trace_id": "self-test-001",
    }

    print(f"  Test packet: intent={test_packet['intent']}")
    result = agent.process_packet(test_packet)
    print(f"  Result: status={result.get('status')}, error={result.get('error', 'none')}")

    # Clean up if a test file was somehow created
    tmp_path = test_packet["context"]["path"]
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
        print(f"  Cleaned up: {tmp_path}")

    print("\n  Self-test complete.")


if __name__ == "__main__":
    main()
