#!/usr/bin/env python3
"""
Markov chain analysis — template wrapper.

CUSTOMIZE:
  1. Update STATES with your domain's tool-call state taxonomy
  2. Update classify_state() with your domain-specific logic
  3. Update CLUSTER_DEFINITIONS, DELTA_PAIRS, NOTE_MAP, COLORS, VARIANT_ORDER

Bootstrap procedure (do this BEFORE finalizing the taxonomy):
  1. Run one control variant (N=1) to generate tool_uses.parquet
  2. Run with MARKOV_DISCOVERY=true to see raw tool name + target frequencies:
         MARKOV_DISCOVERY=true python scripts/make_markov_analysis.py
     Then inspect: SELECT state, count(*) FROM tool_uses GROUP BY 1 ORDER BY 2 DESC
  3. Cluster the top-N patterns into named states
  4. Write classify_state() based on real data, then re-run normally

Requires markov-agent-analysis library:
    uv pip install -e ~/tuvium/projects/markov-agent-analysis/[all]

Run:
    python scripts/make_markov_analysis.py
    MARKOV_DISCOVERY=true python scripts/make_markov_analysis.py   # discovery mode
"""

import os

from pathlib import Path
import duckdb
import matplotlib
matplotlib.use("Agg")

from markov_agent_analysis import MarkovAnalysisPipeline

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "curated"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "figures"
ANALYSIS_DIR = PROJECT_ROOT / "analysis"

# ---------------------------------------------------------------------------
# Discovery mode — set MARKOV_DISCOVERY=true to emit raw tool:target labels
# instead of semantic states. Use this on first run to calibrate classify_state().
# ---------------------------------------------------------------------------

DISCOVERY_MODE = os.environ.get("MARKOV_DISCOVERY", "false").lower() == "true"
if DISCOVERY_MODE:
    print("DISCOVERY MODE: classify_state() returning raw tool:target labels")
    print("Run: SELECT state, count(*) FROM tool_uses GROUP BY 1 ORDER BY 2 DESC LIMIT 30")
    print()

# ---------------------------------------------------------------------------
# CUSTOMIZE: State taxonomy for your domain
# ---------------------------------------------------------------------------

# Replace with your domain's semantic state names.
# These are the labels your classify_state() function returns.
# Common starting point — adjust after inspecting discovery-mode output.
STATES = [
    "EXPLORE",    # reading/searching source files, directories, discovery
    "READ_KB",    # reading knowledge base files
    "WRITE",      # writing output files (first time)
    "BUILD",      # running build/test/verify commands
    "VERIFY",     # reading back output, checking results
    "FIX",        # editing/rewriting output after an error
]

# CUSTOMIZE: per-state colors (optional — defaults to tab10 palette)
COLORS = {
    # "EXPLORE": "#4C72B0",
    # "READ_KB": "#55A868",
    # "WRITE":   "#C44E52",
    # "BUILD":   "#8172B2",
    # "VERIFY":  "#CCB974",
    # "FIX":     "#DD8452",
}

# CUSTOMIZE: display order for variant names in charts
VARIANT_ORDER = [
    "control",
    "variant-a",
    "variant-b",
    "variant-c",
    "variant-d",
]

# CUSTOMIZE: cluster definitions for cluster% computation
# Maps cluster label → list of state names in that cluster
# High FIX_LOOP % = agent thrashing; high PRODUCTIVE % = forward progress
CLUSTER_DEFINITIONS = {
    "FIX_LOOP":   ["FIX", "VERIFY"],     # rework cluster — identifies thrashing
    "PRODUCTIVE": ["WRITE", "BUILD"],    # forward-progress cluster
    # "JAR_INSPECT": ["EXPLORE"],        # example: narrow to JAR-reading substate
}

# CUSTOMIZE: variant pairs for intervention delta heatmaps
# Format: (variant_a, variant_b, "label") — heatmap shows P_b - P_a
DELTA_PAIRS = [
    ("control", "variant-a", "Effect of hardened prompt"),
    # ("variant-a", "variant-b", "Effect of KB"),
    # ("variant-b", "variant-c", "Effect of full KB"),
    # ("variant-a", "variant-d", "Effect of forge plan/act"),
]

