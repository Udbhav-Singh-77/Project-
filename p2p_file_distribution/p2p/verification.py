"""
p2p/verification.py
Cryptographic verification of downloaded file chunks using SHA-256.
Part of the P2P File Distribution System (Member 3 deliverable).
"""

import hashlib
import time
from typing import Tuple


class PieceVerifier:
    """Verifies chunk integrity against pre-computed manifest hashes."""

    @staticmethod
    def verify_piece(piece_data: bytes, expected_hash: str) -> Tuple[bool, float, str]:
        """
        Verifies that sha256(piece_data) == expected_hash.
        Returns: (is_valid, verification_time_sec, calculated_hash)
        """
        t0 = time.perf_counter()
        actual_hash = hashlib.sha256(piece_data).hexdigest()
        dt = time.perf_counter() - t0
        is_valid = (actual_hash == expected_hash)
        return is_valid, dt, actual_hash

    @staticmethod
    def verify_file(filepath: str, expected_hash: str) -> Tuple[bool, float, str]:
        """Verifies overall file hash upon complete assembly."""
        t0 = time.perf_counter()
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()
        dt = time.perf_counter() - t0
        return (actual_hash == expected_hash), dt, actual_hash
