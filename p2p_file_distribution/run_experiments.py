"""
run_experiments.py
Master Benchmark and Experiment Execution Script.
Authored by Member 4 (Udbhav Singh - 241551102).

Executes the full experimental matrix testing the proposal's hypothesis:
- Peer count variation: [1, 2, 4, 8, 12, 16]
- File size variation: [1, 5, 10, 20] MB
- Chunk size tradeoffs: [16, 32, 64, 128, 256, 512] KB
- Fault tolerance & mid-transfer peer failure recovery

Outputs:
- CSV & JSON raw logs
- Statistical comparison tables (Markdown & CSV)
- 6 High-resolution publication-quality PNG figures
"""

import os
import sys
import time

# Set environment
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

os.environ["MPLCONFIGDIR"] = os.path.join(base_dir, ".matplotlib_cache")

from member4_performance.experiment_runner import ExperimentRunner
from member4_performance.analysis import ExperimentAnalyzer
from member4_performance.visualizer import BenchmarkVisualizer


def main():
    print("=" * 80)
    print("  CS-30003 PEER-TO-PEER FILE DISTRIBUTION SYSTEM")
    print("  MEMBER 4 BENCHMARK SUITE: PERFORMANCE, VISUALIZATION & ANALYSIS")
    print("  Author: Udbhav Singh (241551102) | Section: CSE-14")
    print("=" * 80)

    results_dir = os.path.join(base_dir, "results")
    figures_dir = os.path.join(results_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)

    runner = ExperimentRunner(output_dir=results_dir)

    # 1. Run Core Scaling Matrix (Proposal Section 3)
    print("\n>>> STEP 1: Running Core Claim Scaling Matrix (Peers & File Sizes)...")
    # Using 1, 2, 4, 8, 12, 16 peers and 1, 5, 10, 20 MB files, 2 iterations each for stable statistics
    peer_matrix = [1, 2, 4, 8, 12, 16]
    size_matrix = [1, 5, 10, 20]
    df_raw = runner.run_core_claim_experiment_matrix(
        peer_counts=peer_matrix,
        file_sizes_mb=size_matrix,
        iterations_per_point=2
    )

    # 2. Run Chunk Size Tradeoff Experiment
    print("\n>>> STEP 2: Running Chunk Size Tradeoff Experiment (16KB - 512KB)...")
    df_chunks = runner.run_chunk_size_experiment(file_size_mb=5, peer_count=4)

    # 3. Run Fault Tolerance / Churn Experiment
    print("\n>>> STEP 3: Running Fault Tolerance & Peer Crash Experiment...")
    df_faults = runner.run_failure_resilience_experiment(file_size_mb=5, total_peers=6)

    # 4. Statistical Analysis
    print("\n>>> STEP 4: Performing Statistical Aggregation & Analysis...")
    analyzer = ExperimentAnalyzer(
        raw_metrics_df=runner.collector.get_summary_dataframe(),
        piece_events_df=runner.collector.get_piece_events_dataframe()
    )

    summary_df = analyzer.compute_summary_table()
    piece_dist_df = analyzer.analyze_piece_distribution()
    verdict = analyzer.evaluate_claim_hypothesis()

    # Save summary tables to Markdown
    tables_md = analyzer.generate_markdown_report_tables()
    summary_path = os.path.join(results_dir, "summary_tables.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Experimental Benchmark Results & Comparison Tables\n\n")
        f.write(tables_md)
        f.write("\n### Formal Hypothesis Evaluation\n")
        f.write(f"- **Max Speedup Observed**: {verdict.get('max_speedup_observed', 'N/A')}x\n")
        f.write(f"- **Conclusion**: {verdict.get('conclusion', '')}\n")

    print(f"Summary table saved to: {summary_path}")
    print("\n" + tables_md)

    # 5. Visualizations
    print(">>> STEP 5: Rendering High-Resolution Visualizations via Matplotlib...")
    viz = BenchmarkVisualizer(output_dir=figures_dir)

    # Figure 1: Download Time vs Peers
    f1 = viz.plot_download_time_vs_peers(summary_df)
    print(f"  [Figure 1 Generated] {f1}")

    # Figure 2: Throughput vs Peers
    f2 = viz.plot_throughput_vs_peers(summary_df)
    print(f"  [Figure 2 Generated] {f2}")

    # Figure 3: Speedup Factor S(N) vs Amdahl & Linear
    f3 = viz.plot_speedup_analysis(summary_df)
    print(f"  [Figure 3 Generated] {f3}")

    # Figure 4: Piece Transfer Distribution
    f4 = viz.plot_piece_distribution(runner.collector.get_piece_events_dataframe())
    print(f"  [Figure 4 Generated] {f4}")

    # Figure 5: Chunk Size Tradeoff
    sub_chunk_df = runner.collector.get_summary_dataframe()
    sub_chunk_df = sub_chunk_df[sub_chunk_df["swarm_size"] == 4].drop_duplicates(subset=["chunk_size_kb"])
    f5 = viz.plot_chunk_size_tradeoff(sub_chunk_df)
    print(f"  [Figure 5 Generated] {f5}")

    # Figure 6: Fault Resilience
    fault_records = runner.collector.get_summary_dataframe()
    fault_records = fault_records[fault_records["failure_rate_simulated"] > 0.0]
    # Include one baseline 0-failure record
    baseline_rec = runner.collector.get_summary_dataframe()[
        (runner.collector.get_summary_dataframe()["swarm_size"] == 6) &
        (runner.collector.get_summary_dataframe()["failure_rate_simulated"] == 0.0)
    ]
    if not baseline_rec.empty:
        import pandas as pd
        fault_records = pd.concat([baseline_rec.iloc[[0]], fault_records])
    if not fault_records.empty:
        f6 = viz.plot_fault_resilience(fault_records)
        print(f"  [Figure 6 Generated] {f6}")

    print("\n" + "=" * 80)
    print("MEMBER 4 BENCHMARK & EXPERIMENT EXECUTION COMPLETED SUCCESSFULLY!")
    print(f"All figures saved to: {figures_dir}")
    print(f"All raw and summarized metrics saved to: {results_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
