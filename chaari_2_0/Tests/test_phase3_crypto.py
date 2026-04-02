"""
CHAARI 2.0 — Phase 3 Test Suite: Crypto Layer + Intent Hierarchy
═══════════════════════════════════════════════════════════════════
Tests:
  - RSA key generation + load
  - Signing + verification
  - Packet building + validation
  - Nonce tracking + replay protection
  - Timestamp window validation
  - Intent hierarchy + capability groups
  - Full end-to-end signed packet flow
"""

import sys
import os
import json
import time
import uuid
import shutil
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.system_intent import SystemIntent
from models.intent_hierarchy import (
    CapabilityGroup,
    INTENT_NAMESPACE,
    INTENT_CAPABILITY_MAP,
    get_namespace,
    get_capability_group,
    intent_from_namespace,
    get_group_intents,
    list_hierarchy,
)
from crypto.key_manager import KeyManager
from crypto.signer import CryptoSigner
from crypto.packet_builder import PacketBuilder, PACKET_VERSION
from crypto.nonce_store import NonceStore


# ═══════════════════════════════════════════════════
# TEST 1: Intent Hierarchy & Capability Groups
# ═══════════════════════════════════════════════════

class TestIntentHierarchy(unittest.TestCase):
    """Test the hierarchical intent namespace system."""

    def test_all_intents_have_namespace(self):
        """Every SystemIntent must have a namespace mapping."""
        for intent in SystemIntent:
            ns = get_namespace(intent)
            self.assertIsNotNone(ns, f"Missing namespace for {intent}")
            self.assertNotIn("UNKNOWN", ns, f"Unmapped namespace for {intent}")

    def test_all_intents_have_capability_group(self):
        """Every SystemIntent must belong to a capability group."""
        for intent in SystemIntent:
            group = get_capability_group(intent)
            self.assertIsInstance(group, CapabilityGroup, f"Missing group for {intent}")

    def test_namespace_format(self):
        """Namespaces must follow GROUP.SUBGROUP.ACTION format."""
        for intent, ns in INTENT_NAMESPACE.items():
            parts = ns.split(".")
            self.assertGreaterEqual(len(parts), 3, f"Namespace too short: {ns}")
            # All uppercase
            self.assertEqual(ns, ns.upper(), f"Namespace not uppercase: {ns}")

    def test_reverse_lookup(self):
        """Namespace → SystemIntent reverse lookup works."""
        for intent, ns in INTENT_NAMESPACE.items():
            resolved = intent_from_namespace(ns)
            self.assertEqual(resolved, intent, f"Reverse lookup failed for {ns}")

    def test_invalid_namespace_returns_none(self):
        """Unknown namespace returns None."""
        self.assertIsNone(intent_from_namespace("INVALID.NAMESPACE.HERE"))

    def test_capability_group_coverage(self):
        """Active capability groups have at least one intent."""
        # NETWORK is reserved for future — skip it
        active_groups = [g for g in CapabilityGroup if g != CapabilityGroup.NETWORK]
        for group in active_groups:
            intents = get_group_intents(group)
            self.assertGreater(len(intents), 0, f"Empty group: {group}")

    def test_power_group(self):
        """POWER group contains shutdown and restart."""
        intents = get_group_intents(CapabilityGroup.POWER)
        intent_values = [i.value for i in intents]
        self.assertIn("shutdown", intent_values)
        self.assertIn("restart", intent_values)

    def test_filesystem_group(self):
        """FILESYSTEM group contains file operations."""
        intents = get_group_intents(CapabilityGroup.FILESYSTEM)
        intent_values = [i.value for i in intents]
        self.assertIn("create_file", intent_values)
        self.assertIn("delete_file", intent_values)
        self.assertIn("copy_file", intent_values)
        self.assertIn("move_file", intent_values)

    def test_application_group(self):
        """APPLICATION group contains app lifecycle + window mgmt."""
        intents = get_group_intents(CapabilityGroup.APPLICATION)
        intent_values = [i.value for i in intents]
        self.assertIn("open_app", intent_values)
        self.assertIn("close_app", intent_values)
        self.assertIn("minimize_app", intent_values)
        self.assertIn("maximize_app", intent_values)
        self.assertIn("restore_app", intent_values)

    def test_communication_group(self):
        """COMMUNICATION group contains messaging/call intents."""
        intents = get_group_intents(CapabilityGroup.COMMUNICATION)
        intent_values = [i.value for i in intents]
        self.assertIn("type_text", intent_values)
        self.assertIn("send_message", intent_values)
        self.assertIn("make_call", intent_values)

    def test_list_hierarchy_structure(self):
        """list_hierarchy() returns properly structured dict."""
        hierarchy = list_hierarchy()
        self.assertIsInstance(hierarchy, dict)
        # Active groups (with intents) should be present
        active_groups = [g for g in CapabilityGroup if g != CapabilityGroup.NETWORK]
        for group in active_groups:
            self.assertIn(group.value, hierarchy, f"Missing group: {group.value}")

    def test_specific_namespaces(self):
        """Verify specific namespace values."""
        self.assertEqual(get_namespace(SystemIntent.SHUTDOWN), "SYSTEM.POWER.SHUTDOWN")
        self.assertEqual(get_namespace(SystemIntent.OPEN_APP), "APPLICATION.LIFECYCLE.LAUNCH")
        self.assertEqual(get_namespace(SystemIntent.DELETE_FILE), "FILESYSTEM.FILE.DELETE")
        self.assertEqual(get_namespace(SystemIntent.SEND_MESSAGE), "COMMUNICATION.MESSAGING.SEND")
        self.assertEqual(get_namespace(SystemIntent.FORMAT_DISK), "SYSTEM.STORAGE.FORMAT")

    def test_capability_group_from_string(self):
        """CapabilityGroup.from_string() works."""
        self.assertEqual(CapabilityGroup.from_string("POWER"), CapabilityGroup.POWER)
        self.assertEqual(CapabilityGroup.from_string("filesystem"), CapabilityGroup.FILESYSTEM)
        self.assertIsNone(CapabilityGroup.from_string("nonexistent"))


