"""
tests/test_integration.py
Comprehensive Unit and Integration Test Suite.
Verifies all modules and Member 4's integration architecture.
"""

import os
import sys
import unittest
import tempfile
import shutil
import hashlib

# Ensure package in path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from p2p.metadata import FileMetadata
from p2p.chunking import FileChunkStorage
from p2p.piece_selector import PieceSelector
from p2p.verification import PieceVerifier
from p2p.failure_handler import FailureHandler
from member4_performance.measurement import PerformanceMetricsCollector
from integration import P2PSystemIntegration


class TestP2PComponents(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_p2p_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_file_metadata_and_chunking(self):
        """Tests Member 2's metadata creation and chunking integrity."""
        sample_path = os.path.join(self.test_dir, "sample.bin")
        data = b"0123456789ABCDEF" * 1024  # 16 KB
        with open(sample_path, "wb") as f:
            f.write(data)

        meta = FileMetadata.create_from_file(sample_path, chunk_size=4096)
        self.assertEqual(meta.filesize, 16384)
        self.assertEqual(meta.total_pieces, 4)
        self.assertEqual(len(meta.piece_hashes), 4)
        self.assertEqual(meta.file_hash, hashlib.sha256(data).hexdigest())

    def test_piece_verification(self):
        """Tests Member 3's cryptographic chunk verification."""
        data = b"hello_p2p_world"
        valid_hash = hashlib.sha256(data).hexdigest()
        corrupt_hash = hashlib.sha256(b"corrupted_bytes").hexdigest()

        is_valid, _, _ = PieceVerifier.verify_piece(data, valid_hash)
        self.assertTrue(is_valid)

        is_invalid, _, _ = PieceVerifier.verify_piece(data, corrupt_hash)
        self.assertFalse(is_invalid)

    def test_rarest_first_selection(self):
        """Tests Member 2's rarest-first piece selection algorithm."""
        selector = PieceSelector(total_pieces=5, strategy="rarest_first")
        needed = {0, 1, 2, 3, 4}
        in_flight = set()

        # Swarm availability:
        # Piece 0: available on peer1, peer2, peer3 (freq = 3)
        # Piece 1: available on peer1, peer2 (freq = 2)
        # Piece 2: available on peer3 only (freq = 1) -> RAREST
        bitfields = {
            "peer1": [1, 1, 0, 1, 1],
            "peer2": [1, 1, 0, 1, 1],
            "peer3": [1, 0, 1, 1, 1]
        }

        selected = selector.select_next_piece(needed, bitfields, in_flight)
        self.assertEqual(selected, 2, "PieceSelector should have selected rarest piece index 2")

    def test_failure_handling(self):
        """Tests Member 3's failure handling, retries, and blacklisting."""
        fh = FailureHandler(max_retries_per_piece=3, peer_fail_threshold=2)
        self.assertTrue(fh.is_peer_usable("peer_A"))

        # 1 failure
        fh.record_peer_failure("peer_A", piece_index=0)
        self.assertTrue(fh.is_peer_usable("peer_A"))
        self.assertEqual(fh.get_piece_retry_count(0), 1)

        # 2nd failure triggers threshold
        is_blacklisted = fh.record_peer_failure("peer_A", piece_index=0)
        self.assertTrue(is_blacklisted)
        self.assertFalse(fh.is_peer_usable("peer_A"))

    def test_member4_metrics_collector(self):
        """Tests Member 4's PerformanceMetricsCollector calculations."""
        collector = PerformanceMetricsCollector()
        rec = collector.record_transfer_summary(
            experiment_id="test_exp_1",
            file_size_bytes=10 * 1024 * 1024,
            chunk_size_bytes=64 * 1024,
            total_pieces=160,
            swarm_size=4,
            strategy="rarest_first",
            duration_sec=2.0,
            is_successful=True
        )
        self.assertEqual(rec["file_size_mb"], 10.0)
        self.assertEqual(rec["duration_sec"], 2.0)
        self.assertEqual(rec["throughput_mb_s"], 5.0)

        df = collector.get_summary_dataframe()
        self.assertEqual(len(df), 1)
        self.assertEqual(df["throughput_mb_s"].iloc[0], 5.0)


class TestFullP2PIntegration(unittest.TestCase):

    def test_end_to_end_transfer(self):
        """Full system integration test with 2 seeders and 1 leecher."""
        system = P2PSystemIntegration()
        try:
            system.setup_network()
            payload = system.create_dummy_payload("unit_test_payload.bin", 1024 * 1024)  # 1MB
            meta = FileMetadata.create_from_file(payload, chunk_size=32 * 1024)
            system.spawn_seeder_swarm(meta, payload, num_seeders=2)
            res = system.run_leecher_download(meta)
            self.assertTrue(res["is_successful"])
            self.assertTrue(res.get("sha256_match", False))
        finally:
            system.teardown()


if __name__ == "__main__":
    unittest.main()
