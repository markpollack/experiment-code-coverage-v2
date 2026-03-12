#!/usr/bin/env python3
"""
Variant comparison figures — template stubs.

CUSTOMIZE: replace stubs with your domain-specific figures.
The core patterns (load parquet, colorblind palette, save PDF+PNG) are ready to use.

Run:
    python scripts/make_figures.py
"""

from pathlib import Path
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "curated"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "figures"

# ---------------------------------------------------------------------------
# Style defaults (publication-quality, colorblind-safe palette)
# ---------------------------------------------------------------------------

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})

# Paul Tol's colorblind-safe palette
PALETTE = [
    "#0077BB", "#EE7733", "#009988", "#CC3311",
    "#117733", "#DDAA33", "#AA3377", "#999999",
]

# CUSTOMIZE: per-variant colors (optional — cycles through PALETTE otherwise)
# COLORS = {"control": "#999999", "variant-a": "#0077BB", ...}

# CUSTOMIZE: display order for variants in charts
VARIANT_ORDER: list[str] = []


def save_fig(fig: plt.Figure, name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_DIR / f"{name}.pdf")
    fig.savefig(OUTPUT_DIR / f"{name}.png", dpi=200)
    plt.close(fig)
    print(f"  Saved {name}.pdf + .png")


def ordered_variants(variants: list[str]) -> list[str]:
    if not VARIANT_ORDER:
        return sorted(variants)
    order = {v: i for i, v in enumerate(VARIANT_ORDER)}
    return sorted(variants, key=lambda v: order.get(v, 999))


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    con = duckdb.connect()
    items = con.execute(f"SELECT * FROM '{DATA_DIR}/item_results.parquet'").df()
    runs = con.execute(f"SELECT * FROM '{DATA_DIR}/runs.parquet'").df()
    con.close()
    return items, runs


# ---------------------------------------------------------------------------
# Figure 1: Pass rate by variant (always useful)
# ---------------------------------------------------------------------------

def make_pass_rate_chart(items: pd.DataFrame) -> None:
    variants = ordered_variants(items["variant"].unique().tolist())
    pass_rates = []
    for v in variants:
        vdf = items[items["variant"] == v]
        pass_rates.append(vdf["passed"].mean() if len(vdf) > 0 else 0.0)

    colors = [PALETTE[i % len(PALETTE)] for i in range(len(variants))]
    fig, ax = plt.subplots(figsize=(max(6, len(variants) * 1.2), 4))
    bars = ax.bar(range(len(variants)), pass_rates, color=colors)
    ax.set_xticks(range(len(variants)))
    ax.set_xticklabels(variants, rotation=30, ha="right")
    ax.set_ylim(0, 1.1)
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_ylabel("Pass rate")
    ax.set_title("Pass Rate by Variant")
    for bar, rate in zip(bars, pass_rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{rate:.0%}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    save_fig(fig, "pass-rate-by-variant")


# ---------------------------------------------------------------------------
# Figure 2: Cost vs quality scatter (always useful)
# ---------------------------------------------------------------------------

def make_cost_quality_scatter(items: pd.DataFrame) -> None:
    variants = ordered_variants(items["variant"].unique().tolist())
    fig, ax = plt.subplots(figsize=(7, 5))
    for i, variant in enumerate(variants):
        vdf = items[items["variant"] == variant]
        x = vdf["cost_usd"].mean()
        y = vdf["passed"].mean()
        ax.scatter(x, y, color=PALETTE[i % len(PALETTE)], s=80, label=variant, zorder=3)
        ax.annotate(variant, (x, y), textcoords="offset points", xytext=(5, 3), fontsize=8)
    ax.set_xlabel("Mean cost per item (USD)")
    ax.set_ylabel("Pass rate")
    ax.set_title("Cost vs Quality by Variant")
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    save_fig(fig, "cost-quality-scatter")


# ---------------------------------------------------------------------------
# Figure 3: Per-item breakdown (CUSTOMIZE for your domain)
# ---------------------------------------------------------------------------

def make_per_item_breakdown(items: pd.DataFrame) -> None:
    """CUSTOMIZE: replace with domain-specific per-item bar chart.

    Default: shows pass/fail per item per variant as a grouped bar.
    """
    item_ids = sorted(items["item_id"].unique())
    variants = ordered_variants(items["variant"].unique().tolist())
    n_variants = len(variants)
    n_items = len(item_ids)
    if n_items == 0 or n_variants == 0:
        return

    x = np.arange(n_items)
    width = 0.8 / n_variants

    fig, ax = plt.subplots(figsize=(max(8, n_items * 1.5), 4))
    for i, variant in enumerate(variants):
        vdf = items[items["variant"] == variant]
        vals = []
        for item_id in item_ids:
            idf = vdf[vdf["item_id"] == item_id]
            vals.append(float(idf["passed"].iloc[0]) if len(idf) > 0 else 0.0)
        offset = (i - n_variants / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=variant,
               color=PALETTE[i % len(PALETTE)], alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(item_ids, rotation=30, ha="right", fontsize=8)
    ax.set_ylim(0, 1.3)
    ax.set_ylabel("Passed (1=yes, 0=no)")
    ax.set_title("Per-Item Results by Variant")
    ax.legend(fontsize=8, ncol=min(4, n_variants))
    fig.tight_layout()
    save_fig(fig, "per-item-breakdown")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import time
    t0 = time.time()
    print("Variant Comparison Figures")
    print("=" * 40)
    print("\nLoading data...")
    items, runs = load_data()
    print(f"  item_results: {len(items)} rows")
    print(f"  runs: {len(runs)} rows")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("\nGenerating figures:")
    make_pass_rate_chart(items)
    make_cost_quality_scatter(items)
    make_per_item_breakdown(items)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s — figures in {OUTPUT_DIR}")
