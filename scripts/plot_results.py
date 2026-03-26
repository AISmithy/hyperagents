"""
plot_results.py
===============
Reads results/raw_metrics.csv and produces publication-ready learning curves.

Output:
    results/learning_curves.png   — main figure (train + test, 2 panels)
    results/meta_policy_drift.png — meta policy parameter drift over iterations

Usage (from repo root):
    python scripts/plot_results.py
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
except ImportError:
    raise SystemExit("matplotlib is required: pip install matplotlib")

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT    = Path(__file__).resolve().parents[1]
CSV_IN  = ROOT / "results" / "raw_metrics.csv"
OUT_DIR = ROOT / "results"

# ── Colour palette ────────────────────────────────────────────────────────────

PALETTE = {
    "hyperagent": ("#b8582f", "HyperAgent (full system)"),
    "baseline":   ("#1a7d79", "Baseline (frozen meta)"),
    "no_archive": ("#7a6a5a", "No Archive (greedy)"),
}
CONDITIONS = list(PALETTE.keys())

# ── Data helpers ──────────────────────────────────────────────────────────────

def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def group_by(rows: list[dict], *keys: str) -> dict:
    groups: dict = defaultdict(list)
    for row in rows:
        k = tuple(row[k] for k in keys)
        groups[k].append(row)
    return groups


def mean_std(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    m = sum(values) / n
    s = (sum((v - m) ** 2 for v in values) / n) ** 0.5
    return m, s


def build_curves(
    rows: list[dict],
    metric: str,
) -> dict[str, tuple[list[int], list[float], list[float]]]:
    """Return {condition: (iterations, means, stds)}."""
    # Group: condition -> iteration -> list[float]
    data: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        data[row["condition"]][int(row["iteration"])].append(float(row[metric]))

    curves = {}
    for cond, iter_map in data.items():
        iters = sorted(iter_map.keys())
        means, stds = [], []
        for it in iters:
            m, s = mean_std(iter_map[it])
            means.append(m)
            stds.append(s)
        curves[cond] = (iters, means, stds)
    return curves


# ── Plot 1: Learning curves ───────────────────────────────────────────────────

def plot_learning_curves(rows: list[dict]) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=False)
    fig.suptitle("HyperAgents Ablation: Learning Curves", fontsize=13, fontweight="bold", y=1.01)

    metrics = [
        ("best_fitness",       "Best Train Fitness",   axes[0]),
        ("best_test_accuracy", "Best Test Accuracy",   axes[1]),
    ]

    for metric, ylabel, ax in metrics:
        curves = build_curves(rows, metric)
        for cond in CONDITIONS:
            if cond not in curves:
                continue
            color, label = PALETTE[cond]
            iters, means, stds = curves[cond]
            means_arr = means
            stds_arr  = stds
            ax.plot(iters, means_arr, color=color, linewidth=2.2, label=label, zorder=3)
            ax.fill_between(
                iters,
                [m - s for m, s in zip(means_arr, stds_arr)],
                [m + s for m, s in zip(means_arr, stds_arr)],
                color=color, alpha=0.15, zorder=2,
            )

        ax.set_xlabel("Iteration", fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_ylim(0.4, 1.05)
        ax.set_xlim(left=0)
        ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.5)
        ax.spines[["top", "right"]].set_visible(False)

    # Shared legend below
    handles = [
        mpatches.Patch(color=PALETTE[c][0], label=PALETTE[c][1])
        for c in CONDITIONS if c in build_curves(rows, "best_fitness")
    ]
    fig.legend(handles=handles, loc="lower center", ncol=len(CONDITIONS),
               bbox_to_anchor=(0.5, -0.08), fontsize=10, frameon=False)

    fig.tight_layout()
    out = OUT_DIR / "learning_curves.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out


# ── Plot 2: Meta-policy drift ─────────────────────────────────────────────────

def plot_meta_drift(rows: list[dict]) -> Path:
    params = [
        ("meta_weight_step",      "Weight Step"),
        ("meta_threshold_step",   "Threshold Step"),
        ("meta_exploration_scale","Exploration Scale"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=False)
    fig.suptitle(
        "Meta-Policy Parameter Drift\n(HyperAgent vs Baseline — mean across seeds)",
        fontsize=12, fontweight="bold", y=1.02,
    )

    # Only compare hyperagent vs baseline (no_archive uses same meta logic as hyperagent)
    show_conds = ["hyperagent", "baseline"]

    for (param, title), ax in zip(params, axes):
        curves = build_curves(rows, param)
        for cond in show_conds:
            if cond not in curves:
                continue
            color, label = PALETTE[cond]
            iters, means, stds = curves[cond]
            ax.plot(iters, means, color=color, linewidth=2, label=label, zorder=3)
            ax.fill_between(
                iters,
                [m - s for m, s in zip(means, stds)],
                [m + s for m, s in zip(means, stds)],
                color=color, alpha=0.15,
            )
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("Iteration", fontsize=9)
        ax.set_xlim(left=0)
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.45)
        ax.spines[["top", "right"]].set_visible(False)

    handles = [
        mpatches.Patch(color=PALETTE[c][0], label=PALETTE[c][1])
        for c in show_conds
    ]
    fig.legend(handles=handles, loc="lower center", ncol=2,
               bbox_to_anchor=(0.5, -0.1), fontsize=10, frameon=False)
    fig.tight_layout()
    out = OUT_DIR / "meta_policy_drift.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not CSV_IN.exists():
        raise SystemExit(f"CSV not found: {CSV_IN}\nRun scripts/run_experiment.py first.")

    rows = load_csv(CSV_IN)
    print(f"Loaded {len(rows)} rows from {CSV_IN}")

    p1 = plot_learning_curves(rows)
    print(f"Saved -> {p1}")

    p2 = plot_meta_drift(rows)
    print(f"Saved -> {p2}")
