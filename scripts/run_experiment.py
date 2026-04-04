"""
run_experiment.py
=================
Runs the three ablation conditions (hyperagent, baseline, no_archive) across
multiple random seeds and writes all per-iteration metrics to:

    results/raw_metrics.csv

Usage (from repo root):
    python scripts/run_experiment.py [--iterations N] [--seeds M]

Defaults: 30 iterations, 5 seeds per condition.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

# Make the backend importable without a venv activation step
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.engine import CONDITION_LABELS, HyperAgentEngine  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────

CONDITIONS = list(CONDITION_LABELS.keys())  # ["hyperagent", "baseline", "no_archive"]

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "results" / "raw_metrics.csv"

# ── Runner ────────────────────────────────────────────────────────────────────

def run_experiment(iterations: int = 30, n_seeds: int = 5) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    total = len(CONDITIONS) * n_seeds
    completed = 0

    print(f"\nRunning {total} experiments "
          f"({len(CONDITIONS)} conditions × {n_seeds} seeds × {iterations} iterations)\n")

    for condition in CONDITIONS:
        for seed_idx in range(n_seeds):
            seed = seed_idx * 13 + 7  # deterministic, spread across space
            t0 = time.perf_counter()

            engine = HyperAgentEngine(seed=seed)
            engine.reset(mode=condition)
            engine.run(iterations)

            elapsed = time.perf_counter() - t0
            completed += 1

            for record in engine.metrics_json():
                rows.append({
                    "condition": condition,
                    "label": CONDITION_LABELS[condition],
                    "seed": seed,
                    "seed_idx": seed_idx,
                    **record,
                })

            best = engine.best_entry
            print(
                f"  [{completed:2d}/{total}] {condition:<12} seed={seed}"
                f"  best_train={best.evaluation.train_accuracy:.3f}"
                f"  best_test={best.evaluation.test_accuracy:.3f}"
                f"  ({elapsed:.2f}s)"
            )

    # Write CSV
    if rows:
        columns = list(rows[0].keys())
        with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows -> {OUTPUT_PATH}\n")
    _print_summary(rows, iterations)


def _print_summary(rows: list[dict], iterations: int) -> None:
    """Print mean final scores per condition."""
    from collections import defaultdict

    final: dict[str, list[float]] = defaultdict(list)
    final_test: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        if row["iteration"] == iterations:
            final[row["condition"]].append(row["best_fitness"])
            final_test[row["condition"]].append(row["best_test_accuracy"])

    print("-- Final scores (mean +/- std across seeds) --")
    print(f"{'Condition':<14}  {'Train':>12}  {'Test':>12}")
    print("-" * 42)
    for cond in CONDITIONS:
        trains = final[cond]
        tests  = final_test[cond]
        if not trains:
            continue
        mean_tr = sum(trains) / len(trains)
        std_tr  = (sum((x - mean_tr) ** 2 for x in trains) / len(trains)) ** 0.5
        mean_te = sum(tests)  / len(tests)
        std_te  = (sum((x - mean_te) ** 2 for x in tests)  / len(tests))  ** 0.5
        print(f"{cond:<14}  {mean_tr:.3f}±{std_tr:.3f}  {mean_te:.3f}±{std_te:.3f}")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run HyperAgents ablation experiment.")
    parser.add_argument("--iterations", type=int, default=30,
                        help="Iterations per run (default: 30)")
    parser.add_argument("--seeds", type=int, default=5,
                        help="Seeds per condition (default: 5)")
    args = parser.parse_args()
    run_experiment(iterations=args.iterations, n_seeds=args.seeds)