# CUSTOMIZE: human-readable labels for each variant (used in findings.md)
NOTE_MAP = {
    "control":   "Minimal instructions — baseline",
    # "variant-a": "Hardened prompt",
    # "variant-b": "Hardened prompt + KB",
}

# ---------------------------------------------------------------------------
# CUSTOMIZE: Classifier — maps (tool_name, target) → state name
# ---------------------------------------------------------------------------

def classify_state(tool_name: str, target: str) -> str | None:
    """
    Map a tool call to a semantic state name.

    Return None to exclude the tool call from Markov analysis.
    Return a string from STATES to classify it.

    In DISCOVERY_MODE, returns raw "tool:target" so you can inspect
    frequency counts and define the real taxonomy from actual data.
    """
    tool_lower = tool_name.lower() if tool_name else ""
    target_lower = target.lower() if target else ""

    # Discovery mode: return raw label for frequency inspection
    if DISCOVERY_MODE:
        return f"{tool_name}:{target[:40]}"

    # Exclude meta-tools (task management, agent coordination)
    if tool_lower in ("todowrite", "todoread", "task", "taskupdate", "taskcreate",
                      "exitplanmode", "enterplanmode"):
        return None

    # Agent subagent calls — Explore subagents = EXPLORE, others = EXPLORE
    if tool_lower == "agent":
        return "EXPLORE"

    # Writing output files (first production)
    # CUSTOMIZE: narrow by file extension to distinguish productive writes
    if tool_lower in ("write", "writefile", "notebookedit"):
        return "WRITE"

    # Editing output files = rework (FIX)
    # CUSTOMIZE: scope to output files only; exclude editing planning docs
    if tool_lower in ("edit", "str_replace_editor", "str_replace_based_edit"):
        return "FIX"

    # Reading files
    if tool_lower in ("read", "readfile"):
        if "knowledge/" in target_lower or "/kb/" in target_lower:
            return "READ_KB"
        # CUSTOMIZE: reading back your own output = VERIFY, reading source = EXPLORE
        return "EXPLORE"

    # Discovery / search
    if tool_lower in ("glob", "grep"):
        return "EXPLORE"

    # Bash commands
    if tool_lower == "bash":
        # CUSTOMIZE: distinguish build/test commands from verification/discovery
        # Example: if "mvn" in target_lower or "gradle" in target_lower: return "BUILD"
        # Example: if "ls " in target_lower or "find " in target_lower: return "EXPLORE"
        return "BUILD"

    return "EXPLORE"  # default

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data():
    con = duckdb.connect()
    items = con.execute(f"SELECT * FROM '{DATA_DIR}/item_results.parquet'").df()
    tool_uses_path = DATA_DIR / "tool_uses.parquet"
    tools = (con.execute(f"SELECT * FROM '{tool_uses_path}'").df()
             if tool_uses_path.exists() else None)
    con.close()
    return items, tools

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import time
    t0 = time.time()
    print("Markov Chain Analysis (domain wrapper)")
    print("=" * 50)
    print("\nLoading data...")
    items, tools = load_data()
    if tools is None or tools.empty:
        print("ERROR: No tool_uses.parquet found. Run load_results.py first.")
        raise SystemExit(1)
    print(f"  tool_uses: {len(tools)} rows")
    print(f"  item_results: {len(items)} rows")

    # NOTE: load_results.py already uses the library's expected column names:
    #   item_id (not item_slug), tool_target (not target), global_seq for ordering
    tools = tools.sort_values(["variant", "item_id", "global_seq"])

    pipeline = MarkovAnalysisPipeline(
        classify_fn=classify_state,
        states=STATES,
        output_dir=OUTPUT_DIR,
        analysis_dir=ANALYSIS_DIR,
        colors=COLORS,
        variant_order=VARIANT_ORDER,
        cluster_definitions=CLUSTER_DEFINITIONS,
        delta_pairs=DELTA_PAIRS,
        note_map=NOTE_MAP,
        enable_sankey=True,
    )
    pipeline.run(tools, items)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Figures:      {OUTPUT_DIR}")
    print(f"  Summary:      {ANALYSIS_DIR / 'markov-findings.md'}")