# ═══════════════════════════════════════════════════
# TEST 2: Key Manager
# ═══════════════════════════════════════════════════

class TestKeyManager(unittest.TestCase):
    """Test RSA key generation and loading."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.km = KeyManager(key_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_key_pair(self):
        """Generate a key pair and verify files exist."""
        priv_path, pub_path = self.km.generate_key_pair("test")
        self.assertTrue(os.path.exists(priv_path))
        self.assertTrue(os.path.exists(pub_path))
        self.assertIn("test_private.pem", priv_path)
        self.assertIn("test_public.pem", pub_path)

    def test_load_private_key(self):
        """Load a generated private key."""
        self.km.generate_key_pair("test")
        key = self.km.load_private_key("test")
        self.assertIsNotNone(key)
        self.assertEqual(key.key_size, 2048)

    def test_load_public_key(self):
        """Load a generated public key."""
        self.km.generate_key_pair("test")
        key = self.km.load_public_key("test")
        self.assertIsNotNone(key)
        self.assertEqual(key.key_size, 2048)

    def test_generate_all_keys(self):
        """Generate both ASUS and Dell key pairs."""
        result = self.km.generate_all_keys()
        self.assertIn("asus", result)
        self.assertIn("dell", result)
        self.assertTrue(self.km.all_keys_present())

    def test_keys_exist_check(self):
        """keys_exist() returns correct status."""
        status = self.km.keys_exist("asus")
        self.assertFalse(status["private"])
        self.assertFalse(status["public"])

        self.km.generate_key_pair("asus")
        status = self.km.keys_exist("asus")
        self.assertTrue(status["private"])
        self.assertTrue(status["public"])

    def test_all_keys_present_false(self):
        """all_keys_present() returns False when keys missing."""
        self.assertFalse(self.km.all_keys_present())
        self.km.generate_key_pair("asus")
        self.assertFalse(self.km.all_keys_present())  # Dell still missing

    def test_load_nonexistent_key_raises(self):
        """Loading a nonexistent key raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            self.km.load_private_key("nonexistent")

    def test_get_key_info(self):
        """get_key_info() returns proper structure."""
        self.km.generate_all_keys()
        info = self.km.get_key_info()
        self.assertTrue(info["asus_private"]["exists"])
        self.assertTrue(info["asus_public"]["exists"])
        self.assertTrue(info["dell_private"]["exists"])
        self.assertTrue(info["dell_public"]["exists"])
        self.assertGreater(info["asus_private"]["size_bytes"], 0)

    def test_key_pair_with_passphrase(self):
        """Generate and load key pair with passphrase."""
        self.km.generate_key_pair("secure", passphrase=b"test_pass_123")
        key = self.km.load_private_key("secure", passphrase=b"test_pass_123")
        self.assertIsNotNone(key)
        self.assertEqual(key.key_size, 2048)


