#!/usr/bin/env python3
"""
Analyze exploration quality — break down EXPLORE, SHELL, and JAR_INSPECT
by actual tool calls and targets per variant.

Shows the "good explore vs bad explore" distinction:
  - EXPLORE (Read/Glob): targeted file access — good
  - SHELL (find/ls/grep): blind searching — wasteful
  - JAR_INSPECT (jar tf/javap): decompiling binaries — worst

Run:
    python scripts/analyze_explore_quality.py
"""

from pathlib import Path
import pandas as pd
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_markov_analysis import classify_state, STATES, VARIANT_ORDER

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "curated"


def main():
    tu = pd.read_parquet(DATA_DIR / "tool_uses.parquet")
    tu["state"] = tu.apply(
        lambda r: classify_state(r["tool_name"], r.get("tool_target", "")), axis=1
    )
    tu = tu.dropna(subset=["state"])

    print("=" * 70)
    print("Exploration Quality Analysis")
    print("=" * 70)

    for variant in VARIANT_ORDER:
        v = tu[tu["variant"] == variant]
        if len(v) == 0:
            continue

        total = len(v)
        explore = v[v["state"] == "EXPLORE"]
        shell = v[v["state"] == "SHELL"]
        jar = v[v["state"] == "JAR_INSPECT"]

        print(f"\n{'─' * 70}")
        print(f"  {variant} ({total} classified calls)")
        print(f"{'─' * 70}")
        print(f"  EXPLORE (targeted):  {len(explore):3d} ({len(explore)/total*100:.1f}%)")
        print(f"  SHELL (searching):   {len(shell):3d} ({len(shell)/total*100:.1f}%)")
        print(f"  JAR_INSPECT (worst): {len(jar):3d} ({len(jar)/total*100:.1f}%)")
        print(f"  SEARCH total:        {len(shell)+len(jar):3d} ({(len(shell)+len(jar))/total*100:.1f}%)")

        # EXPLORE tool breakdown
        if len(explore) > 0:
            print(f"\n  EXPLORE by tool:")
            for tool, count in explore["tool_name"].value_counts().items():
                print(f"    {tool:15s}: {count:3d} ({count/len(explore)*100:.1f}%)")

        # SHELL sample targets
        if len(shell) > 0:
            print(f"\n  SHELL sample commands ({len(shell)} total):")
            for _, row in shell.head(5).iterrows():
                target = str(row.get("tool_target", ""))[:85]
                print(f"    {target}")

        # JAR_INSPECT sample targets
        if len(jar) > 0:
            print(f"\n  JAR_INSPECT sample commands ({len(jar)} total):")
            for _, row in jar.head(5).iterrows():
                target = str(row.get("tool_target", ""))[:85]
                print(f"    {target}")

    # Summary comparison table
    print(f"\n{'=' * 70}")
    print("Summary: Exploration Quality by Variant")
    print(f"{'=' * 70}")
    print(f"{'Variant':45s} {'Read':>5s} {'Shell':>6s} {'JAR':>5s} {'Search%':>8s}")
    print(f"{'─' * 70}")
    for variant in VARIANT_ORDER:
        v = tu[tu["variant"] == variant]
        if len(v) == 0:
            continue
        total = len(v)
        reads = len(v[(v["state"] == "EXPLORE") & (v["tool_name"] == "Read")])
        shell = len(v[v["state"] == "SHELL"])
        jar = len(v[v["state"] == "JAR_INSPECT"])
        search_pct = (shell + jar) / total * 100
        print(f"  {variant:43s} {reads:5d} {shell:6d} {jar:5d} {search_pct:7.1f}%")


if __name__ == "__main__":
    main()
