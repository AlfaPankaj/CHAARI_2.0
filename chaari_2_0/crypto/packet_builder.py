# CHAARI 2.0 — crypto/packet_builder.py — Command Packet Structure
# Responsibility:
# Build structured command packets (ASUS → Dell)
# Build result packets (Dell → ASUS)
# Attach signatures to packets
# Validate packet structure

# Packet format (from PDF architecture):
#     "version": "2.0",
#     "node_id": "dell-01",
#     "intent": "SYSTEM.POWER.SHUTDOWN",
#     "capability_group": "POWER",
#     "tier": 2,
#     "context": {...},
#     "timestamp": "ISO-8601",
#     "nonce": "uuid",
#     "trace_id": "uuid",
#     "privilege_token": "...",
#     "signature": "base64-encoded"

import uuid
import base64
from datetime import datetime, timezone

from crypto.signer import CryptoSigner


PACKET_VERSION = "2.0"


class PacketBuilder:
    """
    Builds cryptographically signed command packets.
    
    ASUS uses this to create commands destined for Dell.
    Dell uses this to create result packets back to ASUS.
    """

    @staticmethod
    def build_command_packet(
        node_id: str,
        intent: str,
        capability_group: str,
        tier: int,
        context: dict = None,
        trace_id: str = None,
        privilege_token: str = None,
    ) -> dict:
        """
        Build an unsigned command packet.
        
        Args:
            node_id: Target execution node (e.g., "dell-01")
            intent: Hierarchical intent (e.g., "SYSTEM.POWER.SHUTDOWN")
            capability_group: Capability group (e.g., "POWER")
            tier: Tier level (1-3)
            context: Optional parameters dict
            trace_id: Optional trace ID (auto-generated if None)
            privilege_token: Optional privilege token (for Tier 3)
            
        Returns:
            Unsigned packet dict (ready for signing)
        """
        packet = {
            "version": PACKET_VERSION,
            "type": "command",
            "node_id": node_id,
            "intent": intent,
            "capability_group": capability_group,
            "tier": tier,
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": str(uuid.uuid4()),
            "trace_id": trace_id or str(uuid.uuid4()),
        }

        if privilege_token:
            packet["privilege_token"] = privilege_token

        return packet

    @staticmethod
    def build_result_packet(
        node_id: str,
        trace_id: str,
        intent: str,
        status: str,
        output: str = "",
        error: str = "",
        exit_code: int = None,
    ) -> dict:
        """
        Build an unsigned result packet (Dell → ASUS).
        
        Args:
            node_id: Source execution node (e.g., "dell-01")
            trace_id: Must match the original command's trace_id
            intent: The intent that was executed
            status: "success" | "failure" | "rejected"
            output: Execution output
            error: Error message (if any)
            exit_code: OS exit code (if applicable)
            
        Returns:
            Unsigned result packet dict
        """
        packet = {
            "version": PACKET_VERSION,
            "type": "result",
            "node_id": node_id,
            "trace_id": trace_id,
            "intent": intent,
            "status": status,
            "output": output,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": str(uuid.uuid4()),
        }

        if exit_code is not None:
            packet["exit_code"] = exit_code

        return packet

    @staticmethod
    def sign_packet(packet: dict, private_key) -> dict:
        """
        Sign a packet and attach the signature.
        
        The signature covers ALL fields except 'signature' itself.
        
        Args:
            packet: Unsigned packet dict
            private_key: RSAPrivateKey to sign with
            
        Returns:
            New packet dict with 'signature' field added
        """
        signable = {k: v for k, v in packet.items() if k != "signature"}

        signature_bytes = CryptoSigner.sign(signable, private_key)

        signed_packet = dict(packet)
        signed_packet["signature"] = base64.b64encode(signature_bytes).decode("ascii")

        return signed_packet

    @staticmethod
    def verify_packet(packet: dict, public_key) -> bool:
        """
        Verify the signature on a packet.
        
        Args:
            packet: Signed packet dict (must have 'signature' field)
            public_key: RSAPublicKey to verify against
            
        Returns:
            True if signature is valid
        """
        signature_b64 = packet.get("signature")
        if not signature_b64:
            return False

        try:
            signature_bytes = base64.b64decode(signature_b64)
        except Exception:
            return False

        signable = {k: v for k, v in packet.items() if k != "signature"}

        return CryptoSigner.verify(signable, signature_bytes, public_key)

    @staticmethod
    def validate_command_packet(packet: dict) -> tuple[bool, str]:
        """
        Validate command packet structure (not signature — that's separate).
        
        Returns:
            (is_valid, error_message)
        """
        required = ["version", "type", "node_id", "intent", "capability_group",
                     "tier", "timestamp", "nonce", "trace_id"]

        for field in required:
            if field not in packet:
                return False, f"Missing required field: {field}"

        if packet.get("type") != "command":
            return False, f"Invalid packet type: {packet.get('type')} (expected 'command')"

        if packet.get("version") != PACKET_VERSION:
            return False, f"Unsupported version: {packet.get('version')}"

        tier = packet.get("tier")
        if not isinstance(tier, int) or tier < 1 or tier > 3:
            return False, f"Invalid tier: {tier} (must be 1-3)"

        return True, ""

    @staticmethod
    def validate_result_packet(packet: dict) -> tuple[bool, str]:
        """
        Validate result packet structure.
        
        Returns:
            (is_valid, error_message)
        """
        required = ["version", "type", "node_id", "trace_id", "intent",
                     "status", "timestamp", "nonce"]

        for field in required:
            if field not in packet:
                return False, f"Missing required field: {field}"

        if packet.get("type") != "result":
            return False, f"Invalid packet type: {packet.get('type')} (expected 'result')"

        valid_statuses = {"success", "failure", "rejected"}
        if packet.get("status") not in valid_statuses:
            return False, f"Invalid status: {packet.get('status')}"

        return True, ""

    @staticmethod
    def extract_signable(packet: dict) -> dict:
        """Extract the signable portion of a packet (everything except signature)."""
        return {k: v for k, v in packet.items() if k != "signature"}
