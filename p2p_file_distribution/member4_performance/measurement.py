"""
member4_performance/measurement.py
Performance Measurement and Telemetry Engine.
Authored by Member 4 (Udbhav Singh - 241551102).

Collects high-resolution metrics:
- Transfer durations, throughput (MB/s), RTT
- Piece transfer distribution across swarm peers
- Verification overhead & CPU cost
- Protocol overhead and framing efficiency
- Speedup and concurrency scaling
"""

import time
import json
import threading
from typing import Dict, List, Any, Optional
import pandas as pd


class PerformanceMetricsCollector:
    """
    Centralized thread-safe collector for benchmarking P2P file transfers.
    Captures end-to-end transfer stats and granular per-piece transfer events.
    """

    def __init__(self):
        self.lock = threading.Lock()
        # Transfer-level summary records
        self.transfer_records: List[Dict[str, Any]] = []
        # Chunk-level granular records
        self.piece_events: List[Dict[str, Any]] = []

    def record_piece_event(self, event_data: Dict[str, Any]) -> None:
        """Records a single piece transfer event."""
        with self.lock:
            self.piece_events.append(dict(event_data))

    def record_transfer_summary(
        self,
        experiment_id: str,
        file_size_bytes: int,
        chunk_size_bytes: int,
        total_pieces: int,
        swarm_size: int,
        strategy: str,
        duration_sec: float,
        is_successful: bool,
        failure_rate_simulated: float = 0.0,
        extra_meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Computes and records comprehensive performance metrics for a completed transfer.
        """
        throughput_mb_s = (file_size_bytes / (1024 * 1024)) / max(duration_sec, 0.00001) if is_successful else 0.0
        
        record = {
            "experiment_id": experiment_id,
            "timestamp": time.time(),
            "file_size_bytes": file_size_bytes,
            "file_size_mb": round(file_size_bytes / (1024 * 1024), 2),
            "chunk_size_bytes": chunk_size_bytes,
            "chunk_size_kb": round(chunk_size_bytes / 1024, 2),
            "total_pieces": total_pieces,
            "swarm_size": swarm_size,
            "strategy": strategy,
            "duration_sec": round(duration_sec, 4),
            "throughput_mb_s": round(throughput_mb_s, 3),
            "is_successful": is_successful,
            "failure_rate_simulated": failure_rate_simulated
        }

        if extra_meta:
            record.update(extra_meta)

        with self.lock:
            self.transfer_records.append(record)

        return record

    def get_summary_dataframe(self) -> pd.DataFrame:
        with self.lock:
            return pd.DataFrame(self.transfer_records)

    def get_piece_events_dataframe(self) -> pd.DataFrame:
        with self.lock:
            return pd.DataFrame(self.piece_events)

    def export_csv(self, summary_path: str, piece_path: Optional[str] = None) -> None:
        """Exports metrics to CSV for analysis and archival."""
        df_summary = self.get_summary_dataframe()
        df_summary.to_csv(summary_path, index=False)

        if piece_path:
            df_pieces = self.get_piece_events_dataframe()
            df_pieces.to_csv(piece_path, index=False)

    def export_json(self, json_path: str) -> None:
        """Exports metrics as JSON."""
        with self.lock:
            data = {
                "transfers": self.transfer_records,
                "pieces": self.piece_events
            }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def clear(self) -> None:
        with self.lock:
            self.transfer_records.clear()
            self.piece_events.clear()