# ═══════════════════════════════════════════════════
# TEST 3: Crypto Signer
# ═══════════════════════════════════════════════════

class TestCryptoSigner(unittest.TestCase):
    """Test RSA signing and verification."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.km = KeyManager(key_dir=self.temp_dir)
        self.km.generate_key_pair("test")
        self.private_key = self.km.load_private_key("test")
        self.public_key = self.km.load_public_key("test")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sign_and_verify(self):
        """Sign a payload and verify it."""
        payload = {"intent": "SYSTEM.POWER.SHUTDOWN", "nonce": "abc123"}
        signature = CryptoSigner.sign(payload, self.private_key)
        self.assertIsInstance(signature, bytes)
        self.assertTrue(CryptoSigner.verify(payload, signature, self.public_key))

    def test_verify_wrong_key_fails(self):
        """Verification with wrong key fails."""
        self.km.generate_key_pair("other")
        other_pub = self.km.load_public_key("other")
        
        payload = {"intent": "test"}
        signature = CryptoSigner.sign(payload, self.private_key)
        self.assertFalse(CryptoSigner.verify(payload, signature, other_pub))

    def test_verify_modified_payload_fails(self):
        """Modified payload fails verification."""
        payload = {"intent": "SYSTEM.POWER.SHUTDOWN", "nonce": "abc"}
        signature = CryptoSigner.sign(payload, self.private_key)
        
        # Modify payload
        tampered = {"intent": "SYSTEM.POWER.SHUTDOWN", "nonce": "xyz"}
        self.assertFalse(CryptoSigner.verify(tampered, signature, self.public_key))

    def test_canonical_ordering(self):
        """Same keys in different order produce same canonical form."""
        p1 = {"b": 2, "a": 1}
        p2 = {"a": 1, "b": 2}
        sig1 = CryptoSigner.sign(p1, self.private_key)
        # p2 should verify against sig1 since canonical form is the same
        self.assertTrue(CryptoSigner.verify(p2, sig1, self.public_key))

    def test_sign_bytes(self):
        """Sign and verify raw bytes."""
        data = b"raw binary data for signing"
        sig = CryptoSigner.sign_bytes(data, self.private_key)
        self.assertTrue(CryptoSigner.verify_bytes(data, sig, self.public_key))

    def test_hash_payload_consistency(self):
        """Same payload always produces same hash."""
        payload = {"a": 1, "b": "hello"}
        h1 = CryptoSigner.hash_payload(payload)
        h2 = CryptoSigner.hash_payload(payload)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex digest

    def test_hash_payload_changes_with_data(self):
        """Different payloads produce different hashes."""
        h1 = CryptoSigner.hash_payload({"a": 1})
        h2 = CryptoSigner.hash_payload({"a": 2})
        self.assertNotEqual(h1, h2)


# ═══════════════════════════════════════════════════
# TEST 4: Packet Builder
# ═══════════════════════════════════════════════════

class TestPacketBuilder(unittest.TestCase):
    """Test command and result packet building."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.km = KeyManager(key_dir=self.temp_dir)
        self.km.generate_all_keys()
        self.asus_priv = self.km.load_private_key("asus")
        self.asus_pub = self.km.load_public_key("asus")
        self.dell_priv = self.km.load_private_key("dell")
        self.dell_pub = self.km.load_public_key("dell")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_command_packet(self):
        """Build a command packet with all required fields."""
        packet = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent="SYSTEM.POWER.SHUTDOWN",
            capability_group="POWER",
            tier=2,
        )
        self.assertEqual(packet["version"], PACKET_VERSION)
        self.assertEqual(packet["type"], "command")
        self.assertEqual(packet["node_id"], "dell-01")
        self.assertEqual(packet["intent"], "SYSTEM.POWER.SHUTDOWN")
        self.assertEqual(packet["capability_group"], "POWER")
        self.assertEqual(packet["tier"], 2)
        self.assertIn("timestamp", packet)
        self.assertIn("nonce", packet)
        self.assertIn("trace_id", packet)

    def test_build_result_packet(self):
        """Build a result packet."""
        packet = PacketBuilder.build_result_packet(
            node_id="dell-01",
            trace_id="trace-123",
            intent="SYSTEM.POWER.SHUTDOWN",
            status="success",
            output="Shutdown initiated",
        )
        self.assertEqual(packet["type"], "result")
        self.assertEqual(packet["status"], "success")
        self.assertEqual(packet["trace_id"], "trace-123")

    def test_sign_and_verify_command_packet(self):
        """Sign a command packet with ASUS key, verify with ASUS public."""
        packet = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent="SYSTEM.POWER.SHUTDOWN",
            capability_group="POWER",
            tier=2,
        )
        signed = PacketBuilder.sign_packet(packet, self.asus_priv)
        self.assertIn("signature", signed)
        self.assertTrue(PacketBuilder.verify_packet(signed, self.asus_pub))

    def test_sign_and_verify_result_packet(self):
        """Sign a result packet with Dell key, verify with Dell public."""
        packet = PacketBuilder.build_result_packet(
            node_id="dell-01",
            trace_id="trace-456",
            intent="FILESYSTEM.FILE.CREATE",
            status="success",
        )
        signed = PacketBuilder.sign_packet(packet, self.dell_priv)
        self.assertTrue(PacketBuilder.verify_packet(signed, self.dell_pub))

    def test_tampered_packet_fails_verification(self):
        """Modifying a signed packet fails verification."""
        packet = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent="SYSTEM.POWER.SHUTDOWN",
            capability_group="POWER",
            tier=2,
        )
        signed = PacketBuilder.sign_packet(packet, self.asus_priv)
        
        # Tamper with the packet
        signed["intent"] = "SYSTEM.STORAGE.FORMAT"
        self.assertFalse(PacketBuilder.verify_packet(signed, self.asus_pub))

    def test_wrong_key_fails_verification(self):
        """Verifying with Dell key a packet signed by ASUS fails."""
        packet = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent="APPLICATION.LIFECYCLE.LAUNCH",
            capability_group="APPLICATION",
            tier=1,
        )
        signed = PacketBuilder.sign_packet(packet, self.asus_priv)
        self.assertFalse(PacketBuilder.verify_packet(signed, self.dell_pub))

    def test_validate_command_packet_valid(self):
        """Valid command packet passes validation."""
        packet = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent="SYSTEM.POWER.SHUTDOWN",
            capability_group="POWER",
            tier=2,
        )
        valid, msg = PacketBuilder.validate_command_packet(packet)
        self.assertTrue(valid, msg)

    def test_validate_command_packet_missing_field(self):
        """Packet missing required field fails validation."""
        packet = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent="SYSTEM.POWER.SHUTDOWN",
            capability_group="POWER",
            tier=2,
        )
        del packet["nonce"]
        valid, msg = PacketBuilder.validate_command_packet(packet)
        self.assertFalse(valid)
        self.assertIn("nonce", msg)

    def test_validate_command_packet_wrong_type(self):
        """Packet with wrong type fails."""
        packet = PacketBuilder.build_result_packet(
            node_id="dell-01", trace_id="t", intent="x", status="success"
        )
        valid, msg = PacketBuilder.validate_command_packet(packet)
        self.assertFalse(valid)

    def test_validate_command_packet_invalid_tier(self):
        """Packet with invalid tier fails."""
        packet = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent="SYSTEM.POWER.SHUTDOWN",
            capability_group="POWER",
            tier=5,
        )
        valid, msg = PacketBuilder.validate_command_packet(packet)
        self.assertFalse(valid)
        self.assertIn("tier", msg)

    def test_validate_result_packet_valid(self):
        """Valid result packet passes validation."""
        packet = PacketBuilder.build_result_packet(
            node_id="dell-01", trace_id="t", intent="x", status="success"
        )
        valid, msg = PacketBuilder.validate_result_packet(packet)
        self.assertTrue(valid, msg)

    def test_validate_result_packet_bad_status(self):
        """Result packet with invalid status fails."""
        packet = PacketBuilder.build_result_packet(
            node_id="dell-01", trace_id="t", intent="x", status="maybe"
        )
        valid, msg = PacketBuilder.validate_result_packet(packet)
        self.assertFalse(valid)

    def test_packet_with_context(self):
        """Command packet with context dict."""
        ctx = {"app_name": "notepad", "path": "C:\\test.txt"}
        packet = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent="APPLICATION.LIFECYCLE.LAUNCH",
            capability_group="APPLICATION",
            tier=1,
            context=ctx,
        )
        self.assertEqual(packet["context"], ctx)

    def test_packet_with_privilege_token(self):
        """Command packet with privilege token (Tier 3)."""
        packet = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent="SYSTEM.STORAGE.FORMAT",
            capability_group="SYSTEM",
            tier=3,
            privilege_token="creator_token_abc",
        )
        self.assertEqual(packet["privilege_token"], "creator_token_abc")


