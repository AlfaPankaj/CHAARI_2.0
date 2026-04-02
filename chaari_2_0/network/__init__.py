# CHAARI 2.0 — Shared Network Protocol
# ═══════════════════════════════════════════════════════════
# Length-prefixed JSON framing over TCP.
# Used by both ASUS (client) and Dell (server).
#
# Wire format:
#   [4 bytes: big-endian payload length][JSON payload bytes]
#
# This is the ONLY module that touches raw sockets.
# Everything above works with dicts.
# ═══════════════════════════════════════════════════════════

import json
import struct
import socket
from datetime import datetime, timezone

HEADER_SIZE = 4                   
MAX_PAYLOAD_BYTES = 1_048_576     
SOCKET_TIMEOUT = 30              
PROTOCOL_VERSION = "2.0"


class ProtocolError(Exception):
    """Raised on protocol-level failures (bad frame, oversized, etc.)."""
    pass


def send_message(sock: socket.socket, data: dict) -> None:
    """
    Send a length-prefixed JSON message.

    Raises:
        ProtocolError: If payload exceeds MAX_PAYLOAD_BYTES
    """
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    length = len(payload)
    if length > MAX_PAYLOAD_BYTES:
        raise ProtocolError(f"Payload too large: {length} bytes (max {MAX_PAYLOAD_BYTES})")
    header = struct.pack("!I", length)
    sock.sendall(header + payload)


def recv_message(sock: socket.socket, timeout: float = SOCKET_TIMEOUT) -> dict:
    """
    Receive a length-prefixed JSON message.

    Returns:
        Parsed dict from the JSON payload

    Raises:
        ProtocolError: On framing or size errors
        ConnectionError: If peer disconnects
        socket.timeout: If no data within timeout
    """
    old_timeout = sock.gettimeout()
    sock.settimeout(timeout)
    try:
        header = _recv_exact(sock, HEADER_SIZE)
        length = struct.unpack("!I", header)[0]
        if length > MAX_PAYLOAD_BYTES:
            raise ProtocolError(f"Frame too large: {length} bytes")
        if length == 0:
            raise ProtocolError("Empty frame")
        payload = _recv_exact(sock, length)
        return json.loads(payload.decode("utf-8"))
    finally:
        sock.settimeout(old_timeout)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes from socket."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed by peer")
        buf.extend(chunk)
    return bytes(buf)


def make_handshake_hello(node_id: str, role: str, nonce: str) -> dict:
    """Build a handshake HELLO message."""
    return {
        "type": "handshake_hello",
        "version": PROTOCOL_VERSION,
        "node_id": node_id,
        "role": role,
        "nonce": nonce,
    }


def make_handshake_response(node_id: str, role: str, nonce: str, peer_nonce: str) -> dict:
    """Build a handshake RESPONSE message."""
    return {
        "type": "handshake_response",
        "version": PROTOCOL_VERSION,
        "node_id": node_id,
        "role": role,
        "nonce": nonce,
        "peer_nonce": peer_nonce,
    }


def make_handshake_ack(node_id: str, peer_nonce: str) -> dict:
    """Build a handshake ACK (final step)."""
    return {
        "type": "handshake_ack",
        "version": PROTOCOL_VERSION,
        "node_id": node_id,
        "peer_nonce": peer_nonce,
    }


def make_heartbeat(node_id: str, status: str = "alive") -> dict:
    """Build a heartbeat message."""
    return {
        "type": "heartbeat",
        "node_id": node_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def make_heartbeat_ack(node_id: str) -> dict:
    """Build a heartbeat acknowledgement."""
    return {
        "type": "heartbeat_ack",
        "node_id": node_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def make_disconnect(node_id: str, reason: str = "shutdown") -> dict:
    """Build a graceful disconnect message."""
    return {
        "type": "disconnect",
        "node_id": node_id,
        "reason": reason,
    }
