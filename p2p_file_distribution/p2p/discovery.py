"""
p2p/discovery.py
Lightweight Discovery and Rendezvous Tracker for peer registration and lookup.
Part of the P2P File Distribution System (Member 1 deliverable).
"""

import socket
import threading
import time
from typing import Dict, List, Any, Optional
from p2p.protocol import (
    send_msg, recv_msg,
    MSG_REGISTER, MSG_UNREGISTER, MSG_DISCOVER, MSG_PEER_LIST
)


class TrackerServer:
    """
    Lightweight TCP Discovery Tracker that maintains the swarm state.
    Tracks active peers and which files/pieces they are currently serving.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.running = False
        self.sock: Optional[socket.socket] = None
        self.server_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # {file_hash: {peer_id: {"ip": ip, "port": port, "last_seen": timestamp, "is_seeder": bool}}}
        self.swarm_registry: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def start(self) -> int:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        # If port was 0, get dynamically assigned OS port
        self.port = self.sock.getsockname()[1]
        self.sock.listen(128)
        self.running = True

        self.server_thread = threading.Thread(target=self._listen_loop, daemon=True, name="TrackerListener")
        self.server_thread.start()
        return self.port

    def stop(self) -> None:
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1.0)

    def _listen_loop(self) -> None:
        while self.running:
            try:
                client_sock, addr = self.sock.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(client_sock,),
                    daemon=True,
                    name=f"TrackerWorker-{addr}"
                ).start()
            except Exception:
                break

    def _handle_client(self, client_sock: socket.socket) -> None:
        try:
            while self.running:
                header, _ = recv_msg(client_sock)
                msg_type = header.get("type")

                if msg_type == MSG_REGISTER:
                    peer_id = header["peer_id"]
                    peer_ip = header["ip"]
                    peer_port = header["port"]
                    file_hashes = header.get("file_hashes", [])
                    is_seeder = header.get("is_seeder", False)

                    with self.lock:
                        for fh in file_hashes:
                            if fh not in self.swarm_registry:
                                self.swarm_registry[fh] = {}
                            self.swarm_registry[fh][peer_id] = {
                                "ip": peer_ip,
                                "port": peer_port,
                                "last_seen": time.time(),
                                "is_seeder": is_seeder
                            }
                    send_msg(client_sock, {"type": "ACK", "status": "REGISTERED"})

                elif msg_type == MSG_DISCOVER:
                    file_hash = header.get("file_hash")
                    exclude_peer = header.get("exclude_peer", "")
                    peers_out: List[Dict[str, Any]] = []

                    with self.lock:
                        if file_hash in self.swarm_registry:
                            now = time.time()
                            for pid, pinfo in list(self.swarm_registry[file_hash].items()):
                                if pid != exclude_peer:
                                    peers_out.append({
                                        "peer_id": pid,
                                        "ip": pinfo["ip"],
                                        "port": pinfo["port"],
                                        "is_seeder": pinfo["is_seeder"]
                                    })
                    send_msg(client_sock, {"type": MSG_PEER_LIST, "peers": peers_out})

                elif msg_type == MSG_UNREGISTER:
                    peer_id = header.get("peer_id")
                    with self.lock:
                        for fh in list(self.swarm_registry.keys()):
                            self.swarm_registry[fh].pop(peer_id, None)
                    send_msg(client_sock, {"type": "ACK", "status": "UNREGISTERED"})
                    break
                else:
                    break
        except (ConnectionResetError, EOFError, socket.error):
            pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass


class TrackerClient:
    """Helper client used by peers to register and query active swarms."""

    def __init__(self, tracker_host: str, tracker_port: int):
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port

    def register_peer(self, peer_id: str, ip: str, port: int, file_hashes: List[str], is_seeder: bool = False) -> bool:
        try:
            with socket.create_connection((self.tracker_host, self.tracker_port), timeout=3.0) as sock:
                send_msg(sock, {
                    "type": MSG_REGISTER,
                    "peer_id": peer_id,
                    "ip": ip,
                    "port": port,
                    "file_hashes": file_hashes,
                    "is_seeder": is_seeder
                })
                resp, _ = recv_msg(sock)
                return resp.get("status") == "REGISTERED"
        except Exception:
            return False

    def get_peers(self, file_hash: str, exclude_peer: str = "") -> List[Dict[str, Any]]:
        try:
            with socket.create_connection((self.tracker_host, self.tracker_port), timeout=3.0) as sock:
                send_msg(sock, {
                    "type": MSG_DISCOVER,
                    "file_hash": file_hash,
                    "exclude_peer": exclude_peer
                })
                resp, _ = recv_msg(sock)
                return resp.get("peers", [])
        except Exception:
            return []

    def unregister_peer(self, peer_id: str) -> bool:
        try:
            with socket.create_connection((self.tracker_host, self.tracker_port), timeout=2.0) as sock:
                send_msg(sock, {"type": MSG_UNREGISTER, "peer_id": peer_id})
                return True
        except Exception:
            return False
