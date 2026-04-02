# CHAARI 2.0 — Dell crypto/validation_pipeline.py — Full Packet Validation
# ═══════════════════════════════════════════════════════════
# Responsibility:
#   ✔ Run ALL validation checks in order
#   ✔ Reject on first failure (fail-fast)
#   ✔ Return structured ValidationResult
#
# Validation order (from PDF):
#   1. Structure validation (required fields, version, type)
#   2. Source IP check (ASUS_IP whitelist)
#   3. Signature verification (ASUS public key)
#   4. Timestamp window (±60 seconds)
#   5. Nonce check (replay protection)
#   6. Capability group authorization
#   7. Privilege token (if tier 2+)
# ═══════════════════════════════════════════════════════════

import json
import os
from datetime import datetime

from chaari_dell.models.packet_models import ValidationResult, ValidationStatus
from chaari_dell.crypto.signature_verifier import SignatureVerifier
from chaari_dell.crypto.nonce_store import DellNonceStore
from chaari_dell.config import (
    ASUS_IP_WHITELIST,
    AUTHORIZED_CAPABILITIES,
    TIMESTAMP_WINDOW_SECONDS,
    NONCE_TTL_SECONDS,
    LOG_DIR,
)

VALIDATION_LOG_PATH = os.path.join(LOG_DIR, "validation_audit.jsonl")


