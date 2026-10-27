"""
p2p/protocol.py
Defines the wire protocol, message structures, and binary/JSON framing for TCP socket communication.
Part of the P2P File Distribution System (CS-30003 - Assignment 1).
"""

import json
import struct
import socket
from typing import Dict, Any, Tuple, Optional

# Message Type Constants
MSG_REGISTER = "REGISTER"
MSG_UNREGISTER = "UNREGISTER"
MSG_DISCOVER = "DISCOVER"
MSG_PEER_LIST = "PEER_LIST"
MSG_HANDSHAKE = "HANDSHAKE"
MSG_HANDSHAKE_ACK = "HANDSHAKE_ACK"
MSG_BITFIELD = "BITFIELD"
MSG_HAVE = "HAVE"
MSG_REQUEST_PIECE = "REQUEST_PIECE"
MSG_PIECE_DATA = "PIECE_DATA"
MSG_PIECE_NOT_FOUND = "PIECE_NOT_FOUND"
MSG_HEARTBEAT = "HEARTBEAT"
MSG_GOODBYE = "GOODBYE"


def send_msg(sock: socket.socket, header: Dict[str, Any], payload: bytes = b"") -> None:
    """
    Sends a framed message over a TCP socket.
    Framing format:
      [4 bytes: Header Length (Network Endian 'I')]
      [4 bytes: Payload Length (Network Endian 'I')]
      [Header bytes (UTF-8 JSON)]
      [Payload bytes (Raw binary)]
    """
    header_json = json.dumps(header).encode("utf-8")
    header_len = len(header_json)
    payload_len = len(payload)
    
    prefix = struct.pack("!II", header_len, payload_len)
    sock.sendall(prefix + header_json + payload)


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """Helper to receive exactly num_bytes from socket, raising EOFError if connection closes prematurely."""
    buffer = bytearray()
    while len(buffer) < num_bytes:
        chunk = sock.recv(min(num_bytes - len(buffer), 65536))
        if not chunk:
            raise ConnectionResetError("Socket connection closed while reading expected bytes.")
        buffer.extend(chunk)
    return bytes(buffer)


def recv_msg(sock: socket.socket) -> Tuple[Dict[str, Any], bytes]:
    """
    Receives a framed message from a TCP socket.
    Returns: (header_dict, payload_bytes)
    """
    prefix = recv_exact(sock, 8)
    header_len, payload_len = struct.unpack("!II", prefix)
    
    header_raw = recv_exact(sock, header_len)
    header = json.loads(header_raw.decode("utf-8"))
    
    payload = recv_exact(sock, payload_len) if payload_len > 0 else b""
    return header, payload
