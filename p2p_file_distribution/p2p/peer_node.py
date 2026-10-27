"""
p2p/peer_node.py
Autonomous Peer Node implementation featuring TCP server, multi-peer parallel downloader,
seeding engine, and telemetry hooks for Member 4 performance instrumentation.
"""

import os
import socket
import select
import threading
import time
from typing import Dict, List, Set, Optional, Callable, Any

from p2p.protocol import (
    send_msg, recv_msg,
    MSG_HANDSHAKE, MSG_HANDSHAKE_ACK, MSG_BITFIELD, MSG_HAVE,
    MSG_REQUEST_PIECE, MSG_PIECE_DATA, MSG_PIECE_NOT_FOUND, MSG_GOODBYE
)
from p2p.metadata import FileMetadata
from p2p.chunking import FileChunkStorage
from p2p.piece_selector import PieceSelector
from p2p.verification import PieceVerifier
from p2p.failure_handler import FailureHandler
from p2p.discovery import TrackerClient


class PeerNode:
    """
    Complete Peer entity capable of seeding, downloading, uploading concurrently,
    and reporting real-time event telemetry.
    """

    def __init__(
        self,
        peer_id: str,
        host: str = "127.0.0.1",
        port: int = 0,
        tracker_host: str = "127.0.0.1",
        tracker_port: int = 8000,
        storage_dir: str = "./storage",
        max_workers: int = 8,
        piece_strategy: str = "rarest_first"
    ):
        self.peer_id = peer_id
        self.host = host
        self.port = port
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.storage_dir = storage_dir
        self.max_workers = max_workers
        self.piece_strategy = piece_strategy

        os.makedirs(self.storage_dir, exist_ok=True)

        self.server_sock: Optional[socket.socket] = None
        self.running = False
        self.server_thread: Optional[threading.Thread] = None

        # Registered files: {file_hash: {"metadata": FileMetadata, "storage": FileChunkStorage}}
        self.files: Dict[str, Dict[str, Any]] = {}
        self.files_lock = threading.Lock()

        self.tracker = TrackerClient(tracker_host, tracker_port)
        self.failure_handler = FailureHandler()

        # Telemetry callbacks for Member 4
        self.on_piece_downloaded: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_piece_uploaded: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_transfer_complete: Optional[Callable[[Dict[str, Any]], None]] = None

    def start(self) -> int:
        """Starts the peer's TCP server and binds to a port."""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.port = self.server_sock.getsockname()[1]
        self.server_sock.listen(128)
        self.running = True

        self.server_thread = threading.Thread(target=self._server_loop, daemon=True, name=f"PeerServer-{self.peer_id}")
        self.server_thread.start()
        return self.port

    def stop(self) -> None:
        """Gracefully disconnects and shuts down server."""
        self.running = False
        try:
            self.tracker.unregister_peer(self.peer_id)
        except Exception:
            pass

        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1.0)

    def register_file(self, metadata: FileMetadata, filepath: str, is_seeder: bool = False) -> None:
        """Registers a file locally and updates the tracker."""
        storage = FileChunkStorage(filepath, metadata, is_complete=is_seeder)
        with self.files_lock:
            self.files[metadata.file_hash] = {
                "metadata": metadata,
                "storage": storage,
                "is_seeder": is_seeder
            }
        self.tracker.register_peer(
            self.peer_id,
            self.host,
            self.port,
            list(self.files.keys()),
            is_seeder=is_seeder
        )

    # ------------------ SERVER / UPLOADER LOGIC ------------------ #

    def _server_loop(self) -> None:
        while self.running:
            try:
                client_sock, addr = self.server_sock.accept()
                threading.Thread(
                    target=self._handle_incoming_connection,
                    args=(client_sock, addr),
                    daemon=True,
                    name=f"PeerWorker-{self.peer_id}-{addr}"
                ).start()
            except Exception:
                break

    def _handle_incoming_connection(self, client_sock: socket.socket, addr: tuple) -> None:
        client_sock.settimeout(10.0)
        try:
            while self.running:
                try:
                    header, _ = recv_msg(client_sock)
                except (ConnectionResetError, EOFError, socket.timeout):
                    break

                msg_type = header.get("type")

                if msg_type == MSG_HANDSHAKE:
                    file_hash = header.get("file_hash")
                    with self.files_lock:
                        file_entry = self.files.get(file_hash)

                    if file_entry:
                        bitfield = file_entry["storage"].get_bitfield()
                        send_msg(client_sock, {
                            "type": MSG_HANDSHAKE_ACK,
                            "peer_id": self.peer_id,
                            "bitfield": bitfield
                        })
                    else:
                        send_msg(client_sock, {
                            "type": MSG_HANDSHAKE_ACK,
                            "peer_id": self.peer_id,
                            "bitfield": []
                        })

                elif msg_type == MSG_REQUEST_PIECE:
                    t_req = time.perf_counter()
                    file_hash = header.get("file_hash")
                    piece_idx = header.get("piece_index")

                    with self.files_lock:
                        file_entry = self.files.get(file_hash)

                    if file_entry and file_entry["storage"].has_piece(piece_idx):
                        chunk_bytes = file_entry["storage"].read_piece(piece_idx)
                        if chunk_bytes:
                            meta = file_entry["metadata"]
                            send_msg(client_sock, {
                                "type": MSG_PIECE_DATA,
                                "piece_index": piece_idx,
                                "file_hash": file_hash,
                                "sha256": meta.piece_hashes[piece_idx]
                            }, payload=chunk_bytes)

                            duration = time.perf_counter() - t_req
                            if self.on_piece_uploaded:
                                self.on_piece_uploaded({
                                    "seeder_id": self.peer_id,
                                    "piece_index": piece_idx,
                                    "bytes": len(chunk_bytes),
                                    "duration": duration,
                                    "timestamp": time.time()
                                })
                        else:
                            send_msg(client_sock, {"type": MSG_PIECE_NOT_FOUND, "piece_index": piece_idx})
                    else:
                        send_msg(client_sock, {"type": MSG_PIECE_NOT_FOUND, "piece_index": piece_idx})

                elif msg_type == MSG_GOODBYE:
                    break
        except Exception:
            pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    # ------------------ CLIENT / DOWNLOADER LOGIC ------------------ #

    def download_file(
        self,
        metadata: FileMetadata,
        destination_path: str,
        timeout: float = 60.0
    ) -> bool:
        """
        Parallel downloading engine:
        Discovers peers from tracker, connects concurrently, uses PieceSelector (rarest-first),
        verifies each chunk via SHA-256, writes to disk, and tracks telemetry.
        """
        start_time = time.perf_counter()
        storage = FileChunkStorage(destination_path, metadata, is_complete=False)

        with self.files_lock:
            self.files[metadata.file_hash] = {
                "metadata": metadata,
                "storage": storage,
                "is_seeder": False
            }

        # Query tracker for peers
        peer_list = self.tracker.get_peers(metadata.file_hash, exclude_peer=self.peer_id)
        if not peer_list:
            return False

        # State tracking
        needed_pieces: Set[int] = set(range(metadata.total_pieces))
        in_flight_pieces: Set[int] = set()
        peer_bitfields: Dict[str, List[int]] = {}
        active_sockets: Dict[str, socket.socket] = {}
        state_lock = threading.Lock()
        download_finished = threading.Event()
        piece_selector = PieceSelector(metadata.total_pieces, strategy=self.piece_strategy)

        # Connect and perform Handshake with available peers
        for p in peer_list:
            pid = p["peer_id"]
            if not self.failure_handler.is_peer_usable(pid):
                continue
            try:
                s = socket.create_connection((p["ip"], p["port"]), timeout=3.0)
                send_msg(s, {
                    "type": MSG_HANDSHAKE,
                    "peer_id": self.peer_id,
                    "file_hash": metadata.file_hash
                })
                resp, _ = recv_msg(s)
                if resp.get("type") == MSG_HANDSHAKE_ACK:
                    active_sockets[pid] = s
                    peer_bitfields[pid] = resp.get("bitfield", [])
            except Exception:
                self.failure_handler.record_peer_failure(pid)

        if not active_sockets:
            return False

        # Worker thread definition
        def peer_worker(peer_id: str, sock: socket.socket):
            while not download_finished.is_set() and self.running:
                target_piece = None
                with state_lock:
                    if not needed_pieces:
                        download_finished.set()
                        break

                    # Select candidate piece available on this peer
                    available_on_this_peer = peer_bitfields.get(peer_id, [])
                    candidates = [
                        p for p in (needed_pieces - in_flight_pieces)
                        if p < len(available_on_this_peer) and available_on_this_peer[p] == 1
                    ]

                    if not candidates:
                        # No pieces available on this peer right now
                        time.sleep(0.01)
                        continue

                    # Use PieceSelector on sub-swarm
                    target_piece = piece_selector.select_next_piece(
                        set(candidates),
                        peer_bitfields,
                        in_flight_pieces
                    )

                    if target_piece is None:
                        time.sleep(0.01)
                        continue

                    in_flight_pieces.add(target_piece)

                # Request and receive chunk
                t_req = time.perf_counter()
                success = False
                try:
                    send_msg(sock, {
                        "type": MSG_REQUEST_PIECE,
                        "file_hash": metadata.file_hash,
                        "piece_index": target_piece
                    })

                    sock.settimeout(5.0)
                    resp, chunk_data = recv_msg(sock)
                    rtt = time.perf_counter() - t_req

                    if resp.get("type") == MSG_PIECE_DATA and resp.get("piece_index") == target_piece:
                        expected_hash = metadata.piece_hashes[target_piece]
                        is_valid, v_time, _ = PieceVerifier.verify_piece(chunk_data, expected_hash)

                        if is_valid:
                            write_ok = storage.write_piece(target_piece, chunk_data)
                            if write_ok:
                                with state_lock:
                                    needed_pieces.discard(target_piece)
                                    in_flight_pieces.discard(target_piece)
                                success = True
                                self.failure_handler.record_peer_success(peer_id)

                                if self.on_piece_downloaded:
                                    self.on_piece_downloaded({
                                        "peer_id": self.peer_id,
                                        "source_peer_id": peer_id,
                                        "piece_index": target_piece,
                                        "bytes": len(chunk_data),
                                        "duration": rtt,
                                        "verification_time": v_time,
                                        "timestamp": time.time(),
                                        "status": "SUCCESS"
                                    })
                        else:
                            # Integrity verification failed
                            if self.on_piece_downloaded:
                                self.on_piece_downloaded({
                                    "peer_id": self.peer_id,
                                    "source_peer_id": peer_id,
                                    "piece_index": target_piece,
                                    "bytes": len(chunk_data),
                                    "duration": rtt,
                                    "verification_time": v_time,
                                    "timestamp": time.time(),
                                    "status": "HASH_CORRUPT"
                                })
                except Exception:
                    self.failure_handler.record_peer_failure(peer_id, target_piece)

                if not success:
                    with state_lock:
                        in_flight_pieces.discard(target_piece)
                    # Small backoff before retrying
                    time.sleep(0.02)

        # Launch worker threads for each connected peer
        threads = []
        for pid, sock in active_sockets.items():
            t = threading.Thread(
                target=peer_worker,
                args=(pid, sock),
                daemon=True,
                name=f"DownloaderWorker-{self.peer_id}->{pid}"
            )
            threads.append(t)
            t.start()

        # Monitor loop
        t_deadline = time.time() + timeout
        while time.time() < t_deadline:
            with state_lock:
                if len(needed_pieces) == 0:
                    download_finished.set()
                    break
            time.sleep(0.05)

        download_finished.set()
        for t in threads:
            t.join(timeout=0.5)

        # Close all client sockets gracefully
        for pid, s in active_sockets.items():
            try:
                send_msg(s, {"type": MSG_GOODBYE})
                s.close()
            except Exception:
                pass

        total_download_time = time.perf_counter() - start_time
        is_complete = storage.is_complete()

        # Overall file verification
        verified_final = False
        if is_complete:
            verified_final, _, _ = PieceVerifier.verify_file(destination_path, metadata.file_hash)

        if self.on_transfer_complete:
            self.on_transfer_complete({
                "peer_id": self.peer_id,
                "file_hash": metadata.file_hash,
                "filesize": metadata.filesize,
                "total_pieces": metadata.total_pieces,
                "is_complete": is_complete and verified_final,
                "duration": total_download_time,
                "throughput_mb_s": (metadata.filesize / (1024 * 1024)) / max(total_download_time, 0.0001) if is_complete else 0.0
            })

        return is_complete and verified_final