class ValidationPipeline:
    """
    Full packet validation pipeline.
    
    ASUS sends a signed command packet → Dell runs this pipeline.
    If ANY check fails → reject immediately with specific reason.
    """

    def __init__(self, verifier: SignatureVerifier, nonce_store: DellNonceStore = None):
        self._verifier = verifier
        self._nonce_store = nonce_store or DellNonceStore(
            timestamp_window=TIMESTAMP_WINDOW_SECONDS,
            nonce_ttl=NONCE_TTL_SECONDS,
        )
        os.makedirs(LOG_DIR, exist_ok=True)

    def validate(self, packet: dict, source_ip: str = "127.0.0.1") -> ValidationResult:
        """
        Run full validation pipeline on incoming command packet.
        
        Args:
            packet: The signed command packet from ASUS
            source_ip: IP address of the sender
            
        Returns:
            ValidationResult — check .valid before executing
        """
        # ── Step 1: Structure validation ──
        result = self._check_structure(packet)
        if not result.valid:
            self._log("REJECTED", packet, result)
            return result

        # ── Step 2: Source IP check ──
        result = self._check_source_ip(packet, source_ip)
        if not result.valid:
            self._log("REJECTED", packet, result)
            return result

        # ── Step 3: Signature verification ──
        result = self._check_signature(packet)
        if not result.valid:
            self._log("REJECTED", packet, result)
            return result

        # ── Step 4: Timestamp window ──
        result = self._check_timestamp(packet)
        if not result.valid:
            self._log("REJECTED", packet, result)
            return result

        # ── Step 5: Nonce (replay protection) ──
        result = self._check_nonce(packet)
        if not result.valid:
            self._log("REJECTED", packet, result)
            return result

        # ── Step 6: Capability group authorization ──
        result = self._check_capability(packet)
        if not result.valid:
            self._log("REJECTED", packet, result)
            return result

        # ── Step 7: Privilege check (tier 3 only) ──
        result = self._check_privilege(packet)
        if not result.valid:
            self._log("REJECTED", packet, result)
            return result

        # ── ALL CHECKS PASSED ──
        valid_result = ValidationResult(
            valid=True,
            status=ValidationStatus.VALID,
            reason="all_checks_passed",
            packet=packet,
        )
        self._log("ACCEPTED", packet, valid_result)
        return valid_result

    # ══════════════════════════════════════════
    # INDIVIDUAL CHECKS
    # ══════════════════════════════════════════

    def _check_structure(self, packet: dict) -> ValidationResult:
        """Step 1: Validate packet structure."""
        required = ["version", "type", "node_id", "intent", "capability_group",
                     "tier", "timestamp", "nonce", "trace_id"]

        for field in required:
            if field not in packet:
                return ValidationResult(
                    valid=False,
                    status=ValidationStatus.INVALID_STRUCTURE,
                    reason=f"missing_field:{field}",
                )

        if packet.get("type") != "command":
            return ValidationResult(
                valid=False,
                status=ValidationStatus.INVALID_STRUCTURE,
                reason=f"wrong_type:{packet.get('type')}",
            )

        if packet.get("version") != "2.0":
            return ValidationResult(
                valid=False,
                status=ValidationStatus.INVALID_STRUCTURE,
                reason=f"unsupported_version:{packet.get('version')}",
            )

        tier = packet.get("tier")
        if not isinstance(tier, int) or tier < 1 or tier > 3:
            return ValidationResult(
                valid=False,
                status=ValidationStatus.INVALID_STRUCTURE,
                reason=f"invalid_tier:{tier}",
            )

        return ValidationResult(valid=True, status=ValidationStatus.VALID)

    def _check_source_ip(self, packet: dict, source_ip: str) -> ValidationResult:
        """Step 2: Check source IP against whitelist."""
        if source_ip not in ASUS_IP_WHITELIST:
            return ValidationResult(
                valid=False,
                status=ValidationStatus.UNAUTHORIZED_IP,
                reason=f"ip_not_whitelisted:{source_ip}",
            )
        return ValidationResult(valid=True, status=ValidationStatus.VALID)

    def _check_signature(self, packet: dict) -> ValidationResult:
        """Step 3: Verify ASUS signature."""
        if "signature" not in packet:
            return ValidationResult(
                valid=False,
                status=ValidationStatus.INVALID_SIGNATURE,
                reason="missing_signature",
            )

        if not self._verifier.verify_command(packet):
            return ValidationResult(
                valid=False,
                status=ValidationStatus.INVALID_SIGNATURE,
                reason="signature_verification_failed",
            )

        return ValidationResult(valid=True, status=ValidationStatus.VALID)

    def _check_timestamp(self, packet: dict) -> ValidationResult:
        """Step 4: Validate timestamp window."""
        ts_valid, ts_reason = self._nonce_store.validate_timestamp(packet.get("timestamp", ""))
        if not ts_valid:
            return ValidationResult(
                valid=False,
                status=ValidationStatus.INVALID_TIMESTAMP,
                reason=f"timestamp_{ts_reason}",
            )
        return ValidationResult(valid=True, status=ValidationStatus.VALID)

    def _check_nonce(self, packet: dict) -> ValidationResult:
        """Step 5: Check nonce for replay."""
        nonce_valid, nonce_reason = self._nonce_store.check_and_record(packet.get("nonce", ""))
        if not nonce_valid:
            return ValidationResult(
                valid=False,
                status=ValidationStatus.REPLAY_DETECTED,
                reason=f"nonce_{nonce_reason}",
            )
        return ValidationResult(valid=True, status=ValidationStatus.VALID)

    def _check_capability(self, packet: dict) -> ValidationResult:
        """Step 6: Check capability group authorization."""
        cap_group = packet.get("capability_group", "")
        if cap_group not in AUTHORIZED_CAPABILITIES:
            return ValidationResult(
                valid=False,
                status=ValidationStatus.UNAUTHORIZED_CAPABILITY,
                reason=f"unauthorized_capability:{cap_group}",
            )
        return ValidationResult(valid=True, status=ValidationStatus.VALID)

    def _check_privilege(self, packet: dict) -> ValidationResult:
        """Step 7: Check privilege token for tier 3."""
        tier = packet.get("tier", 1)
        if tier >= 3:
            token = packet.get("privilege_token")
            if not token:
                return ValidationResult(
                    valid=False,
                    status=ValidationStatus.INVALID_PRIVILEGE,
                    reason="tier3_requires_privilege_token",
                )
            # Future: validate token signature/expiry
        return ValidationResult(valid=True, status=ValidationStatus.VALID)

    # ══════════════════════════════════════════
    # LOGGING
    # ══════════════════════════════════════════

    def _log(self, action: str, packet: dict, result: ValidationResult):
        """Append validation event to audit log."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "trace_id": packet.get("trace_id", "unknown"),
            "intent": packet.get("intent", "unknown"),
            "status": result.status.value,
            "reason": result.reason,
        }
        try:
            with open(VALIDATION_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
