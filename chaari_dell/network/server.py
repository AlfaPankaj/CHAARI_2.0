# CHAARI 2.0 — Dell network/server.py — TCP Command Server
# ═══════════════════════════════════════════════════════════
# Responsibility:
#   ✔ Listen on LISTEN_PORT for ASUS connections
#   ✔ 3-step handshake (hello → response → ack)
#   ✔ IP whitelist enforcement
#   ✔ Receive signed command packets → forward to DellAgent
#   ✔ Send signed result packets back
#   ✔ Heartbeat response
#   ✔ Graceful disconnect handling
#
# Threading model:
#   Main thread: accept loop
#   Per-client thread: message recv/send loop
#   Heartbeat is handled inline (client sends, server acks)
# ═══════════════════════════════════════════════════════════

import os
import sys
import json
import uuid
import socket
import logging
import threading
import time
from datetime import datetime, timezone

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chaari_2_0.network import (
    send_message, recv_message, ProtocolError,
    make_handshake_response, make_handshake_ack, make_heartbeat_ack,
    PROTOCOL_VERSION,
)
from chaari_dell.config import (
    LISTEN_HOST, LISTEN_PORT, ASUS_IP_WHITELIST,
    NODE_ID, LOG_DIR, HEARTBEAT_INTERVAL,
)

logger = logging.getLogger("chaari.dell.server")