# ═══════════════════════════════════════════════════
# TEST 5: Nonce Store
# ═══════════════════════════════════════════════════

class TestNonceStore(unittest.TestCase):
    """Test nonce tracking and replay protection."""

    def setUp(self):
        self.store = NonceStore()

    def test_new_nonce_accepted(self):
        """New nonce is accepted."""
        valid, reason = self.store.check_and_record("nonce-123")
        self.assertTrue(valid)
        self.assertEqual(reason, "ok")

    def test_replay_nonce_rejected(self):
        """Same nonce rejected on second use."""
        self.store.check_and_record("nonce-123")
        valid, reason = self.store.check_and_record("nonce-123")
        self.assertFalse(valid)
        self.assertEqual(reason, "replay")

    def test_empty_nonce_rejected(self):
        """Empty nonce rejected."""
        valid, reason = self.store.check_and_record("")
        self.assertFalse(valid)
        self.assertEqual(reason, "empty")

    def test_different_nonces_accepted(self):
        """Different nonces are accepted."""
        for i in range(100):
            valid, reason = self.store.check_and_record(str(uuid.uuid4()))
            self.assertTrue(valid)

    def test_timestamp_valid(self):
        """Current timestamp is valid."""
        now = datetime.now(timezone.utc).isoformat()
        valid, reason = self.store.validate_timestamp(now)
        self.assertTrue(valid)
        self.assertEqual(reason, "ok")

    def test_timestamp_expired(self):
        """Old timestamp is rejected."""
        old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        valid, reason = self.store.validate_timestamp(old)
        self.assertFalse(valid)
        self.assertEqual(reason, "expired")

    def test_timestamp_future(self):
        """Far-future timestamp is rejected."""
        future = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()
        valid, reason = self.store.validate_timestamp(future)
        self.assertFalse(valid)
        self.assertEqual(reason, "future")

    def test_timestamp_invalid_format(self):
        """Invalid timestamp string is rejected."""
        valid, reason = self.store.validate_timestamp("not-a-timestamp")
        self.assertFalse(valid)
        self.assertEqual(reason, "invalid")

    def test_validate_packet_freshness(self):
        """Combined nonce + timestamp validation."""
        nonce = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()
        valid, reason = self.store.validate_packet_freshness(nonce, ts)
        self.assertTrue(valid)
        self.assertEqual(reason, "ok")

    def test_validate_packet_replay(self):
        """Replay detected in combined validation."""
        nonce = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()
        self.store.validate_packet_freshness(nonce, ts)
        
        # Replay
        valid, reason = self.store.validate_packet_freshness(nonce, ts)
        self.assertFalse(valid)
        self.assertIn("replay", reason)

    def test_purge_expired(self):
        """Purge removes old nonces."""
        store = NonceStore(nonce_ttl=1)  # 1 second TTL
        store.check_and_record("old-nonce")
        time.sleep(1.5)
        purged = store.purge_expired()
        self.assertEqual(purged, 1)

    def test_stats(self):
        """get_stats() returns proper info."""
        self.store.check_and_record("n1")
        self.store.check_and_record("n2")
        stats = self.store.get_stats()
        self.assertEqual(stats["total_nonces"], 2)


