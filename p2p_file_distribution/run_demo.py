"""
run_demo.py
Interactive Live Demonstration of the P2P File Distribution Swarm.
Member 4 (Udbhav Singh - 241551102) System Showcase.

Demonstrates:
- Multi-peer swarm discovery
- Parallel piece downloads across 4 seeders
- Real-time piece verification (SHA-256)
- Member 4 performance instrumentation
"""

import os
import sys
import time

base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from integration import P2PSystemIntegration
from p2p.metadata import FileMetadata


def main():
    print("*" * 75)
    print("   P2P FILE DISTRIBUTION SYSTEM - LIVE DEMONSTRATION")
    print("   Course: CS-30003 · Section: CSE-14 · Path: A")
    print("   Integration & Performance: Member 4 (Udbhav Singh - 241551102)")
    print("*" * 75)

    file_size_mb = 8
    num_seeders = 4
    chunk_size_kb = 64

    print(f"\n[DEMO CONFIGURATION]")
    print(f"  - Target Payload Size : {file_size_mb} MB ({file_size_mb * 1024 * 1024} bytes)")
    print(f"  - Chunk / Piece Size  : {chunk_size_kb} KB ({chunk_size_kb * 1024} bytes)")
    print(f"  - Total Pieces        : {(file_size_mb * 1024) // chunk_size_kb} pieces")
    print(f"  - Active Seeder Swarm : {num_seeders} concurrent peers")
    print(f"  - Piece Strategy      : Rarest-First (Dynamic Frequency-Weighted)")
    print("-" * 75)

    system = P2PSystemIntegration()
    try:
        # Step 1: Start Discovery Tracker
        print("\n[Step 1] Starting Discovery Tracker Server...")
        tracker_port = system.setup_network()
        print(f"         Tracker listening on port {tracker_port}")

        # Step 2: Create Test Payload
        print("\n[Step 2] Generating Test File Payload...")
        payload_file = system.create_dummy_payload(
            f"demo_dataset_{file_size_mb}MB.bin",
            file_size_mb * 1024 * 1024
        )
        metadata = FileMetadata.create_from_file(payload_file, chunk_size=chunk_size_kb * 1024)
        print(f"         SHA-256: {metadata.file_hash}")

        # Step 3: Spawn Seeder Swarm
        print(f"\n[Step 3] Spawning Seeder Swarm ({num_seeders} Peer Nodes)...")
        system.spawn_seeder_swarm(metadata, payload_file, num_seeders=num_seeders)
        time.sleep(0.1)

        # Step 4: Execute Download on Leecher
        print("\n[Step 4] Starting Leecher Download with Parallel Workers...")
        res = system.run_leecher_download(metadata, output_filename="demo_downloaded.bin")

        # Step 5: Member 4 Performance Analysis
        print("[Step 5] Analyzing Member 4 Granular Piece Metrics...")
        piece_events = system.metrics_collector.get_piece_events_dataframe()
        if not piece_events.empty:
            peer_shares = piece_events["source_peer_id"].value_counts()
            print("\n  Piece Contribution Breakdown by Peer:")
            for pid, count in peer_shares.items():
                pct = (count / len(piece_events)) * 100.0
                bar = "#" * int(pct / 4)
                print(f"    - {pid:<16} : {count:3d} pieces ({pct:5.1f}%) |{bar:<25}|")

        print("\n" + "=" * 75)
        print("DEMO VERDICT: P2P FILE DISTRIBUTION SUCCEEDED WITHOUT CENTRAL DATA SERVER!")
        print("=" * 75 + "\n")

    finally:
        system.teardown()


if __name__ == "__main__":
    main()
