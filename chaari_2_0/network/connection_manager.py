# CHAARI 2.0 — ASUS network/connection_manager.py — TCP Client

# Responsibility:
#  Connect to Dell execution node
#    3-step handshake (hello → response → ack)
#    Send signed command packets
#    Receive signed result packets
#    Heartbeat thread (keep connection alive)
#    Auto-reconnect on disconnect
#    Connection registry (track Dell node status)


import os
import sys
import uuid
import socket
import logging
import threading
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chaari_2_0.network import (
    send_message, recv_message, ProtocolError,
    make_handshake_hello, make_handshake_ack, make_heartbeat,
    make_disconnect, PROTOCOL_VERSION,
)

logger = logging.getLogger("chaari.asus.connection")

ASUS_NODE_ID = "asus-01"
DEFAULT_DELL_HOST = "127.0.0.1"
DEFAULT_DELL_PORT = 9734
HEARTBEAT_INTERVAL = 30     
RECONNECT_INTERVAL = 10     
MAX_RECONNECT_ATTEMPTS = 0  


class NodeStatus:
    """Status of a remote execution node."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    HANDSHAKING = "handshaking"
    CONNECTED = "connected"
    UNAVAILABLE = "unavailable"


class ConnectionManager:
    """
    ASUS-side TCP client for communicating with Dell execution nodes.

    Usage:
        cm = ConnectionManager()
        cm.connect("127.0.0.1", 9734)
        result = cm.send_command(signed_packet)
        cm.disconnect()
    """

    def __init__(self, node_id: str = None):
        self._node_id = node_id or ASUS_NODE_ID
        self._socket: socket.socket = None
        self._connected = False
        self._peer_node_id: str = None
        self._status = NodeStatus.DISCONNECTED
        self._lock = threading.Lock()

        self._heartbeat_thread: threading.Thread = None
        self._heartbeat_running = False

        self._auto_reconnect = False
        self._reconnect_thread: threading.Thread = None
        self._dell_host: str = None
        self._dell_port: int = None

        self._registry: dict[str, dict] = {}

    def connect(self, host: str = None, port: int = None,
                auto_reconnect: bool = True, timeout: float = 10) -> bool:
        """
        Connect to a Dell execution node and perform handshake.

        Args:
            host: Dell node IP/hostname
            port: Dell node port
            auto_reconnect: Enable auto-reconnect on disconnect
            timeout: Connection timeout in seconds

        Returns:
            True if connected and handshake succeeded
        """
        host = host or DEFAULT_DELL_HOST
        port = port or DEFAULT_DELL_PORT
        self._dell_host = host
        self._dell_port = port
        self._auto_reconnect = auto_reconnect

        self._status = NodeStatus.CONNECTING
        self._update_registry(host, port, NodeStatus.CONNECTING)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))

            self._socket = sock
            self._status = NodeStatus.HANDSHAKING
            self._update_registry(host, port, NodeStatus.HANDSHAKING)

            peer = self._perform_handshake(sock)
            if not peer:
                sock.close()
                self._status = NodeStatus.DISCONNECTED
                self._update_registry(host, port, NodeStatus.DISCONNECTED, "handshake_failed")
                return False

            self._peer_node_id = peer
            self._connected = True
            self._status = NodeStatus.CONNECTED
            self._update_registry(host, port, NodeStatus.CONNECTED)

            logger.info(f"Connected to {peer} at {host}:{port}")
            print(f"  [NET] Connected to Dell node: {peer} ({host}:{port})")

            self._start_heartbeat()

            return True

        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            self._status = NodeStatus.UNAVAILABLE
            self._update_registry(host, port, NodeStatus.UNAVAILABLE, str(e))
            logger.warning(f"Connection failed to {host}:{port}: {e}")
            print(f"  [NET] ✗ Cannot reach Dell node at {host}:{port}: {e}")

            if auto_reconnect:
                self._start_reconnect()

            return False

    def disconnect(self, reason: str = "shutdown") -> None:
        """Gracefully disconnect from Dell node."""
        self._auto_reconnect = False
        self._stop_heartbeat()
        self._stop_reconnect()

        if self._socket and self._connected:
            try:
                send_message(self._socket, make_disconnect(self._node_id, reason))
            except Exception:
                pass
            try:
                self._socket.close()
            except Exception:
                pass

        self._socket = None
        self._connected = False
        self._peer_node_id = None
        self._status = NodeStatus.DISCONNECTED
        if self._dell_host:
            self._update_registry(self._dell_host, self._dell_port, NodeStatus.DISCONNECTED)
        logger.info("Disconnected from Dell node")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def status(self) -> str:
        return self._status

    @property
    def peer_node_id(self) -> str:
        return self._peer_node_id

    def send_command(self, packet: dict, timeout: float = 30) -> dict:
        """
        Send a signed command packet and wait for the result.

        Args:
            packet: Signed command packet dict
            timeout: Seconds to wait for result

        Returns:
            Result packet dict from Dell

        Raises:
            ConnectionError: If not connected
        """
        if not self._connected or not self._socket:
            raise ConnectionError("Not connected to Dell node")

        with self._lock:
            try:
                send_message(self._socket, packet)
                result = recv_message(self._socket, timeout=timeout)
                return result
            except (ConnectionError, socket.timeout, ProtocolError) as e:
                self._handle_disconnect(str(e))
                raise ConnectionError(f"Lost connection during command: {e}")

    def _perform_handshake(self, sock: socket.socket) -> str:
        """
        3-step handshake from ASUS side:
          1. Send HELLO to Dell
          2. Recv RESPONSE from Dell
          3. Send ACK to Dell

        Returns:
            Peer node_id if handshake succeeds, None if fails
        """
        try:
            my_nonce = str(uuid.uuid4())
            hello = make_handshake_hello(
                node_id=self._node_id,
                role="controller",
                nonce=my_nonce,
            )
            send_message(sock, hello)

            response = recv_message(sock, timeout=10)
            if response.get("type") != "handshake_response":
                logger.warning(f"Expected handshake_response, got: {response.get('type')}")
                return None
            if response.get("version") != PROTOCOL_VERSION:
                logger.warning(f"Version mismatch: {response.get('version')}")
                return None
            if response.get("peer_nonce") != my_nonce:
                logger.warning("Handshake response nonce mismatch")
                return None

            peer_node_id = response.get("node_id", "unknown")
            peer_nonce = response.get("nonce", "")

            ack = make_handshake_ack(
                node_id=self._node_id,
                peer_nonce=peer_nonce,
            )
            send_message(sock, ack)

            return peer_node_id

        except (ProtocolError, ConnectionError, socket.timeout) as e:
            logger.warning(f"Handshake failed: {e}")
            return None

    def _start_heartbeat(self) -> None:
        """Start heartbeat thread."""
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True,
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        """Stop heartbeat thread."""
        self._heartbeat_running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
            self._heartbeat_thread = None

    def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats, listen for acks."""
        missed = 0
        while self._heartbeat_running and self._connected:
            time.sleep(HEARTBEAT_INTERVAL)
            if not self._heartbeat_running or not self._connected:
                break

            with self._lock:
                try:
                    hb = make_heartbeat(self._node_id)
                    send_message(self._socket, hb)
                    ack = recv_message(self._socket, timeout=10)
                    if ack.get("type") == "heartbeat_ack":
                        missed = 0
                        if self._dell_host:
                            self._update_registry(
                                self._dell_host, self._dell_port,
                                NodeStatus.CONNECTED,
                            )
                    else:
                        missed += 1
                except Exception:
                    missed += 1

            if missed >= 3:
                logger.warning(f"Dell node unresponsive ({missed} missed heartbeats)")
                print(f"  [NET] ⚠ Dell node unresponsive — {missed} missed heartbeats")
                self._handle_disconnect("heartbeat_timeout")
                break

    def _handle_disconnect(self, reason: str) -> None:
        """Handle unexpected disconnect."""
        self._connected = False
        self._status = NodeStatus.UNAVAILABLE
        if self._dell_host:
            self._update_registry(self._dell_host, self._dell_port,
                                  NodeStatus.UNAVAILABLE, reason)
        try:
            self._socket.close()
        except Exception:
            pass
        self._socket = None

        if self._auto_reconnect:
            self._start_reconnect()

    def _start_reconnect(self) -> None:
        """Start background reconnect attempts."""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop, daemon=True,
        )
        self._reconnect_thread.start()

    def _stop_reconnect(self) -> None:
        """Stop reconnect thread."""
        self._auto_reconnect = False
        if self._reconnect_thread:
            self._reconnect_thread.join(timeout=5)
            self._reconnect_thread = None

    def _reconnect_loop(self) -> None:
        """Attempt to reconnect periodically."""
        attempts = 0
        while self._auto_reconnect and not self._connected:
            attempts += 1
            print(f"  [NET] Reconnecting to Dell ({attempts})...")
            logger.info(f"Reconnect attempt {attempts}")

            if self.connect(self._dell_host, self._dell_port, auto_reconnect=False):
                self._auto_reconnect = True  
                print(f"  [NET] ✓ Reconnected to Dell")
                return

            if MAX_RECONNECT_ATTEMPTS > 0 and attempts >= MAX_RECONNECT_ATTEMPTS:
                logger.warning(f"Max reconnect attempts reached ({attempts})")
                print(f"  [NET] ✗ Max reconnect attempts reached")
                self._status = NodeStatus.UNAVAILABLE
                return

            time.sleep(RECONNECT_INTERVAL)

    def _update_registry(self, host: str, port: int, status: str,
                         error: str = None) -> None:
        """Update the connection registry entry for a node."""
        key = f"{host}:{port}"
        self._registry[key] = {
            "host": host,
            "port": port,
            "node_id": self._peer_node_id or "unknown",
            "status": status,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "error": error,
        }

    def get_registry(self) -> dict:
        """Get the full connection registry."""
        return dict(self._registry)

    def get_node_status(self, host: str = None, port: int = None) -> dict:
        """Get status for a specific node."""
        host = host or DEFAULT_DELL_HOST
        port = port or DEFAULT_DELL_PORT
        key = f"{host}:{port}"
        return self._registry.get(key, {"status": NodeStatus.DISCONNECTED})