# ═══════════════════════════════════════════════════
# TEST 6: End-to-End Signed Packet Flow
# ═══════════════════════════════════════════════════

class TestEndToEndFlow(unittest.TestCase):
    """Test full ASUS → sign → Dell verify → execute → sign result → ASUS verify."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.km = KeyManager(key_dir=self.temp_dir)
        self.km.generate_all_keys()
        self.asus_priv = self.km.load_private_key("asus")
        self.asus_pub = self.km.load_public_key("asus")
        self.dell_priv = self.km.load_private_key("dell")
        self.dell_pub = self.km.load_public_key("dell")
        self.nonce_store = NonceStore()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_command_flow(self):
        """Simulate ASUS sends signed command → Dell verifies → executes → returns signed result."""
        
        # ─── ASUS: Build and sign command ───
        intent = SystemIntent.SHUTDOWN
        ns = get_namespace(intent)
        group = get_capability_group(intent)
        
        command_packet = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent=ns,
            capability_group=group.value,
            tier=2,
            context={"delay_seconds": 10},
        )
        signed_command = PacketBuilder.sign_packet(command_packet, self.asus_priv)
        
        # ─── DELL: Validate structure ───
        valid, msg = PacketBuilder.validate_command_packet(signed_command)
        self.assertTrue(valid, msg)
        
        # ─── DELL: Verify ASUS signature ───
        self.assertTrue(PacketBuilder.verify_packet(signed_command, self.asus_pub))
        
        # ─── DELL: Check nonce + timestamp ───
        fresh_valid, fresh_reason = self.nonce_store.validate_packet_freshness(
            signed_command["nonce"], signed_command["timestamp"]
        )
        self.assertTrue(fresh_valid, fresh_reason)
        
        # ─── DELL: Execute (simulated) ───
        result_packet = PacketBuilder.build_result_packet(
            node_id="dell-01",
            trace_id=signed_command["trace_id"],
            intent=signed_command["intent"],
            status="success",
            output="Shutdown initiated with 10s delay",
            exit_code=0,
        )
        signed_result = PacketBuilder.sign_packet(result_packet, self.dell_priv)
        
        # ─── ASUS: Verify Dell result signature ───
        self.assertTrue(PacketBuilder.verify_packet(signed_result, self.dell_pub))
        
        # ─── ASUS: Check trace_id matches ───
        self.assertEqual(signed_result["trace_id"], signed_command["trace_id"])
        self.assertEqual(signed_result["status"], "success")

    def test_replay_attack_blocked(self):
        """Replaying the same signed packet is rejected by nonce store."""
        command = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent="SYSTEM.POWER.RESTART",
            capability_group="POWER",
            tier=2,
        )
        signed = PacketBuilder.sign_packet(command, self.asus_priv)
        
        # First use — accepted
        valid1, _ = self.nonce_store.validate_packet_freshness(
            signed["nonce"], signed["timestamp"]
        )
        self.assertTrue(valid1)
        
        # Replay — rejected
        valid2, reason = self.nonce_store.validate_packet_freshness(
            signed["nonce"], signed["timestamp"]
        )
        self.assertFalse(valid2)
        self.assertIn("replay", reason)

    def test_tampered_command_rejected(self):
        """Tampered command packet is rejected by signature verification."""
        command = PacketBuilder.build_command_packet(
            node_id="dell-01",
            intent="FILESYSTEM.FILE.DELETE",
            capability_group="FILESYSTEM",
            tier=2,
            context={"path": "test.txt"},
        )
        signed = PacketBuilder.sign_packet(command, self.asus_priv)
        
        # Tamper: change path
        signed["context"]["path"] = "C:\\Windows\\System32"
        
        # Signature should now fail
        self.assertFalse(PacketBuilder.verify_packet(signed, self.asus_pub))

    def test_capability_group_isolation(self):
        """Verify that intent maps to correct capability group."""
        test_cases = [
            (SystemIntent.SHUTDOWN, CapabilityGroup.POWER),
            (SystemIntent.OPEN_APP, CapabilityGroup.APPLICATION),
            (SystemIntent.DELETE_FILE, CapabilityGroup.FILESYSTEM),
            (SystemIntent.SEND_MESSAGE, CapabilityGroup.COMMUNICATION),
            (SystemIntent.FORMAT_DISK, CapabilityGroup.SYSTEM),
        ]
        for intent, expected_group in test_cases:
            group = get_capability_group(intent)
            self.assertEqual(group, expected_group,
                           f"{intent} should be in {expected_group}, got {group}")


# ═══════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
