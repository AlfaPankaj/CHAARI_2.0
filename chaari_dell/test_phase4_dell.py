# CHAARI 2.0 — Phase 4 Test Suite — Dell Execution Node
# ═══════════════════════════════════════════════════════════
# Tests for:
#   - Validation pipeline (7 steps)
#   - Capability router
#   - All capability modules (power, filesystem, app, system, communication)
#   - Result signing
#   - Agent integration
#
# Run: python -B -m unittest test_phase4_dell -v
# ═══════════════════════════════════════════════════════════

import os
import sys
import json
import time
import tempfile
import shutil
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chaari_dell.models.packet_models import (
    ValidationResult, ValidationStatus, ExecutionResult, PacketType,
)
from chaari_dell.crypto.nonce_store import DellNonceStore
from chaari_dell.executor.capability_router import CapabilityRouter
from chaari_dell.executor.filesystem_module import FilesystemModule
from chaari_dell.executor.application_module import ApplicationModule
from chaari_dell.executor.system_module import SystemModule
from chaari_dell.executor.communication_module import CommunicationModule


# ══════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════

def make_packet(**overrides) -> dict:
    """Create a valid test packet."""
    base = {
        "version": "2.0",
        "type": "command",
        "node_id": "asus-01",
        "intent": "FILESYSTEM.FILE.CREATE",
        "capability_group": "FILESYSTEM",
        "tier": 1,
        "context": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": f"test-{time.time()}-{id(overrides)}",
        "trace_id": "test-trace-001",
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════
# TEST 1: PACKET MODELS
# ══════════════════════════════════════════════════════════════

class TestPacketModels(unittest.TestCase):
    """Test packet model dataclasses."""

    def test_validation_result_valid(self):
        r = ValidationResult(valid=True, status=ValidationStatus.VALID)
        self.assertTrue(r.valid)
        self.assertEqual(r.status, ValidationStatus.VALID)

    def test_validation_result_invalid(self):
        r = ValidationResult(valid=False, status=ValidationStatus.INVALID_SIGNATURE, reason="bad_sig")
        self.assertFalse(r.valid)
        self.assertEqual(r.reason, "bad_sig")

    def test_validation_result_str(self):
        r = ValidationResult(valid=True, status=ValidationStatus.VALID)
        self.assertIn("valid=True", str(r))

    def test_execution_result_success(self):
        r = ExecutionResult(intent="test", status="success", output="done")
        self.assertTrue(r.is_success())
        self.assertEqual(r.output, "done")

    def test_execution_result_failure(self):
        r = ExecutionResult(intent="test", status="failure", error="boom")
        self.assertFalse(r.is_success())
        self.assertEqual(r.error, "boom")

    def test_execution_result_to_dict(self):
        r = ExecutionResult(intent="test", status="success", trace_id="t1")
        d = r.to_dict()
        self.assertEqual(d["intent"], "test")
        self.assertEqual(d["status"], "success")
        self.assertEqual(d["trace_id"], "t1")

    def test_execution_result_auto_timestamp(self):
        r = ExecutionResult(intent="test", status="success")
        self.assertTrue(r.timestamp)
        self.assertIn("Z", r.timestamp)

    def test_execution_result_truncates_long_output(self):
        r = ExecutionResult(intent="test", status="success", output="A" * 1000)
        d = r.to_dict()
        self.assertEqual(len(d["output"]), 500)

    def test_packet_type_enum(self):
        self.assertEqual(PacketType.COMMAND.value, "command")
        self.assertEqual(PacketType.RESULT.value, "result")

    def test_validation_status_enum_values(self):
        self.assertEqual(ValidationStatus.VALID.value, "valid")
        self.assertEqual(ValidationStatus.REPLAY_DETECTED.value, "replay_detected")
        self.assertEqual(ValidationStatus.UNAUTHORIZED_IP.value, "unauthorized_ip")


# ══════════════════════════════════════════════════════════════
# TEST 2: DELL NONCE STORE
# ══════════════════════════════════════════════════════════════

class TestDellNonceStore(unittest.TestCase):
    """Test Dell-side nonce tracking."""

    def setUp(self):
        self.store = DellNonceStore(timestamp_window=60, nonce_ttl=300)

    def test_fresh_nonce_accepted(self):
        ok, reason = self.store.check_and_record("nonce-001")
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_duplicate_nonce_rejected(self):
        self.store.check_and_record("nonce-dup")
        ok, reason = self.store.check_and_record("nonce-dup")
        self.assertFalse(ok)
        self.assertEqual(reason, "replay")

    def test_empty_nonce_rejected(self):
        ok, reason = self.store.check_and_record("")
        self.assertFalse(ok)
        self.assertEqual(reason, "empty")

    def test_whitespace_nonce_rejected(self):
        ok, reason = self.store.check_and_record("   ")
        self.assertFalse(ok)
        self.assertEqual(reason, "empty")

    def test_timestamp_valid(self):
        ts = datetime.now(timezone.utc).isoformat()
        ok, reason = self.store.validate_timestamp(ts)
        self.assertTrue(ok)

    def test_timestamp_expired(self):
        ts = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        ok, reason = self.store.validate_timestamp(ts)
        self.assertFalse(ok)
        self.assertEqual(reason, "expired")

    def test_timestamp_future(self):
        ts = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()
        ok, reason = self.store.validate_timestamp(ts)
        self.assertFalse(ok)
        self.assertEqual(reason, "future")

    def test_timestamp_invalid_format(self):
        ok, reason = self.store.validate_timestamp("not-a-date")
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid")

    def test_validate_freshness_combined(self):
        ts = datetime.now(timezone.utc).isoformat()
        ok, reason = self.store.validate_freshness("fresh-001", ts)
        self.assertTrue(ok)

    def test_validate_freshness_replayed(self):
        ts = datetime.now(timezone.utc).isoformat()
        self.store.validate_freshness("fresh-dup", ts)
        ok, reason = self.store.validate_freshness("fresh-dup", ts)
        self.assertFalse(ok)
        self.assertIn("nonce_replay", reason)

    def test_purge_expired(self):
        # Record with old timestamp manually
        self.store._seen["old-nonce"] = time.time() - 600
        purged = self.store.purge_expired()
        self.assertEqual(purged, 1)
        self.assertNotIn("old-nonce", self.store._seen)

    def test_many_nonces(self):
        for i in range(100):
            ok, _ = self.store.check_and_record(f"bulk-{i}")
            self.assertTrue(ok)


# ══════════════════════════════════════════════════════════════
# TEST 3: VALIDATION PIPELINE
# ══════════════════════════════════════════════════════════════

class TestValidationPipeline(unittest.TestCase):
    """Test 7-step validation pipeline."""

    def setUp(self):
        # Create pipeline with mocked verifier
        from chaari_dell.crypto.validation_pipeline import ValidationPipeline
        self.mock_verifier = MagicMock()
        self.mock_verifier.verify_command.return_value = True
        self.nonce_store = DellNonceStore(timestamp_window=60)
        self.pipeline = ValidationPipeline(self.mock_verifier, self.nonce_store)

    def _signed_packet(self, **overrides):
        p = make_packet(**overrides)
        p["signature"] = "fake-sig-base64"
        return p

    # ── Step 1: Structure ──

    def test_valid_structure(self):
        r = self.pipeline._check_structure(make_packet())
        self.assertTrue(r.valid)

    def test_missing_version(self):
        p = make_packet()
        del p["version"]
        r = self.pipeline._check_structure(p)
        self.assertFalse(r.valid)
        self.assertEqual(r.status, ValidationStatus.INVALID_STRUCTURE)

    def test_missing_intent(self):
        p = make_packet()
        del p["intent"]
        r = self.pipeline._check_structure(p)
        self.assertFalse(r.valid)

    def test_wrong_type(self):
        r = self.pipeline._check_structure(make_packet(type="result"))
        self.assertFalse(r.valid)

    def test_wrong_version(self):
        r = self.pipeline._check_structure(make_packet(version="1.0"))
        self.assertFalse(r.valid)

    def test_invalid_tier_zero(self):
        r = self.pipeline._check_structure(make_packet(tier=0))
        self.assertFalse(r.valid)

    def test_invalid_tier_four(self):
        r = self.pipeline._check_structure(make_packet(tier=4))
        self.assertFalse(r.valid)

    def test_tier_string_rejected(self):
        r = self.pipeline._check_structure(make_packet(tier="high"))
        self.assertFalse(r.valid)

    # ── Step 2: Source IP ──

    def test_localhost_accepted(self):
        r = self.pipeline._check_source_ip(make_packet(), "127.0.0.1")
        self.assertTrue(r.valid)

    def test_unknown_ip_rejected(self):
        r = self.pipeline._check_source_ip(make_packet(), "10.0.0.99")
        self.assertFalse(r.valid)
        self.assertEqual(r.status, ValidationStatus.UNAUTHORIZED_IP)

    # ── Step 3: Signature ──

    def test_valid_signature(self):
        p = self._signed_packet()
        r = self.pipeline._check_signature(p)
        self.assertTrue(r.valid)

    def test_missing_signature(self):
        r = self.pipeline._check_signature(make_packet())
        self.assertFalse(r.valid)
        self.assertEqual(r.status, ValidationStatus.INVALID_SIGNATURE)

    def test_invalid_signature(self):
        self.mock_verifier.verify_command.return_value = False
        p = self._signed_packet()
        r = self.pipeline._check_signature(p)
        self.assertFalse(r.valid)

    # ── Step 4: Timestamp ──

    def test_valid_timestamp(self):
        r = self.pipeline._check_timestamp(make_packet())
        self.assertTrue(r.valid)

    def test_expired_timestamp(self):
        ts = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        r = self.pipeline._check_timestamp(make_packet(timestamp=ts))
        self.assertFalse(r.valid)
        self.assertEqual(r.status, ValidationStatus.INVALID_TIMESTAMP)

    # ── Step 5: Nonce ──

    def test_fresh_nonce(self):
        r = self.pipeline._check_nonce(make_packet(nonce="unique-001"))
        self.assertTrue(r.valid)

    def test_replay_nonce(self):
        self.nonce_store.check_and_record("replay-nonce")
        r = self.pipeline._check_nonce(make_packet(nonce="replay-nonce"))
        self.assertFalse(r.valid)
        self.assertEqual(r.status, ValidationStatus.REPLAY_DETECTED)

    # ── Step 6: Capability ──

    def test_authorized_capability(self):
        r = self.pipeline._check_capability(make_packet(capability_group="FILESYSTEM"))
        self.assertTrue(r.valid)

    def test_unauthorized_capability(self):
        r = self.pipeline._check_capability(make_packet(capability_group="NETWORK"))
        self.assertFalse(r.valid)
        self.assertEqual(r.status, ValidationStatus.UNAUTHORIZED_CAPABILITY)

    # ── Step 7: Privilege ──

    def test_tier1_no_privilege_needed(self):
        r = self.pipeline._check_privilege(make_packet(tier=1))
        self.assertTrue(r.valid)

    def test_tier2_no_privilege_needed(self):
        r = self.pipeline._check_privilege(make_packet(tier=2))
        self.assertTrue(r.valid)

    def test_tier3_requires_privilege(self):
        r = self.pipeline._check_privilege(make_packet(tier=3))
        self.assertFalse(r.valid)
        self.assertEqual(r.status, ValidationStatus.INVALID_PRIVILEGE)

    def test_tier3_with_privilege(self):
        r = self.pipeline._check_privilege(make_packet(tier=3, privilege_token="creator-tok"))
        self.assertTrue(r.valid)

    # ── Full Pipeline ──

    def test_full_valid_packet(self):
        p = self._signed_packet(nonce=f"full-{time.time()}")
        r = self.pipeline.validate(p, "127.0.0.1")
        self.assertTrue(r.valid)
        self.assertEqual(r.status, ValidationStatus.VALID)

    def test_full_reject_bad_ip(self):
        p = self._signed_packet()
        r = self.pipeline.validate(p, "10.0.0.99")
        self.assertFalse(r.valid)
        self.assertEqual(r.status, ValidationStatus.UNAUTHORIZED_IP)

    def test_full_reject_missing_field(self):
        p = self._signed_packet()
        del p["intent"]
        r = self.pipeline.validate(p, "127.0.0.1")
        self.assertFalse(r.valid)


# ══════════════════════════════════════════════════════════════
# TEST 4: CAPABILITY ROUTER
# ══════════════════════════════════════════════════════════════

class TestCapabilityRouter(unittest.TestCase):
    """Test capability routing."""

    def setUp(self):
        self.router = CapabilityRouter()
        self.mock_module = MagicMock()
        self.mock_module.execute.return_value = ExecutionResult(
            intent="test", status="success", output="ok",
        )
        self.router.register("FILESYSTEM", self.mock_module)

    def test_route_to_registered_module(self):
        p = make_packet(capability_group="FILESYSTEM", intent="FILESYSTEM.FILE.CREATE")
        result = self.router.route(p)
        self.assertEqual(result.status, "success")
        self.mock_module.execute.assert_called_once()

    def test_route_unregistered_group_rejected(self):
        p = make_packet(capability_group="UNKNOWN", intent="UNKNOWN.ACTION")
        result = self.router.route(p)
        self.assertEqual(result.status, "rejected")
        self.assertIn("No module", result.error)

    def test_route_preserves_trace_id(self):
        p = make_packet(capability_group="FILESYSTEM", trace_id="trace-xyz")
        result = self.router.route(p)
        self.assertEqual(result.trace_id, "trace-xyz")

    def test_route_handles_module_exception(self):
        self.mock_module.execute.side_effect = RuntimeError("module crash")
        p = make_packet(capability_group="FILESYSTEM")
        result = self.router.route(p)
        self.assertEqual(result.status, "failure")
        self.assertIn("module crash", result.error)

    def test_list_modules(self):
        modules = self.router.list_modules()
        self.assertIn("FILESYSTEM", modules)

    def test_case_insensitive_group(self):
        p = make_packet(capability_group="filesystem")
        result = self.router.route(p)
        self.assertEqual(result.status, "success")


# ══════════════════════════════════════════════════════════════
# TEST 5: FILESYSTEM MODULE
# ══════════════════════════════════════════════════════════════

class TestFilesystemModule(unittest.TestCase):
    """Test filesystem capability module."""

    def setUp(self):
        self.mod = FilesystemModule()
        self.test_dir = tempfile.mkdtemp(prefix="chaari_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_file(self):
        path = os.path.join(self.test_dir, "test.txt")
        r = self.mod.execute("FILESYSTEM.FILE.CREATE", {"path": path})
        self.assertEqual(r.status, "success")
        self.assertTrue(os.path.exists(path))

    def test_create_file_no_path(self):
        r = self.mod.execute("FILESYSTEM.FILE.CREATE", {})
        self.assertEqual(r.status, "failure")
        self.assertIn("path", r.error.lower())

    def test_copy_file(self):
        src = os.path.join(self.test_dir, "source.txt")
        dst = os.path.join(self.test_dir, "dest.txt")
        with open(src, "w") as f:
            f.write("hello")
        r = self.mod.execute("FILESYSTEM.FILE.COPY", {"source": src, "destination": dst})
        self.assertEqual(r.status, "success")
        self.assertTrue(os.path.exists(dst))

    def test_copy_file_missing_source(self):
        r = self.mod.execute("FILESYSTEM.FILE.COPY", {
            "source": os.path.join(self.test_dir, "noexist.txt"),
            "destination": os.path.join(self.test_dir, "dest.txt"),
        })
        self.assertEqual(r.status, "failure")

    def test_copy_file_no_args(self):
        r = self.mod.execute("FILESYSTEM.FILE.COPY", {})
        self.assertEqual(r.status, "failure")

    def test_move_file(self):
        src = os.path.join(self.test_dir, "moveme.txt")
        dst = os.path.join(self.test_dir, "moved.txt")
        with open(src, "w") as f:
            f.write("data")
        r = self.mod.execute("FILESYSTEM.FILE.MOVE", {"source": src, "destination": dst})
        self.assertEqual(r.status, "success")
        self.assertFalse(os.path.exists(src))
        self.assertTrue(os.path.exists(dst))

    def test_move_file_missing_source(self):
        r = self.mod.execute("FILESYSTEM.FILE.MOVE", {
            "source": os.path.join(self.test_dir, "noexist.txt"),
            "destination": os.path.join(self.test_dir, "dest.txt"),
        })
        self.assertEqual(r.status, "failure")

    def test_delete_file(self):
        path = os.path.join(self.test_dir, "deleteme.txt")
        with open(path, "w") as f:
            f.write("bye")
        r = self.mod.execute("FILESYSTEM.FILE.DELETE", {"path": path})
        self.assertEqual(r.status, "success")
        self.assertFalse(os.path.exists(path))
        self.assertIn("backup", r.output.lower())

    def test_delete_nonexistent_file(self):
        path = os.path.join(self.test_dir, "noexist.txt")
        r = self.mod.execute("FILESYSTEM.FILE.DELETE", {"path": path})
        self.assertEqual(r.status, "failure")

    def test_unsupported_intent(self):
        r = self.mod.execute("FILESYSTEM.FILE.ENCRYPT", {})
        self.assertEqual(r.status, "rejected")

    def test_path_validation_blocks_system(self):
        valid, reason = self.mod._validate_path(r"C:\Windows\System32\test.txt")
        self.assertFalse(valid)

    def test_path_validation_allows_user_dir(self):
        valid, reason = self.mod._validate_path(os.path.join(self.test_dir, "safe.txt"))
        self.assertTrue(valid)

    def test_path_validation_empty(self):
        valid, reason = self.mod._validate_path("")
        self.assertFalse(valid)


# ══════════════════════════════════════════════════════════════
# TEST 6: APPLICATION MODULE
# ══════════════════════════════════════════════════════════════

class TestApplicationModule(unittest.TestCase):
    """Test application capability module."""

    def setUp(self):
        self.mod = ApplicationModule()

    def test_unsupported_intent_rejected(self):
        r = self.mod.execute("APPLICATION.LIFECYCLE.INSTALL", {"app_name": "notepad"})
        self.assertEqual(r.status, "rejected")

    def test_missing_app_name(self):
        r = self.mod.execute("APPLICATION.LIFECYCLE.LAUNCH", {})
        self.assertEqual(r.status, "failure")
        self.assertIn("app_name", r.error.lower())

    def test_app_not_in_whitelist(self):
        r = self.mod.execute("APPLICATION.LIFECYCLE.LAUNCH", {"app_name": "malware"})
        self.assertEqual(r.status, "failure")
        self.assertIn("whitelist", r.error.lower())

    def test_terminate_missing_app(self):
        r = self.mod.execute("APPLICATION.LIFECYCLE.TERMINATE", {"app_name": "nonexistent_app_xyz"})
        # Should fail gracefully (no running instances)
        self.assertIn(r.status, ("failure", "rejected"))


# ══════════════════════════════════════════════════════════════
# TEST 7: SYSTEM MODULE
# ══════════════════════════════════════════════════════════════

class TestSystemModule(unittest.TestCase):
    """Test system capability module (Tier 3 / critical)."""

    def setUp(self):
        self.mod = SystemModule()

    def test_format_disk_blocked(self):
        r = self.mod.execute("SYSTEM.STORAGE.FORMAT", {})
        self.assertEqual(r.status, "rejected")
        self.assertIn("disabled", r.error.lower())

    def test_registry_modify_blocked(self):
        r = self.mod.execute("SYSTEM.REGISTRY.MODIFY", {})
        self.assertEqual(r.status, "rejected")
        self.assertIn("disabled", r.error.lower())

    def test_kill_invalid_pid(self):
        r = self.mod.execute("SYSTEM.PROCESS.KILL", {"pid": "abc"})
        self.assertEqual(r.status, "failure")
        self.assertIn("Invalid PID", r.error)

    def test_kill_system_pid_blocked(self):
        r = self.mod.execute("SYSTEM.PROCESS.KILL", {"pid": "0"})
        self.assertEqual(r.status, "rejected")

    def test_kill_pid_4_blocked(self):
        r = self.mod.execute("SYSTEM.PROCESS.KILL", {"pid": "4"})
        self.assertEqual(r.status, "rejected")

    def test_kill_nonexistent_pid(self):
        r = self.mod.execute("SYSTEM.PROCESS.KILL", {"pid": "999999"})
        self.assertEqual(r.status, "failure")

    def test_unsupported_intent(self):
        r = self.mod.execute("SYSTEM.NETWORK.HACK", {})
        self.assertEqual(r.status, "rejected")


# ══════════════════════════════════════════════════════════════
# TEST 8: COMMUNICATION MODULE
# ══════════════════════════════════════════════════════════════

class TestCommunicationModule(unittest.TestCase):
    """Test communication capability module."""

    def setUp(self):
        self.mod = CommunicationModule()

    def test_type_text_no_text(self):
        r = self.mod.execute("COMMUNICATION.INPUT.TYPE_TEXT", {"text": ""})
        self.assertEqual(r.status, "failure")

    def test_send_message_missing_contact(self):
        r = self.mod.execute("COMMUNICATION.MESSAGING.SEND", {"text": "hello"})
        self.assertEqual(r.status, "failure")
        self.assertIn("contact", r.error.lower())

    def test_send_message_missing_text(self):
        r = self.mod.execute("COMMUNICATION.MESSAGING.SEND", {"contact": "Bhaiya"})
        self.assertEqual(r.status, "failure")

    def test_send_message_valid(self):
        r = self.mod.execute("COMMUNICATION.MESSAGING.SEND", {
            "contact": "Bhaiya",
            "text": "Hello",
            "platform": "whatsapp",
        })
        self.assertEqual(r.status, "success")
        self.assertIn("Bhaiya", r.output)

    def test_make_call_no_contact(self):
        r = self.mod.execute("COMMUNICATION.CALLING.DIAL", {})
        self.assertEqual(r.status, "failure")

    def test_make_call_valid(self):
        r = self.mod.execute("COMMUNICATION.CALLING.DIAL", {
            "contact": "Bhaiya",
            "call_type": "video",
            "platform": "whatsapp",
        })
        self.assertEqual(r.status, "success")
        self.assertIn("Video", r.output)

    def test_unsupported_intent(self):
        r = self.mod.execute("COMMUNICATION.SPAM.BULK", {})
        self.assertEqual(r.status, "rejected")


# ══════════════════════════════════════════════════════════════
# TEST 9: POWER MODULE (safe tests only — no actual shutdown)
# ══════════════════════════════════════════════════════════════

class TestPowerModule(unittest.TestCase):
    """Test power module (without actually shutting down)."""

    def setUp(self):
        from chaari_dell.executor.power_module import PowerModule
        self.mod = PowerModule()

    def test_unsupported_intent(self):
        r = self.mod.execute("SYSTEM.POWER.HIBERNATE")
        self.assertEqual(r.status, "rejected")

    def test_supported_intents(self):
        self.assertIn("SYSTEM.POWER.SHUTDOWN", self.mod.SUPPORTED_INTENTS)
        self.assertIn("SYSTEM.POWER.RESTART", self.mod.SUPPORTED_INTENTS)


# ══════════════════════════════════════════════════════════════
# TEST 10: AGENT INTEGRATION
# ══════════════════════════════════════════════════════════════

class TestDellAgentIntegration(unittest.TestCase):
    """Test DellAgent wiring (without real keys)."""

    def setUp(self):
        from chaari_dell.agent import DellAgent
        self.agent = DellAgent()

    def test_agent_not_booted_initially(self):
        self.assertFalse(self.agent._booted)

    def test_process_packet_before_boot(self):
        r = self.agent.process_packet(make_packet())
        self.assertEqual(r["status"], "failure")
        self.assertIn("not booted", r["error"])

    def test_status_before_boot(self):
        s = self.agent.status()
        self.assertFalse(s["booted"])
        self.assertEqual(s["node_id"], "dell-01")

    def test_build_result_packet_structure(self):
        # Test result packet builder directly
        exec_result = ExecutionResult(
            intent="test.intent",
            status="success",
            output="done",
            trace_id="t1",
        )
        packet = self.agent._build_result_packet(exec_result)
        self.assertEqual(packet["version"], "2.0")
        self.assertEqual(packet["type"], "result")
        self.assertEqual(packet["status"], "success")
        self.assertEqual(packet["intent"], "test.intent")

    def test_error_result_structure(self):
        r = self.agent._error_result("test error", {"intent": "X", "trace_id": "T"})
        self.assertEqual(r["status"], "failure")
        self.assertEqual(r["error"], "test error")
        self.assertEqual(r["intent"], "X")


# ══════════════════════════════════════════════════════════════
# TEST 11: SIGNATURE VERIFIER (unit tests)
# ══════════════════════════════════════════════════════════════

class TestSignatureVerifier(unittest.TestCase):
    """Test SignatureVerifier without real keys."""

    def test_keys_not_loaded_initially(self):
        from chaari_dell.crypto.signature_verifier import SignatureVerifier
        sv = SignatureVerifier(tempfile.mkdtemp())
        self.assertFalse(sv.keys_loaded())

    def test_verify_without_keys_raises(self):
        from chaari_dell.crypto.signature_verifier import SignatureVerifier
        sv = SignatureVerifier(tempfile.mkdtemp())
        with self.assertRaises(RuntimeError):
            sv.verify_command({"signature": "abc"})

    def test_sign_without_keys_raises(self):
        from chaari_dell.crypto.signature_verifier import SignatureVerifier
        sv = SignatureVerifier(tempfile.mkdtemp())
        with self.assertRaises(RuntimeError):
            sv.sign_result({"data": "test"})


# ══════════════════════════════════════════════════════════════
# TEST 12: CRYPTO INTEGRATION (with real key generation)
# ══════════════════════════════════════════════════════════════

class TestCryptoIntegration(unittest.TestCase):
    """Test sign → verify round-trip with generated keys."""

    @classmethod
    def setUpClass(cls):
        """Generate temp keys for testing."""
        cls.key_dir = tempfile.mkdtemp(prefix="chaari_keys_")
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend

            # Generate ASUS key pair
            asus_private = rsa.generate_private_key(65537, 2048, default_backend())
            asus_public = asus_private.public_key()

            # Generate Dell key pair
            dell_private = rsa.generate_private_key(65537, 2048, default_backend())
            dell_public = dell_private.public_key()

            # Save keys
            for name, key, is_private in [
                ("asus_private.pem", asus_private, True),
                ("asus_public.pem", asus_public, False),
                ("dell_private.pem", dell_private, True),
                ("dell_public.pem", dell_public, False),
            ]:
                path = os.path.join(cls.key_dir, name)
                with open(path, "wb") as f:
                    if is_private:
                        f.write(key.private_bytes(
                            serialization.Encoding.PEM,
                            serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption(),
                        ))
                    else:
                        f.write(key.public_bytes(
                            serialization.Encoding.PEM,
                            serialization.PublicFormat.SubjectPublicKeyInfo,
                        ))

            cls.keys_available = True
        except ImportError:
            cls.keys_available = False

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.key_dir, ignore_errors=True)

    def setUp(self):
        if not self.keys_available:
            self.skipTest("cryptography package not available")

    def test_sign_and_verify_roundtrip(self):
        from chaari_dell.crypto.signature_verifier import SignatureVerifier
        sv = SignatureVerifier(self.key_dir)
        sv.load_keys("asus", "dell")
        self.assertTrue(sv.keys_loaded())

        # Create and sign a packet (simulate ASUS signing)
        # We use ASUS private key to sign (need to load it directly)
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        import base64

        with open(os.path.join(self.key_dir, "asus_private.pem"), "rb") as f:
            asus_priv = serialization.load_pem_private_key(f.read(), None, default_backend())

        packet = make_packet(nonce=f"crypto-{time.time()}")
        canonical = json.dumps(
            {k: v for k, v in packet.items() if k != "signature"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")

        sig = asus_priv.sign(
            canonical,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        packet["signature"] = base64.b64encode(sig).decode("ascii")

        # Verify with Dell verifier
        self.assertTrue(sv.verify_command(packet))

    def test_tampered_packet_fails(self):
        from chaari_dell.crypto.signature_verifier import SignatureVerifier
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        import base64

        sv = SignatureVerifier(self.key_dir)
        sv.load_keys("asus", "dell")

        with open(os.path.join(self.key_dir, "asus_private.pem"), "rb") as f:
            asus_priv = serialization.load_pem_private_key(f.read(), None, default_backend())

        packet = make_packet(nonce=f"tamper-{time.time()}")
        canonical = json.dumps(
            {k: v for k, v in packet.items() if k != "signature"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        sig = asus_priv.sign(
            canonical,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        packet["signature"] = base64.b64encode(sig).decode("ascii")

        # Tamper
        packet["intent"] = "HACKED"
        self.assertFalse(sv.verify_command(packet))

    def test_dell_sign_result(self):
        from chaari_dell.crypto.signature_verifier import SignatureVerifier
        sv = SignatureVerifier(self.key_dir)
        sv.load_keys("asus", "dell")

        result = {
            "version": "2.0",
            "type": "result",
            "intent": "test",
            "status": "success",
        }
        signed = sv.sign_result(result)
        self.assertIn("signature", signed)
        self.assertIsInstance(signed["signature"], str)

    def test_full_pipeline_with_real_crypto(self):
        """End-to-end: ASUS signs → Dell validates → routes → signs result."""
        from chaari_dell.crypto.signature_verifier import SignatureVerifier
        from chaari_dell.crypto.validation_pipeline import ValidationPipeline
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        import base64

        # Load verifier
        sv = SignatureVerifier(self.key_dir)
        sv.load_keys("asus", "dell")

        # Load ASUS private key to simulate ASUS signing
        with open(os.path.join(self.key_dir, "asus_private.pem"), "rb") as f:
            asus_priv = serialization.load_pem_private_key(f.read(), None, default_backend())

        # Build and sign packet (ASUS side)
        packet = make_packet(
            nonce=f"e2e-{time.time()}",
            capability_group="FILESYSTEM",
        )
        canonical = json.dumps(
            {k: v for k, v in packet.items() if k != "signature"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        sig = asus_priv.sign(
            canonical,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        packet["signature"] = base64.b64encode(sig).decode("ascii")

        # Validate on Dell side
        pipeline = ValidationPipeline(sv, DellNonceStore())
        result = pipeline.validate(packet, "127.0.0.1")
        self.assertTrue(result.valid, f"Validation failed: {result.reason}")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
