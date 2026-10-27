"""
member4_performance/visualizer.py
High-Resolution Visualization Suite using Matplotlib.
Authored by Member 4 (Udbhav Singh - 241551102).

Generates 6 publication-ready figures illustrating:
1. Download Time vs. Number of Peers (across file sizes)
2. Effective Throughput vs. Swarm Size
3. Concurrency Speedup Curve vs. Ideal Linear & Amdahl's Model
4. Piece Transfer Distribution across Swarm Peers
5. Chunk Size Tradeoff Analysis (Latency vs Overhead)
6. Fault Resilience & Peer Churn Impact
"""

import os
# Configure Matplotlib writable cache before importing pyplot
os.environ["MPLCONFIGDIR"] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".matplotlib_cache")
)

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless / server environments
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import Optional


class BenchmarkVisualizer:
    """Generates styled, high-DPI charts for reports and presentations."""

    def __init__(self, output_dir: str = "./results/figures"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self._setup_style()

    def _setup_style(self):
        plt.rcParams.update({
            "font.size": 11,
            "axes.labelsize": 12,
            "axes.titlesize": 13,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "figure.titlesize": 14,
            "grid.alpha": 0.35,
            "lines.linewidth": 2.2,
            "lines.markersize": 7
        })

    def plot_download_time_vs_peers(self, df_summary: pd.DataFrame, save_filename: str = "download_time_vs_peers.png") -> str:
        """
        Figure 1: Download Time (seconds) vs. Number of Available Peers.
        Demonstrates the core claim: concurrency dramatically reduces download time.
        """
        fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=300)
        colors = ["#2b5c8f", "#d95f02", "#7570b3", "#1b9e77"]
        markers = ["o", "s", "^", "D"]

        file_sizes = sorted(df_summary["file_size_mb"].unique())
        for idx, sz in enumerate(file_sizes):
            sub = df_summary[df_summary["file_size_mb"] == sz].sort_values("swarm_size")
            color = colors[idx % len(colors)]
            marker = markers[idx % len(markers)]

            if "std_duration" in sub.columns:
                ax.errorbar(
                    sub["swarm_size"],
                    sub["mean_duration"],
                    yerr=sub["std_duration"],
                    fmt=f"-{marker}",
                    color=color,
                    label=f"File Size: {sz} MB",
                    capsize=4,
                    capthick=1.2,
                    elinewidth=1.2
                )
            else:
                ax.plot(
                    sub["swarm_size"],
                    sub["mean_duration"],
                    f"-{marker}",
                    color=color,
                    label=f"File Size: {sz} MB"
                )

        ax.set_title("Download Time vs. Number of Available Peers", fontweight="bold", pad=12)
        ax.set_xlabel("Number of Available Peers (Swarm Size)")
        ax.set_ylabel("Download Time (seconds)")
        ax.set_xticks(sorted(df_summary["swarm_size"].unique()))
        ax.grid(True, linestyle="--")
        ax.legend(frameon=True, facecolor="white", edgecolor="none", shadow=True)

        # Highlight diminishing returns
        ax.annotate(
            "Diminishing Returns Region\n(Socket Overhead / TCP contention)",
            xy=(12, df_summary[df_summary["swarm_size"] == 12]["mean_duration"].min()),
            xytext=(9, df_summary["mean_duration"].max() * 0.45),
            arrowprops=dict(facecolor="#c0392b", shrink=0.08, width=1.5, headwidth=7),
            fontsize=9.5,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdf2e9", edgecolor="#e67e22")
        )

        plt.tight_layout()
        save_path = os.path.join(self.output_dir, save_filename)
        fig.savefig(save_path)
        plt.close(fig)
        return save_path

    def plot_throughput_vs_peers(self, df_summary: pd.DataFrame, save_filename: str = "throughput_vs_peers.png") -> str:
        """
        Figure 2: Effective Throughput (MB/s) vs. Swarm Size.
        """
        fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=300)
        colors = ["#2b5c8f", "#d95f02", "#7570b3", "#1b9e77"]
        markers = ["o", "s", "^", "D"]

        file_sizes = sorted(df_summary["file_size_mb"].unique())
        for idx, sz in enumerate(file_sizes):
            sub = df_summary[df_summary["file_size_mb"] == sz].sort_values("swarm_size")
            color = colors[idx % len(colors)]
            marker = markers[idx % len(markers)]

            ax.plot(
                sub["swarm_size"],
                sub["mean_throughput"],
                f"-{marker}",
                color=color,
                label=f"{sz} MB File"
            )

        ax.set_title("Effective Download Throughput vs. Swarm Size", fontweight="bold", pad=12)
        ax.set_xlabel("Number of Available Peers")
        ax.set_ylabel("Throughput (MB/s)")
        ax.set_xticks(sorted(df_summary["swarm_size"].unique()))
        ax.grid(True, linestyle="--")
        ax.legend(frameon=True, loc="upper left")

        plt.tight_layout()
        save_path = os.path.join(self.output_dir, save_filename)
        fig.savefig(save_path)
        plt.close(fig)
        return save_path

    def plot_speedup_analysis(self, df_summary: pd.DataFrame, save_filename: str = "speedup_analysis.png") -> str:
        """
        Figure 3: Speedup Factor S(N) vs. Ideal Linear Speedup and Amdahl's Law.
        """
        fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=300)

        # Use largest file size for purest scaling representation
        max_sz = df_summary["file_size_mb"].max()
        sub = df_summary[df_summary["file_size_mb"] == max_sz].sort_values("swarm_size")
        peers = sub["swarm_size"].values
        speedup = sub["speedup"].values

        # Ideal linear speedup: y = x
        ax.plot(peers, peers, "--", color="#7f8c8d", label="Ideal Linear Speedup (y = x)", linewidth=1.8)

        # Amdahl's Law Model: S(N) = 1 / ((1-P) + P/N) with P = 0.92
        p_factor = 0.92
        amdahl_s = [1.0 / ((1.0 - p_factor) + (p_factor / n)) for n in peers]
        ax.plot(peers, amdahl_s, "-.", color="#e74c3c", label="Amdahl's Law Model (P=0.92)", linewidth=2.0)

        # Measured Speedup
        ax.plot(peers, speedup, "-o", color="#2980b9", label=f"Measured P2P Speedup ({max_sz}MB File)", linewidth=2.5)

        ax.set_title("Concurrency Speedup S(N) vs. Swarm Scalability", fontweight="bold", pad=12)
        ax.set_xlabel("Available Peers (N)")
        ax.set_ylabel("Speedup Factor S(N) = T(1) / T(N)")
        ax.set_xticks(peers)
        ax.grid(True, linestyle="--")
        ax.legend(frameon=True, loc="upper left")

        plt.tight_layout()
        save_path = os.path.join(self.output_dir, save_filename)
        fig.savefig(save_path)
        plt.close(fig)
        return save_path

    def plot_piece_distribution(self, df_pieces: pd.DataFrame, save_filename: str = "piece_distribution.png") -> str:
        """
        Figure 4: Piece Transfer Distribution across available Seeders.
        Illustrates how parallel piece retrieval balances load.
        """
        if df_pieces.empty or "source_peer_id" not in df_pieces.columns:
            return ""

        fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=300)
        counts = df_pieces["source_peer_id"].value_counts().sort_index()

        bars = ax.bar(counts.index, counts.values, color="#3498db", edgecolor="#2980b9", width=0.55)
        ax.set_title("Piece Transfer Distribution Across Swarm Peers", fontweight="bold", pad=12)
        ax.set_xlabel("Peer ID")
        ax.set_ylabel("Number of Pieces Supplied")
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        # Add value labels atop bars
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontweight="semibold"
            )

        plt.tight_layout()
        save_path = os.path.join(self.output_dir, save_filename)
        fig.savefig(save_path)
        plt.close(fig)
        return save_path

    def plot_chunk_size_tradeoff(self, df_chunks: pd.DataFrame, save_filename: str = "chunk_size_tradeoff.png") -> str:
        """
        Figure 5: Download Time & Overhead vs. Chunk Size.
        Finds the optimal chunk size trade-off point.
        """
        fig, ax1 = plt.subplots(figsize=(8.5, 5.0), dpi=300)

        sub = df_chunks.sort_values("chunk_size_kb")
        x = [str(int(c)) + " KB" for c in sub["chunk_size_kb"]]

        color_time = "#2980b9"
        ax1.set_xlabel("Chunk Size (KB)")
        ax1.set_ylabel("Download Time (s)", color=color_time)
        line1 = ax1.plot(x, sub["duration_sec"], "-o", color=color_time, linewidth=2.3, label="Download Time (s)")
        ax1.tick_params(axis="y", labelcolor=color_time)
        ax1.grid(True, linestyle="--")

        ax2 = ax1.twinx()
        color_tp = "#27ae60"
        ax2.set_ylabel("Throughput (MB/s)", color=color_tp)
        line2 = ax2.plot(x, sub["throughput_mb_s"], "-s", color=color_tp, linewidth=2.3, label="Throughput (MB/s)")
        ax2.tick_params(axis="y", labelcolor=color_tp)

        # Combined legend
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax1.legend(lines, labels, loc="center right", frameon=True)

        plt.title("Chunk Size Tradeoff: Socket Overhead vs. Pipeline Efficiency", fontweight="bold", pad=12)
        plt.tight_layout()
        save_path = os.path.join(self.output_dir, save_filename)
        fig.savefig(save_path)
        plt.close(fig)
        return save_path

    def plot_fault_resilience(self, df_faults: pd.DataFrame, save_filename: str = "peer_failure_impact.png") -> str:
        """
        Figure 6: Download Time under Peer Disconnections (Fault Tolerance).
        """
        fig, ax = plt.subplots(figsize=(8.0, 4.8), dpi=300)

        labels = [f"{int(r['extra_meta.killed_peers']) if 'extra_meta.killed_peers' in r else int(r.get('killed_peers', 0))} Peers Failed" for _, r in df_faults.iterrows()]
        times = df_faults["duration_sec"].values

        bars = ax.bar(labels, times, color=["#27ae60", "#f39c12", "#e67e22", "#c0392b"], width=0.5)
        ax.set_title("Fault Tolerance: Impact of Mid-Transfer Peer Disconnection", fontweight="bold", pad=12)
        ax.set_ylabel("Total Download & Recovery Time (seconds)")
        ax.grid(axis="y", linestyle="--", alpha=0.4)

        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.2f}s",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontweight="bold"
            )

        plt.tight_layout()
        save_path = os.path.join(self.output_dir, save_filename)
        fig.savefig(save_path)
        plt.close(fig)
        return save_path
