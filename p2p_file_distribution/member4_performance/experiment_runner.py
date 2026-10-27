"""
member4_performance/experiment_runner.py
Automated Experiment Harness for Testing the P2P Scaling Claim.
Authored by Member 4 (Udbhav Singh - 241551102).

Systematically tests the hypothesis:
"Increasing the number of available peers can reduce file-distribution time because
different pieces can be downloaded concurrently, although excessive peer connections
may introduce communication overhead."
"""

import os
import time
import shutil
import tempfile
import threading
from typing import List, Dict, Any, Optional
import pandas as pd

from p2p.metadata import FileMetadata
from p2p.discovery import TrackerServer
from p2p.peer_node import PeerNode
from member4_performance.measurement import PerformanceMetricsCollector


class ExperimentRunner:
    """
    Automates test runs across varying peer counts, file sizes, chunk sizes,
    and churn rates. Orchestrates swarms, collects metrics, and cleans up artifacts.
    """

    def __init__(self, output_dir: str = "./results"):
        self.output_dir = output_dir
        self.figures_dir = os.path.join(output_dir, "figures")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.figures_dir, exist_ok=True)
        self.collector = PerformanceMetricsCollector()

    def generate_dummy_file(self, filepath: str, size_bytes: int) -> str:
        """Generates a binary file of exact size containing pseudo-random patterns."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        # 64KB pattern block for speed
        block_size = 64 * 1024
        pattern = b"P2P_NETWORKING_ASSIGNMENT_1_CSE14_MEMBER_4_" * 1524  # ~64KB
        pattern = pattern[:block_size]

        with open(filepath, "wb") as f:
            written = 0
            while written < size_bytes:
                to_write = min(block_size, size_bytes - written)
                f.write(pattern[:to_write])
                written += to_write
        return filepath

    def run_single_transfer(
        self,
        file_size_bytes: int,
        num_seeders: int,
        chunk_size_bytes: int = 64 * 1024,
        piece_strategy: str = "rarest_first",
        kill_peers_midway: int = 0
    ) -> Dict[str, Any]:
        """
        Sets up an isolated tracker and swarm, seeds a file across num_seeders,
        launches 1 leecher, completes the download, verifies hashes, records telemetry.
        """
        temp_dir = tempfile.mkdtemp(prefix="p2p_exp_")
        tracker = None
        seeders: List[PeerNode] = []
        leecher = None

        try:
            # 1. Start Tracker
            tracker = TrackerServer(host="127.0.0.1", port=0)
            tracker_port = tracker.start()

            # 2. Generate Source File and Metadata
            source_file = os.path.join(temp_dir, "source", "test_file.bin")
            self.generate_dummy_file(source_file, file_size_bytes)
            meta = FileMetadata.create_from_file(source_file, chunk_size=chunk_size_bytes)

            # 3. Spin up Seeder Peer Nodes
            for i in range(num_seeders):
                seeder_storage = os.path.join(temp_dir, f"seeder_{i}")
                seeder = PeerNode(
                    peer_id=f"seeder-{i}",
                    host="127.0.0.1",
                    port=0,
                    tracker_host="127.0.0.1",
                    tracker_port=tracker_port,
                    storage_dir=seeder_storage
                )
                seeder.start()
                # Link source file to seeder
                seeder.register_file(meta, source_file, is_seeder=True)
                seeders.append(seeder)

            # Wait briefly for registration
            time.sleep(0.05)

            # 4. Spin up Leecher Peer Node
            leecher_storage = os.path.join(temp_dir, "leecher")
            leecher = PeerNode(
                peer_id="leecher-main",
                host="127.0.0.1",
                port=0,
                tracker_host="127.0.0.1",
                tracker_port=tracker_port,
                storage_dir=leecher_storage,
                piece_strategy=piece_strategy
            )
            leecher.start()

            # Hook telemetry events to Member 4 collector
            leecher.on_piece_downloaded = self.collector.record_piece_event

            dest_file = os.path.join(leecher_storage, "downloaded.bin")

            # Fault injection thread if kill_peers_midway > 0
            if kill_peers_midway > 0 and len(seeders) > kill_peers_midway:
                def killer_worker():
                    time.sleep(0.08)
                    for k in range(kill_peers_midway):
                        try:
                            seeders[k].stop()
                        except Exception:
                            pass
                threading.Thread(target=killer_worker, daemon=True).start()

            # 5. Execute Download
            t0 = time.perf_counter()
            success = leecher.download_file(meta, dest_file, timeout=60.0)
            duration = time.perf_counter() - t0

            # 6. Record Summary Record
            exp_id = f"exp_sz{file_size_bytes}_p{num_seeders}_c{chunk_size_bytes}_fail{kill_peers_midway}"
            record = self.collector.record_transfer_summary(
                experiment_id=exp_id,
                file_size_bytes=file_size_bytes,
                chunk_size_bytes=chunk_size_bytes,
                total_pieces=meta.total_pieces,
                swarm_size=num_seeders,
                strategy=piece_strategy,
                duration_sec=duration,
                is_successful=success,
                failure_rate_simulated=kill_peers_midway / max(num_seeders, 1),
                extra_meta={"killed_peers": kill_peers_midway}
            )

            return record

        finally:
            # Clean shutdown of all sockets and temporary files
            if leecher:
                try:
                    leecher.stop()
                except Exception:
                    pass
            for s in seeders:
                try:
                    s.stop()
                except Exception:
                    pass
            if tracker:
                try:
                    tracker.stop()
                except Exception:
                    pass
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    def run_core_claim_experiment_matrix(
        self,
        peer_counts: Optional[List[int]] = None,
        file_sizes_mb: Optional[List[int]] = None,
        iterations_per_point: int = 3
    ) -> pd.DataFrame:
        """
        Executes the primary experiment matrix defined in Section 3 of proposal:
        Varying peer counts (independent var 1) and file sizes (independent var 2),
        measuring download time and throughput with repeated trials.
        """
        if peer_counts is None:
            peer_counts = [1, 2, 4, 8, 12, 16]
        if file_sizes_mb is None:
            file_sizes_mb = [1, 5, 10, 20]

        print("=" * 70)
        print("MEMBER 4: EXECUTING P2P PERFORMANCE EXPERIMENT MATRIX")
        print(f"Peer Counts: {peer_counts}")
        print(f"File Sizes (MB): {file_sizes_mb}")
        print(f"Iterations per configuration: {iterations_per_point}")
        print("=" * 70)

        total_runs = len(peer_counts) * len(file_sizes_mb) * iterations_per_point
        current_run = 0

        for sz_mb in file_sizes_mb:
            sz_bytes = sz_mb * 1024 * 1024
            for p_count in peer_counts:
                for rep in range(iterations_per_point):
                    current_run += 1
                    print(f"[{current_run}/{total_runs}] Testing Size: {sz_mb} MB | Peers: {p_count} | Iteration: {rep+1}...", end="", flush=True)
                    res = self.run_single_transfer(
                        file_size_bytes=sz_bytes,
                        num_seeders=p_count,
                        chunk_size_bytes=64 * 1024
                    )
                    status_str = "SUCCESS" if res["is_successful"] else "FAILED"
                    print(f" -> {status_str} in {res['duration_sec']}s ({res['throughput_mb_s']} MB/s)")

        # Export current data
        self.collector.export_csv(
            os.path.join(self.output_dir, "raw_metrics.csv"),
            os.path.join(self.output_dir, "piece_transfer_logs.csv")
        )
        self.collector.export_json(os.path.join(self.output_dir, "raw_metrics.json"))
        return self.collector.get_summary_dataframe()

    def run_chunk_size_experiment(self, file_size_mb: int = 5, peer_count: int = 4) -> pd.DataFrame:
        """
        Controlled variable experiment: Tests impact of chunk sizes on socket overhead.
        Chunk sizes tested: 16KB, 32KB, 64KB, 128KB, 256KB, 512KB.
        """
        chunk_sizes_kb = [16, 32, 64, 128, 256, 512]
        sz_bytes = file_size_mb * 1024 * 1024
        print("\n" + "=" * 70)
        print("MEMBER 4: EXECUTING CHUNK SIZE TRADEOFF EXPERIMENT")
        print(f"File Size: {file_size_mb} MB | Swarm: {peer_count} peers")
        print("=" * 70)

        for c_kb in chunk_sizes_kb:
            c_bytes = c_kb * 1024
            print(f"Testing Chunk Size: {c_kb} KB...", end="", flush=True)
            res = self.run_single_transfer(
                file_size_bytes=sz_bytes,
                num_seeders=peer_count,
                chunk_size_bytes=c_bytes
            )
            print(f" -> {res['duration_sec']}s ({res['throughput_mb_s']} MB/s)")

        return self.collector.get_summary_dataframe()

    def run_failure_resilience_experiment(self, file_size_mb: int = 10, total_peers: int = 8) -> pd.DataFrame:
        """
        Tests Risk 2 from Proposal: Peer disconnections mid-transfer and failover recovery.
        """
        print("\n" + "=" * 70)
        print("MEMBER 4: EXECUTING FAULT TOLERANCE & RECOVERY EXPERIMENT")
        print("=" * 70)
        sz_bytes = file_size_mb * 1024 * 1024
        scenarios = [
            ("Baseline (0 Failures)", 0),
            ("1 Peer Crashed", 1),
            ("2 Peers Crashed", 2),
            ("3 Peers Crashed", 3)
        ]

        for label, killed in scenarios:
            print(f"Running scenario: {label}...", end="", flush=True)
            res = self.run_single_transfer(
                file_size_bytes=sz_bytes,
                num_seeders=total_peers,
                kill_peers_midway=killed
            )
            print(f" -> Completed: {res['is_successful']} in {res['duration_sec']}s")

        return self.collector.get_summary_dataframe()
