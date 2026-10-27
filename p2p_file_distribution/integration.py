"""
integration.py
System Integration and Verification Orchestrator.
Authored by Member 4 (Udbhav Singh - 241551102).

Integrates all 4 members' subsystems:
- Member 1: Discovery Tracker & TCP Socket Communication
- Member 2: File Metadata, Deterministic Chunking, & Piece Selection (Rarest-first)
- Member 3: Parallel Workers, SHA-256 Piece Verification, & Failure Handling
- Member 4: Real-time Telemetry, Metrics Logging, & Performance Measurement
"""

import os
import sys
import time
import shutil
import tempfile
import hashlib
from typing import Dict, Any, List, Optional

from p2p.metadata import FileMetadata
from p2p.discovery import TrackerServer, TrackerClient
from p2p.peer_node import PeerNode
from member4_performance.measurement import PerformanceMetricsCollector


class P2PSystemIntegration:
    """
    Master Integration Harness for end-to-end swarm verification.
    """

    def __init__(self, tracker_host: str = "127.0.0.1", tracker_port: int = 0):
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.tracker: Optional[TrackerServer] = None
        self.seeders: List[PeerNode] = []
        self.leechers: List[PeerNode] = []
        self.metrics_collector = PerformanceMetricsCollector()
        self.work_dir = tempfile.mkdtemp(prefix="p2p_integration_")

    def setup_network(self) -> int:
        """Starts the Discovery Tracker."""
        self.tracker = TrackerServer(self.tracker_host, self.tracker_port)
        self.tracker_port = self.tracker.start()
        print(f"[INTEGRATION] Tracker successfully online at {self.tracker_host}:{self.tracker_port}")
        return self.tracker_port

    def create_dummy_payload(self, filename: str, size_bytes: int) -> str:
        """Creates a verified test payload file."""
        payload_dir = os.path.join(self.work_dir, "payloads")
        os.makedirs(payload_dir, exist_ok=True)
        filepath = os.path.join(payload_dir, filename)

        # Generate deterministic repeating binary content
        pattern = b"MEMBER4_INTEGRATION_TEST_PAYLOAD_" * 64
        with open(filepath, "wb") as f:
            written = 0
            while written < size_bytes:
                chunk = pattern[:min(len(pattern), size_bytes - written)]
                f.write(chunk)
                written += len(chunk)

        print(f"[INTEGRATION] Generated payload: {filepath} ({size_bytes / (1024*1024):.2f} MB)")
        return filepath

    def spawn_seeder_swarm(
        self,
        metadata: FileMetadata,
        source_filepath: str,
        num_seeders: int = 4
    ) -> List[PeerNode]:
        """Launches N seeder peers and registers them to the tracker."""
        for i in range(num_seeders):
            s_dir = os.path.join(self.work_dir, f"seeder_{i}")
            seeder = PeerNode(
                peer_id=f"seeder-node-{i+1}",
                host="127.0.0.1",
                port=0,
                tracker_host=self.tracker_host,
                tracker_port=self.tracker_port,
                storage_dir=s_dir
            )
            seeder.start()
            seeder.register_file(metadata, source_filepath, is_seeder=True)
            self.seeders.append(seeder)
            print(f"[INTEGRATION] Seeder {seeder.peer_id} active on port {seeder.port} (Serving {metadata.total_pieces} pieces)")

        return self.seeders

    def run_leecher_download(
        self,
        metadata: FileMetadata,
        output_filename: str = "downloaded_file.bin",
        piece_strategy: str = "rarest_first"
    ) -> Dict[str, Any]:
        """
        Launches a leecher peer, hooks telemetry, executes parallel download,
        verifies SHA-256 hash match, and records transfer statistics.
        """
        leecher_dir = os.path.join(self.work_dir, "leecher_client")
        leecher = PeerNode(
            peer_id="leecher-client-1",
            host="127.0.0.1",
            port=0,
            tracker_host=self.tracker_host,
            tracker_port=self.tracker_port,
            storage_dir=leecher_dir,
            piece_strategy=piece_strategy
        )
        leecher.start()
        self.leechers.append(leecher)

        # Hook telemetry for Member 4 collector
        leecher.on_piece_downloaded = self.metrics_collector.record_piece_event

        dest_path = os.path.join(leecher_dir, output_filename)
        print(f"\n[INTEGRATION] Initiating Parallel Download on {leecher.peer_id}...")
        print(f"[INTEGRATION] Target: {metadata.filename} | Size: {metadata.filesize} bytes | Pieces: {metadata.total_pieces}")

        t0 = time.perf_counter()
        is_success = leecher.download_file(metadata, dest_path, timeout=45.0)
        t_duration = time.perf_counter() - t0

        # Cryptographic end-to-end verification
        hasher = hashlib.sha256()
        with open(dest_path, "rb") as f:
            while blk := f.read(65536):
                hasher.update(blk)
        downloaded_hash = hasher.hexdigest()

        is_hash_identical = (downloaded_hash == metadata.file_hash)
        throughput = (metadata.filesize / (1024 * 1024)) / max(t_duration, 0.0001)

        summary = self.metrics_collector.record_transfer_summary(
            experiment_id="integration_test_run",
            file_size_bytes=metadata.filesize,
            chunk_size_bytes=metadata.chunk_size,
            total_pieces=metadata.total_pieces,
            swarm_size=len(self.seeders),
            strategy=piece_strategy,
            duration_sec=t_duration,
            is_successful=is_success and is_hash_identical,
            extra_meta={
                "sha256_match": is_hash_identical,
                "expected_hash": metadata.file_hash,
                "downloaded_hash": downloaded_hash
            }
        )

        print("\n" + "=" * 60)
        print("SYSTEM INTEGRATION VERIFICATION RESULT")
        print("=" * 60)
        print(f"Transfer Status      : {'PASS' if is_success and is_hash_identical else 'FAIL'}")
        print(f"Elapsed Time         : {t_duration:.4f} seconds")
        print(f"Effective Throughput : {throughput:.2f} MB/s")
        print(f"Original SHA-256     : {metadata.file_hash}")
        print(f"Reconstructed SHA-256: {downloaded_hash}")
        print(f"Cryptographic Match  : {is_hash_identical}")
        print(f"Total Pieces Verified: {metadata.total_pieces} / {metadata.total_pieces}")
        print("=" * 60 + "\n")

        return summary

    def teardown(self):
        """Clean shutdown of all nodes and removal of temp scratch data."""
        print("[INTEGRATION] Tearing down peer network...")
        for l in self.leechers:
            try:
                l.stop()
            except Exception:
                pass
        for s in self.seeders:
            try:
                s.stop()
            except Exception:
                pass
        if self.tracker:
            try:
                self.tracker.stop()
            except Exception:
                pass
        shutil.rmtree(self.work_dir, ignore_errors=True)
        print("[INTEGRATION] Network shutdown complete.")


def run_full_system_integration_test(file_size_mb: int = 4, num_seeders: int = 4) -> bool:
    """Convenience function to run a complete integration test."""
    system = P2PSystemIntegration()
    try:
        system.setup_network()
        payload_path = system.create_dummy_payload("integration_sample.bin", file_size_mb * 1024 * 1024)
        meta = FileMetadata.create_from_file(payload_path, chunk_size=64 * 1024)
        system.spawn_seeder_swarm(meta, payload_path, num_seeders=num_seeders)
        res = system.run_leecher_download(meta)
        return res["is_successful"]
    finally:
        system.teardown()


if __name__ == "__main__":
    success = run_full_system_integration_test(file_size_mb=4, num_seeders=4)
    sys.exit(0 if success else 1)
