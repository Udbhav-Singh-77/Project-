"""
p2p/failure_handler.py
Fault tolerance, peer churn management, retry queues, and timeout handling.
Part of the P2P File Distribution System (Member 3 deliverable).
"""

import time
import threading
from typing import Dict, Set, Optional, Tuple


class FailureHandler:
    """
    Manages peer health, timeouts, retry backoff, and piece reassignments
    when peers disconnect or fail mid-transfer.
    """

    def __init__(self, max_retries_per_piece: int = 5, peer_fail_threshold: int = 3):
        self.max_retries = max_retries_per_piece
        self.peer_fail_threshold = peer_fail_threshold
        self.lock = threading.Lock()

        # Piece retry tracking: {piece_index: retry_count}
        self.piece_retries: Dict[int, int] = {}
        # Peer error tracking: {peer_id: error_count}
        self.peer_errors: Dict[str, int] = {}
        # Blacklisted peers: {peer_id: blacklisted_until_time}
        self.blacklisted_peers: Dict[str, float] = {}

    def record_peer_failure(self, peer_id: str, piece_index: Optional[int] = None) -> bool:
        """
        Records an error on a peer connection.
        Returns True if peer is now blacklisted, False otherwise.
        """
        with self.lock:
            self.peer_errors[peer_id] = self.peer_errors.get(peer_id, 0) + 1
            if piece_index is not None:
                self.piece_retries[piece_index] = self.piece_retries.get(piece_index, 0) + 1

            if self.peer_errors[peer_id] >= self.peer_fail_threshold:
                # Blacklist peer for 30 seconds
                self.blacklisted_peers[peer_id] = time.time() + 30.0
                return True
            return False

    def is_peer_usable(self, peer_id: str) -> bool:
        with self.lock:
            if peer_id in self.blacklisted_peers:
                if time.time() < self.blacklisted_peers[peer_id]:
                    return False
                else:
                    # Cooldown expired
                    del self.blacklisted_peers[peer_id]
                    self.peer_errors[peer_id] = 0
            return True

    def record_peer_success(self, peer_id: str) -> None:
        with self.lock:
            if peer_id in self.peer_errors:
                self.peer_errors[peer_id] = max(0, self.peer_errors[peer_id] - 1)

    def can_retry_piece(self, piece_index: int) -> bool:
        with self.lock:
            return self.piece_retries.get(piece_index, 0) < self.max_retries

    def get_piece_retry_count(self, piece_index: int) -> int:
        with self.lock:
            return self.piece_retries.get(piece_index, 0)
