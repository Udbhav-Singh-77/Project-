"""
p2p/metadata.py
Manages file metadata, cryptographic piece hashes (SHA-256), and manifest serialization.
Part of the P2P File Distribution System (Member 2 deliverable).
"""

import os
import json
import hashlib
from typing import List, Dict, Any, Optional

DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KB default chunk size


class FileMetadata:
    def __init__(
        self,
        filename: str,
        filesize: int,
        chunk_size: int,
        total_pieces: int,
        file_hash: str,
        piece_hashes: List[str]
    ):
        self.filename = filename
        self.filesize = filesize
        self.chunk_size = chunk_size
        self.total_pieces = total_pieces
        self.file_hash = file_hash
        self.piece_hashes = piece_hashes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "filesize": self.filesize,
            "chunk_size": self.chunk_size,
            "total_pieces": self.total_pieces,
            "file_hash": self.file_hash,
            "piece_hashes": self.piece_hashes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileMetadata":
        return cls(
            filename=data["filename"],
            filesize=data["filesize"],
            chunk_size=data["chunk_size"],
            total_pieces=data["total_pieces"],
            file_hash=data["file_hash"],
            piece_hashes=data["piece_hashes"]
        )

    @classmethod
    def create_from_file(cls, filepath: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> "FileMetadata":
        """Calculates piece hashes and whole-file hash from a local file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        filesize = os.path.getsize(filepath)
        filename = os.path.basename(filepath)
        piece_hashes = []
        overall_hasher = hashlib.sha256()

        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                piece_hash = hashlib.sha256(chunk).hexdigest()
                piece_hashes.append(piece_hash)
                overall_hasher.update(chunk)

        total_pieces = len(piece_hashes)
        return cls(
            filename=filename,
            filesize=filesize,
            chunk_size=chunk_size,
            total_pieces=total_pieces,
            file_hash=overall_hasher.hexdigest(),
            piece_hashes=piece_hashes
        )

    def save_manifest(self, manifest_path: str) -> None:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_manifest(cls, manifest_path: str) -> "FileMetadata":
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
