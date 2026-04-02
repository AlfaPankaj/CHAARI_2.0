# CHAARI 2.0 — Phase 5 Test Suite — Network Layer
# ═══════════════════════════════════════════════════════════
# Tests for:
#   - Wire protocol (length-prefixed JSON framing)
#   - Message constructors
#   - 3-step handshake (ASUS ↔ Dell)
#   - Heartbeat exchange
#   - Command send/receive over TCP
#   - Connection registry
#   - Disconnect/reconnect
#   - End-to-end signed flow over network
#
# Run: python -B -m unittest test_phase5_network -v
# ═══════════════════════════════════════════════════════════

import os
import sys
import json
import time
import struct
import socket
import threading
import unittest
import tempfile
import shutil
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chaari_2_0.network import (
    send_message, recv_message, ProtocolError,
    make_handshake_hello, make_handshake_response, make_handshake_ack,
    make_heartbeat, make_heartbeat_ack, make_disconnect,
    HEADER_SIZE, MAX_PAYLOAD_BYTES, PROTOCOL_VERSION,
)


# ══════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════

def create_socket_pair():
    """Create a connected pair of TCP sockets via loopback."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    peer, _ = server.accept()

    server.close()
    return client, peer


# ══════════════════════════════════════════════════════════════
# TEST 1: WIRE PROTOCOL
# ══════════════════════════════════════════════════════════════

class TestWireProtocol(unittest.TestCase):
    """Test length-prefixed JSON framing."""

    def setUp(self):
        self.client, self.peer = create_socket_pair()

    def tearDown(self):
        self.client.close()
        self.peer.close()

    def test_send_recv_simple(self):
        data = {"type": "test", "value": 42}
        send_message(self.client, data)
        result = recv_message(self.peer, timeout=5)
        self.assertEqual(result, data)

    def test_send_recv_unicode(self):
        data = {"text": "Hello Boss! 🤖 नमस्ते"}
        send_message(self.client, data)
        result = recv_message(self.peer, timeout=5)
        self.assertEqual(result["text"], "Hello Boss! 🤖 नमस्ते")

    def test_send_recv_empty_dict(self):
        send_message(self.client, {})
        result = recv_message(self.peer, timeout=5)
        self.assertEqual(result, {})

    def test_send_recv_nested(self):
        data = {"a": {"b": {"c": [1, 2, 3]}}, "d": None}
        send_message(self.client, data)
        result = recv_message(self.peer, timeout=5)
        self.assertEqual(result, data)

    def test_send_recv_large(self):
        data = {"payload": "X" * 100_000}
        send_message(self.client, data)
        result = recv_message(self.peer, timeout=5)
        self.assertEqual(len(result["payload"]), 100_000)

    def test_multiple_messages(self):
        for i in range(10):
            send_message(self.client, {"seq": i})
        for i in range(10):
            result = recv_message(self.peer, timeout=5)
            self.assertEqual(result["seq"], i)

    def test_payload_too_large_raises(self):
        data = {"payload": "X" * (MAX_PAYLOAD_BYTES + 1)}
        with self.assertRaises(ProtocolError):
            send_message(self.client, data)

    def test_recv_timeout(self):
        self.peer.settimeout(0.5)
        with self.assertRaises(socket.timeout):
            recv_message(self.client, timeout=0.5)

    def test_recv_closed_connection(self):
        self.peer.close()
        with self.assertRaises(ConnectionError):
            recv_message(self.client, timeout=2)

    def test_header_is_4_bytes(self):
        self.assertEqual(HEADER_SIZE, 4)

    def test_frame_format(self):
        """Verify raw wire format: 4-byte length + JSON."""
        data = {"key": "val"}
        send_message(self.client, data)

        # Read raw header
        header = b""
        while len(header) < 4:
            header += self.peer.recv(4 - len(header))
        length = struct.unpack("!I", header)[0]

        # Read raw payload
        payload = b""
        while len(payload) < length:
            payload += self.peer.recv(length - len(payload))

        parsed = json.loads(payload.decode("utf-8"))
        self.assertEqual(parsed, data)


# ══════════════════════════════════════════════════════════════
# TEST 2: MESSAGE CONSTRUCTORS
# ══════════════════════════════════════════════════════════════

class TestMessageConstructors(unittest.TestCase):
    """Test protocol message constructors."""

    def test_handshake_hello(self):
        msg = make_handshake_hello("asus-01", "controller", "nonce-123")
        self.assertEqual(msg["type"], "handshake_hello")
        self.assertEqual(msg["node_id"], "asus-01")
        self.assertEqual(msg["role"], "controller")
        self.assertEqual(msg["nonce"], "nonce-123")
        self.assertEqual(msg["version"], PROTOCOL_VERSION)

    def test_handshake_response(self):
        msg = make_handshake_response("dell-01", "executor", "my-nonce", "peer-nonce")
        self.assertEqual(msg["type"], "handshake_response")
        self.assertEqual(msg["node_id"], "dell-01")
        self.assertEqual(msg["peer_nonce"], "peer-nonce")

    def test_handshake_ack(self):
        msg = make_handshake_ack("asus-01", "peer-nonce")
        self.assertEqual(msg["type"], "handshake_ack")
        self.assertEqual(msg["peer_nonce"], "peer-nonce")

    def test_heartbeat(self):
        msg = make_heartbeat("asus-01")
        self.assertEqual(msg["type"], "heartbeat")
        self.assertEqual(msg["status"], "alive")
        self.assertIn("timestamp", msg)

    def test_heartbeat_ack(self):
        msg = make_heartbeat_ack("dell-01")
        self.assertEqual(msg["type"], "heartbeat_ack")
        self.assertIn("timestamp", msg)

    def test_disconnect(self):
        msg = make_disconnect("asus-01", "user_quit")
        self.assertEqual(msg["type"], "disconnect")
        self.assertEqual(msg["reason"], "user_quit")

    def test_disconnect_default_reason(self):
        msg = make_disconnect("asus-01")
        self.assertEqual(msg["reason"], "shutdown")


# ══════════════════════════════════════════════════════════════
# TEST 3: HANDSHAKE OVER SOCKETS
# ══════════════════════════════════════════════════════════════

class TestHandshakeOverSockets(unittest.TestCase):
    """Test 3-step handshake over real sockets."""

    def setUp(self):
        self.client, self.server = create_socket_pair()

    def tearDown(self):
        self.client.close()
        self.server.close()

    def test_full_handshake(self):
        """Simulate ASUS (client) ↔ Dell (server) handshake."""
        # Step 1: ASUS sends HELLO
        hello = make_handshake_hello("asus-01", "controller", "asus-nonce-1")
        send_message(self.client, hello)

        # Dell receives HELLO
        recv_hello = recv_message(self.server, timeout=5)
        self.assertEqual(recv_hello["type"], "handshake_hello")
        self.assertEqual(recv_hello["node_id"], "asus-01")

        # Step 2: Dell sends RESPONSE
        response = make_handshake_response(
            "dell-01", "executor", "dell-nonce-1", recv_hello["nonce"],
        )
        send_message(self.server, response)

        # ASUS receives RESPONSE
        recv_resp = recv_message(self.client, timeout=5)
        self.assertEqual(recv_resp["type"], "handshake_response")
        self.assertEqual(recv_resp["peer_nonce"], "asus-nonce-1")  # Echoed back
        self.assertEqual(recv_resp["node_id"], "dell-01")

        # Step 3: ASUS sends ACK
        ack = make_handshake_ack("asus-01", recv_resp["nonce"])
        send_message(self.client, ack)

        # Dell receives ACK
        recv_ack = recv_message(self.server, timeout=5)
        self.assertEqual(recv_ack["type"], "handshake_ack")
        self.assertEqual(recv_ack["peer_nonce"], "dell-nonce-1")

    def test_version_mismatch_detectable(self):
        """ASUS sends wrong version — Dell can detect."""
        hello = make_handshake_hello("asus-01", "controller", "n1")
        hello["version"] = "1.0"  # wrong
        send_message(self.client, hello)

        recv_hello = recv_message(self.server, timeout=5)
        self.assertNotEqual(recv_hello["version"], PROTOCOL_VERSION)

    def test_nonce_echo_correctness(self):
        """Verify nonce echoing in both directions."""
        hello = make_handshake_hello("asus-01", "controller", "ASUS_NONCE")
        send_message(self.client, hello)
        recv_hello = recv_message(self.server, timeout=5)

        response = make_handshake_response("dell-01", "executor", "DELL_NONCE", recv_hello["nonce"])
        send_message(self.server, response)
        recv_resp = recv_message(self.client, timeout=5)

        self.assertEqual(recv_resp["peer_nonce"], "ASUS_NONCE")

        ack = make_handshake_ack("asus-01", recv_resp["nonce"])
        send_message(self.client, ack)
        recv_ack = recv_message(self.server, timeout=5)

        self.assertEqual(recv_ack["peer_nonce"], "DELL_NONCE")


# ══════════════════════════════════════════════════════════════
# TEST 4: HEARTBEAT OVER SOCKETS
# ══════════════════════════════════════════════════════════════

class TestHeartbeatOverSockets(unittest.TestCase):
    """Test heartbeat exchange over real sockets."""

    def setUp(self):
        self.client, self.server = create_socket_pair()

    def tearDown(self):
        self.client.close()
        self.server.close()

    def test_heartbeat_round_trip(self):
        hb = make_heartbeat("asus-01")
        send_message(self.client, hb)

        recv_hb = recv_message(self.server, timeout=5)
        self.assertEqual(recv_hb["type"], "heartbeat")
        self.assertEqual(recv_hb["status"], "alive")

        ack = make_heartbeat_ack("dell-01")
        send_message(self.server, ack)

        recv_ack = recv_message(self.client, timeout=5)
        self.assertEqual(recv_ack["type"], "heartbeat_ack")

    def test_multiple_heartbeats(self):
        for i in range(5):
            hb = make_heartbeat("asus-01")
            send_message(self.client, hb)
            recv_hb = recv_message(self.server, timeout=5)
            self.assertEqual(recv_hb["type"], "heartbeat")

            ack = make_heartbeat_ack("dell-01")
            send_message(self.server, ack)
            recv_ack = recv_message(self.client, timeout=5)
            self.assertEqual(recv_ack["type"], "heartbeat_ack")


# ══════════════════════════════════════════════════════════════
# TEST 5: COMMAND FLOW OVER SOCKETS
# ══════════════════════════════════════════════════════════════

class TestCommandFlowOverSockets(unittest.TestCase):
    """Test signed command → result flow over TCP."""

    def setUp(self):
        self.client, self.server = create_socket_pair()

    def tearDown(self):
        self.client.close()
        self.server.close()

    def test_command_and_result(self):
        """ASUS sends command, Dell sends result."""
        command = {
            "type": "command",
            "version": "2.0",
            "node_id": "dell-01",
            "intent": "FILESYSTEM.FILE.CREATE",
            "capability_group": "FILESYSTEM",
            "tier": 1,
            "context": {"path": "test.txt"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": "cmd-nonce-1",
            "trace_id": "trace-001",
            "signature": "fake-sig",
        }
        send_message(self.client, command)
        recv_cmd = recv_message(self.server, timeout=5)
        self.assertEqual(recv_cmd["type"], "command")
        self.assertEqual(recv_cmd["intent"], "FILESYSTEM.FILE.CREATE")

        result = {
            "type": "result",
            "version": "2.0",
            "node_id": "dell-01",
            "trace_id": recv_cmd["trace_id"],
            "intent": recv_cmd["intent"],
            "status": "success",
            "output": "Created file: test.txt",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        send_message(self.server, result)
        recv_result = recv_message(self.client, timeout=5)
        self.assertEqual(recv_result["status"], "success")
        self.assertEqual(recv_result["trace_id"], "trace-001")


# ══════════════════════════════════════════════════════════════
# TEST 6: DISCONNECT FLOW
# ══════════════════════════════════════════════════════════════

class TestDisconnectFlow(unittest.TestCase):
    """Test graceful disconnect."""

    def setUp(self):
        self.client, self.server = create_socket_pair()

    def tearDown(self):
        try:
            self.client.close()
        except Exception:
            pass
        try:
            self.server.close()
        except Exception:
            pass

    def test_graceful_disconnect(self):
        dc = make_disconnect("asus-01", "user_quit")
        send_message(self.client, dc)
        recv_dc = recv_message(self.server, timeout=5)
        self.assertEqual(recv_dc["type"], "disconnect")
        self.assertEqual(recv_dc["reason"], "user_quit")

    def test_abrupt_close_detected(self):
        """If client closes, server gets ConnectionError on recv."""
        self.client.close()
        with self.assertRaises(ConnectionError):
            recv_message(self.server, timeout=2)


# ══════════════════════════════════════════════════════════════
# TEST 7: CONNECTION MANAGER (unit tests)
# ══════════════════════════════════════════════════════════════

class TestConnectionManager(unittest.TestCase):
    """Test ASUS ConnectionManager (unit)."""

    def test_initial_state(self):
        from chaari_2_0.network.connection_manager import ConnectionManager, NodeStatus
        cm = ConnectionManager("test-01")
        self.assertFalse(cm.is_connected)
        self.assertEqual(cm.status, NodeStatus.DISCONNECTED)
        self.assertIsNone(cm.peer_node_id)

    def test_registry_empty_initially(self):
        from chaari_2_0.network.connection_manager import ConnectionManager
        cm = ConnectionManager()
        self.assertEqual(cm.get_registry(), {})

    def test_send_command_not_connected_raises(self):
        from chaari_2_0.network.connection_manager import ConnectionManager
        cm = ConnectionManager()
        with self.assertRaises(ConnectionError):
            cm.send_command({"type": "command"})

    def test_connect_refused(self):
        """Connect to a port with nothing listening."""
        from chaari_2_0.network.connection_manager import ConnectionManager, NodeStatus
        cm = ConnectionManager()
        ok = cm.connect("127.0.0.1", 19999, auto_reconnect=False, timeout=2)
        self.assertFalse(ok)
        self.assertIn(cm.status, (NodeStatus.UNAVAILABLE, NodeStatus.DISCONNECTED))


# ══════════════════════════════════════════════════════════════
# TEST 8: FULL SERVER + CLIENT INTEGRATION
# ══════════════════════════════════════════════════════════════

class TestServerClientIntegration(unittest.TestCase):
    """Test DellServer + ConnectionManager talking to each other."""

    @classmethod
    def setUpClass(cls):
        """Start a Dell server with a mock agent on a random port."""
        # Mock agent that returns success for any packet
        cls.mock_agent = MagicMock()
        cls.mock_agent._booted = True
        cls.mock_agent.process_packet.return_value = {
            "version": "2.0",
            "type": "result",
            "node_id": "dell-01",
            "intent": "test",
            "trace_id": "t1",
            "status": "success",
            "output": "mock result",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        from chaari_dell.network.server import DellServer
        cls.server = DellServer(cls.mock_agent)

        # Find a free port
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        cls.port = s.getsockname()[1]
        s.close()

        # Start server in background thread
        cls.server_thread = threading.Thread(
            target=cls.server.start,
            kwargs={"host": "127.0.0.1", "port": cls.port},
            daemon=True,
        )
        cls.server_thread.start()
        time.sleep(0.5)  # Let server start

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.server_thread.join(timeout=3)

    def test_connect_handshake_disconnect(self):
        """Full flow: connect → handshake → disconnect."""
        from chaari_2_0.network.connection_manager import ConnectionManager
        cm = ConnectionManager("asus-test")
        ok = cm.connect("127.0.0.1", self.port, auto_reconnect=False)
        self.assertTrue(ok, "Connection should succeed")
        self.assertTrue(cm.is_connected)
        self.assertEqual(cm.peer_node_id, "dell-01")
        cm.disconnect()
        self.assertFalse(cm.is_connected)

    def test_send_command_receives_result(self):
        """Send command over TCP, get result back."""
        from chaari_2_0.network.connection_manager import ConnectionManager
        cm = ConnectionManager("asus-test-cmd")
        cm.connect("127.0.0.1", self.port, auto_reconnect=False)
        self.assertTrue(cm.is_connected)

        command = {
            "type": "command",
            "version": "2.0",
            "node_id": "dell-01",
            "intent": "FILESYSTEM.FILE.CREATE",
            "capability_group": "FILESYSTEM",
            "tier": 1,
            "context": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": "test-cmd-1",
            "trace_id": "trace-cmd-1",
            "signature": "fake",
        }
        result = cm.send_command(command)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["output"], "mock result")
        cm.disconnect()

    def test_multiple_commands(self):
        """Send multiple commands in sequence."""
        from chaari_2_0.network.connection_manager import ConnectionManager
        cm = ConnectionManager("asus-multi")
        cm.connect("127.0.0.1", self.port, auto_reconnect=False)

        for i in range(5):
            cmd = {
                "type": "command", "version": "2.0", "node_id": "dell-01",
                "intent": f"TEST.CMD.{i}", "capability_group": "FILESYSTEM",
                "tier": 1, "context": {}, "nonce": f"n-{i}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": f"t-{i}", "signature": "fake",
            }
            result = cm.send_command(cmd)
            self.assertEqual(result["status"], "success")

        cm.disconnect()

    def test_registry_updates(self):
        """Connection registry tracks node status."""
        from chaari_2_0.network.connection_manager import ConnectionManager, NodeStatus
        cm = ConnectionManager("asus-reg")
        cm.connect("127.0.0.1", self.port, auto_reconnect=False)

        reg = cm.get_registry()
        key = f"127.0.0.1:{self.port}"
        self.assertIn(key, reg)
        self.assertEqual(reg[key]["status"], NodeStatus.CONNECTED)

        cm.disconnect()
        reg = cm.get_registry()
        self.assertEqual(reg[key]["status"], NodeStatus.DISCONNECTED)

    def test_server_client_list(self):
        """Server tracks connected clients."""
        from chaari_2_0.network.connection_manager import ConnectionManager
        cm = ConnectionManager("asus-list")
        cm.connect("127.0.0.1", self.port, auto_reconnect=False)
        time.sleep(0.3)

        clients = self.server.get_connected_clients()
        self.assertGreater(len(clients), 0)

        cm.disconnect()


# ══════════════════════════════════════════════════════════════
# TEST 9: END-TO-END WITH REAL CRYPTO
# ══════════════════════════════════════════════════════════════

class TestEndToEndCrypto(unittest.TestCase):
    """Test full signed command flow: ASUS signs → TCP → Dell validates."""

    @classmethod
    def setUpClass(cls):
        """Generate keys and start Dell server with real agent."""
        cls.key_dir = tempfile.mkdtemp(prefix="chaari_e2e_keys_")

        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend

            for name in ("asus", "dell"):
                priv = rsa.generate_private_key(65537, 2048, default_backend())
                pub = priv.public_key()
                with open(os.path.join(cls.key_dir, f"{name}_private.pem"), "wb") as f:
                    f.write(priv.private_bytes(
                        serialization.Encoding.PEM,
                        serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption(),
                    ))
                with open(os.path.join(cls.key_dir, f"{name}_public.pem"), "wb") as f:
                    f.write(pub.public_bytes(
                        serialization.Encoding.PEM,
                        serialization.PublicFormat.SubjectPublicKeyInfo,
                    ))

            cls.keys_available = True
        except ImportError:
            cls.keys_available = False
            return

        # Create Dell agent with real crypto
        from chaari_dell.crypto.signature_verifier import SignatureVerifier
        from chaari_dell.crypto.validation_pipeline import ValidationPipeline
        from chaari_dell.crypto.nonce_store import DellNonceStore
        from chaari_dell.executor.capability_router import CapabilityRouter
        from chaari_dell.executor.filesystem_module import FilesystemModule
        from chaari_dell.executor.communication_module import CommunicationModule
        from chaari_dell.models.packet_models import ExecutionResult

        verifier = SignatureVerifier(cls.key_dir)
        verifier.load_keys("asus", "dell")
        nonce_store = DellNonceStore()
        pipeline = ValidationPipeline(verifier, nonce_store)
        router = CapabilityRouter()
        router.register("FILESYSTEM", FilesystemModule())
        router.register("COMMUNICATION", CommunicationModule())

        # Create a minimal agent-like object
        class MiniAgent:
            def __init__(self):
                self._booted = True
            def process_packet(self, packet, source_ip="127.0.0.1"):
                val = pipeline.validate(packet, source_ip)
                if not val.valid:
                    return {
                        "version": "2.0", "type": "result", "node_id": "dell-01",
                        "intent": packet.get("intent", "?"), "trace_id": packet.get("trace_id", "?"),
                        "status": "rejected", "error": val.reason,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                result = router.route(packet)
                result_pkt = {
                    "version": "2.0", "type": "result", "node_id": "dell-01",
                    "intent": result.intent, "trace_id": result.trace_id,
                    "status": result.status, "output": result.output or "",
                    "error": result.error or "",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                signed = verifier.sign_result(result_pkt)
                return signed or result_pkt

        cls.mini_agent = MiniAgent()

        from chaari_dell.network.server import DellServer
        cls.server = DellServer(cls.mini_agent)

        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        cls.port = s.getsockname()[1]
        s.close()

        cls.server_thread = threading.Thread(
            target=cls.server.start,
            kwargs={"host": "127.0.0.1", "port": cls.port},
            daemon=True,
        )
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'server'):
            cls.server.stop()
        if hasattr(cls, 'server_thread'):
            cls.server_thread.join(timeout=3)
        if hasattr(cls, 'key_dir'):
            shutil.rmtree(cls.key_dir, ignore_errors=True)

    def setUp(self):
        if not self.keys_available:
            self.skipTest("cryptography not available")

    def test_signed_command_over_network(self):
        """ASUS signs → TCP → Dell validates → executes → signs result → TCP → ASUS."""
        from chaari_2_0.network.connection_manager import ConnectionManager
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        import base64
        import uuid

        # Load ASUS private key to sign
        with open(os.path.join(self.key_dir, "asus_private.pem"), "rb") as f:
            asus_priv = serialization.load_pem_private_key(f.read(), None, default_backend())

        # Build command packet
        packet = {
            "version": "2.0", "type": "command", "node_id": "dell-01",
            "intent": "COMMUNICATION.MESSAGING.SEND",
            "capability_group": "COMMUNICATION", "tier": 1,
            "context": {"contact": "Bhaiya", "text": "Hello from network!", "platform": "whatsapp"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": str(uuid.uuid4()), "trace_id": str(uuid.uuid4()),
        }

        # Sign
        signable = {k: v for k, v in packet.items() if k != "signature"}
        canonical = json.dumps(signable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        sig = asus_priv.sign(
            canonical,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        packet["signature"] = base64.b64encode(sig).decode("ascii")

        # Connect and send
        cm = ConnectionManager("asus-e2e")
        ok = cm.connect("127.0.0.1", self.port, auto_reconnect=False)
        self.assertTrue(ok)

        result = cm.send_command(packet)
        self.assertEqual(result["status"], "success")
        self.assertIn("Bhaiya", result["output"])
        # Result should be signed by Dell
        self.assertIn("signature", result)

        cm.disconnect()

    def test_tampered_command_rejected(self):
        """Dell rejects commands with invalid signature."""
        from chaari_2_0.network.connection_manager import ConnectionManager
        import uuid

        packet = {
            "version": "2.0", "type": "command", "node_id": "dell-01",
            "intent": "FILESYSTEM.FILE.CREATE",
            "capability_group": "FILESYSTEM", "tier": 1,
            "context": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nonce": str(uuid.uuid4()), "trace_id": str(uuid.uuid4()),
            "signature": "invalid-signature-base64",
        }

        cm = ConnectionManager("asus-tamper")
        ok = cm.connect("127.0.0.1", self.port, auto_reconnect=False)
        self.assertTrue(ok)

        result = cm.send_command(packet)
        self.assertEqual(result["status"], "rejected")

        cm.disconnect()


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
