"""
p2p/chunking.py
Manages file splitting, piece reading/writing, and in-memory or on-disk chunk storage.
Part of the P2P File Distribution System (Member 2 deliverable).
"""

import os
import threading
from typing import List, Optional
from p2p.metadata import FileMetadata


class FileChunkStorage:
    """Thread-safe piece storage for reading and writing file chunks."""

    def __init__(self, filepath: str, metadata: FileMetadata, is_complete: bool = False):
        self.filepath = filepath
        self.metadata = metadata
        self.lock = threading.Lock()
        self.total_pieces = metadata.total_pieces
        self.piece_size = metadata.chunk_size

        # Bitfield indicating availability of each piece: 1 = available, 0 = missing
        self.bitfield = [1 if is_complete else 0] * self.total_pieces

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        if not is_complete:
            # Pre-allocate file with zero bytes if not already present
            if not os.path.exists(self.filepath) or os.path.getsize(self.filepath) != self.metadata.filesize:
                with open(self.filepath, "wb") as f:
                    f.truncate(self.metadata.filesize)

    def is_complete(self) -> bool:
        with self.lock:
            return all(p == 1 for p in self.bitfield)

    def get_progress(self) -> float:
        with self.lock:
            if self.total_pieces == 0:
                return 1.0
            return sum(self.bitfield) / self.total_pieces

    def has_piece(self, piece_index: int) -> bool:
        with self.lock:
            if 0 <= piece_index < self.total_pieces:
                return self.bitfield[piece_index] == 1
            return False

    def get_bitfield(self) -> List[int]:
        with self.lock:
            return list(self.bitfield)

    def read_piece(self, piece_index: int) -> Optional[bytes]:
        with self.lock:
            if not (0 <= piece_index < self.total_pieces and self.bitfield[piece_index] == 1):
                return None

            offset = piece_index * self.piece_size
            length = min(self.piece_size, self.metadata.filesize - offset)

            with open(self.filepath, "rb") as f:
                f.seek(offset)
                return f.read(length)

    def write_piece(self, piece_index: int, data: bytes) -> bool:
        """Writes a piece to disk and updates the bitfield."""
        offset = piece_index * self.piece_size
        expected_len = min(self.piece_size, self.metadata.filesize - offset)

        if len(data) != expected_len:
            return False

        with self.lock:
            with open(self.filepath, "r+b") as f:
                f.seek(offset)
                f.write(data)
                f.flush()
            self.bitfield[piece_index] = 1
            return True