class DellServer:
    """
    TCP server for the Dell execution node.

    Accepts connections from ASUS, performs mutual handshake,
    then enters a message loop: receive commands, send results.
    """

    def __init__(self, agent):
        """
        Args:
            agent: DellAgent instance (must be booted)
        """
        self._agent = agent
        self._server_socket: socket.socket = None
        self._running = False
        self._clients: dict[str, dict] = {}  # node_id → client info
        self._lock = threading.Lock()

    def start(self, host: str = None, port: int = None) -> None:
        """Start the TCP server (blocking)."""
        host = host or LISTEN_HOST
        port = port or LISTEN_PORT

        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.settimeout(1.0)  # Allow periodic shutdown check
        self._server_socket.bind((host, port))
        self._server_socket.listen(5)
        self._running = True

        print(f"  [NET] Dell server listening on {host}:{port}")
        logger.info(f"Server started on {host}:{port}")

        while self._running:
            try:
                client_sock, addr = self._server_socket.accept()
                client_ip = addr[0]

                # IP whitelist check
                if client_ip not in ASUS_IP_WHITELIST:
                    logger.warning(f"Rejected connection from unauthorized IP: {client_ip}")
                    print(f"  [NET] ✗ Rejected: {client_ip} (not in whitelist)")
                    client_sock.close()
                    continue

                print(f"  [NET] ✓ Accepted connection from {client_ip}:{addr[1]}")
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, addr),
                    daemon=True,
                )
                thread.start()

            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    logger.error("Server socket error", exc_info=True)
                break

    def stop(self) -> None:
        """Stop the server gracefully."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        # Close all client connections
        with self._lock:
            for cid, info in self._clients.items():
                try:
                    info["socket"].close()
                except Exception:
                    pass
            self._clients.clear()
        logger.info("Server stopped")
        print("  [NET] Server stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_connected_clients(self) -> dict:
        """Get info about connected clients."""
        with self._lock:
            return {
                cid: {
                    "node_id": info.get("node_id", "unknown"),
                    "ip": info.get("ip"),
                    "connected_at": info.get("connected_at"),
                    "last_heartbeat": info.get("last_heartbeat"),
                }
                for cid, info in self._clients.items()
            }

    # ══════════════════════════════════════════
    # CLIENT HANDLER
    # ══════════════════════════════════════════

    def _handle_client(self, sock: socket.socket, addr: tuple) -> None:
        """Handle a single ASUS client connection."""
        client_ip = addr[0]
        client_id = f"{client_ip}:{addr[1]}"

        try:
            # ── Step 1: Handshake ──
            peer_node_id = self._perform_handshake(sock, client_ip)
            if not peer_node_id:
                sock.close()
                return

            # Register client
            with self._lock:
                self._clients[client_id] = {
                    "socket": sock,
                    "node_id": peer_node_id,
                    "ip": client_ip,
                    "connected_at": datetime.now(timezone.utc).isoformat(),
                    "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                }

            print(f"  [NET] Handshake complete with {peer_node_id}")
            logger.info(f"Handshake complete: {peer_node_id} from {client_ip}")

            # ── Step 2: Message loop ──
            self._message_loop(sock, client_id, peer_node_id, client_ip)

        except ConnectionError as e:
            logger.info(f"Client {client_id} disconnected: {e}")
            print(f"  [NET] Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Client handler error: {e}", exc_info=True)
            print(f"  [NET] Error handling {client_id}: {e}")
        finally:
            with self._lock:
                self._clients.pop(client_id, None)
            try:
                sock.close()
            except Exception:
                pass

    def _perform_handshake(self, sock: socket.socket, client_ip: str) -> str:
        """
        3-step handshake:
          1. Recv HELLO from ASUS
          2. Send RESPONSE to ASUS
          3. Recv ACK from ASUS

        Returns:
            Peer node_id if handshake succeeds, None if fails
        """
        try:
            # Step 1: Receive HELLO
            hello = recv_message(sock, timeout=10)
            if hello.get("type") != "handshake_hello":
                logger.warning(f"Expected handshake_hello, got: {hello.get('type')}")
                return None
            if hello.get("version") != PROTOCOL_VERSION:
                logger.warning(f"Version mismatch: {hello.get('version')}")
                return None

            peer_node_id = hello.get("node_id", "unknown")
            peer_nonce = hello.get("nonce", "")

            # Step 2: Send RESPONSE
            my_nonce = str(uuid.uuid4())
            response = make_handshake_response(
                node_id=NODE_ID,
                role="executor",
                nonce=my_nonce,
                peer_nonce=peer_nonce,
            )
            send_message(sock, response)

            # Step 3: Receive ACK
            ack = recv_message(sock, timeout=10)
            if ack.get("type") != "handshake_ack":
                logger.warning(f"Expected handshake_ack, got: {ack.get('type')}")
                return None
            if ack.get("peer_nonce") != my_nonce:
                logger.warning("Handshake ACK nonce mismatch")
                return None

            return peer_node_id

        except (ProtocolError, ConnectionError, socket.timeout) as e:
            logger.warning(f"Handshake failed: {e}")
            return None

    def _message_loop(self, sock: socket.socket, client_id: str,
                      peer_node_id: str, client_ip: str) -> None:
        """Main recv/process/reply loop for a connected ASUS client."""
        missed_heartbeats = 0

        while self._running:
            try:
                msg = recv_message(sock, timeout=HEARTBEAT_INTERVAL * 2)
                msg_type = msg.get("type", "")

                if msg_type == "heartbeat":
                    # Respond with heartbeat_ack
                    ack = make_heartbeat_ack(NODE_ID)
                    send_message(sock, ack)
                    missed_heartbeats = 0
                    with self._lock:
                        if client_id in self._clients:
                            self._clients[client_id]["last_heartbeat"] = \
                                datetime.now(timezone.utc).isoformat()

                elif msg_type == "command":
                    # Process through DellAgent
                    result = self._agent.process_packet(msg, source_ip=client_ip)
                    send_message(sock, result)
                    logger.info(f"Executed: {msg.get('intent')} → {result.get('status')}")

                elif msg_type == "disconnect":
                    logger.info(f"Client {peer_node_id} disconnecting: {msg.get('reason')}")
                    print(f"  [NET] {peer_node_id} disconnected: {msg.get('reason', 'unknown')}")
                    break

                else:
                    logger.warning(f"Unknown message type: {msg_type}")

            except socket.timeout:
                missed_heartbeats += 1
                if missed_heartbeats >= 3:
                    logger.warning(f"Client {peer_node_id} missed {missed_heartbeats} heartbeats")
                    print(f"  [NET] ⚠ {peer_node_id}: no heartbeat (missed {missed_heartbeats})")
                    break
            except ConnectionError:
                break
