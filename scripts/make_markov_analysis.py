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
    uv pip install markov-agent-analysis

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
from markov_agent_analysis.transitions import apply_classify, build_transition_counts, normalize_to_probability_matrix
from markov_agent_analysis.figures import make_single_transition_matrix

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
    "EXPLORE",      # reading source files, directories, dep investigation
    "READ_KB",      # reading knowledge base files (knowledge/ dir)
    "READ_SKILL",   # invoking a SkillsJars skill (Skill tool call)
    "JAR_INSPECT",  # jar tf — agent spelunking .m2 to find classes/imports
    "WRITE",        # writing test files (first time)
    "BUILD",        # ./mvnw clean test jacoco:report — actual test execution
    "VERIFY",       # reading back JaCoCo report to confirm coverage %
    "FIX",          # editing test files after a failure
]

COLORS = {
    "EXPLORE":     "#4C72B0",
    "READ_KB":     "#55A868",
    "READ_SKILL":  "#29a8ab",
    "JAR_INSPECT": "#937860",
    "WRITE":       "#2ca02c",
    "BUILD":       "#8172B2",
    "VERIFY":      "#CCB974",
    "FIX":         "#C44E52",
}

VARIANT_ORDER = [
    "simple",
    "hardened",
    "hardened+kb",
    "hardened+sae",
    "hardened+skills",
    "hardened+skills+sae",
    "hardened+skills+sae+forge",
]

# FIX_LOOP: rework cluster — agent retrying after test failure
# JAR_INSPECT_CLUSTER: framework-friction cluster — agent spelunking .m2 to find imports
#   This is addressable by KB: if KB provides correct Spring test annotations/imports,
#   the agent never needs to inspect jars.
# PRODUCTIVE: forward-progress — writing and running tests for the first time
CLUSTER_DEFINITIONS = {
    "FIX_LOOP":        ["FIX", "BUILD"],   # rework cycle: edit → rebuild
    "PRODUCTIVE":      ["WRITE"],          # forward progress: writing tests
    "JAR_INSPECT":     ["JAR_INSPECT"],    # framework friction: addressable by KB
}

DELTA_PAIRS = [
    ("simple",    "hardened",    "Effect of hardened prompt"),
    ("hardened",  "hardened+kb", "Effect of KB"),
    ("hardened",  "hardened+skills", "Effect of skills"),
    ("hardened+kb", "hardened+skills", "KB vs skills"),
]

NOTE_MAP = {
    "simple":                  "Minimal prompt — baseline",
    "hardened":                "Hardened prompt + stopping condition",
    "hardened+kb":             "Hardened + flat KB injection",
    "hardened+sae":            "Hardened + pre-analysis script",
    "hardened+skills":         "Hardened + SkillsJars (structured KB)",
    "hardened+skills+sae":     "Hardened + skills + pre-analysis script",
    "hardened+skills+sae+forge": "Two-phase: explore → act",
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

    # Skill tool — agent invoking a SkillsJars skill
    if tool_lower == "skill":
        return "READ_SKILL"

    # Agent subagent calls — counts as exploration overhead
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

    # Bash commands — distinguish by what the command is actually doing
    if tool_lower == "bash":
        # JAR inspection: agent reading .m2 jars to discover classes/imports
        # Signal: agent doesn't know test framework imports — addressable by KB
        if "jar tf" in target_lower or "jar -tf" in target_lower or "jar --list" in target_lower:
            return "JAR_INSPECT"

        # Actual test execution: the real BUILD state
        # Matches: ./mvnw clean test, ./mvnw test jacoco:report, ./mvnw verify, ./gradlew test
        if any(x in target_lower for x in (
            "mvnw clean", "mvnw test", "mvnw verify", "mvnw package",
            "gradlew test", "gradlew build", "gradlew check",
            "jacoco:report", "mvn test", "mvn verify",
        )):
            return "BUILD"

        # Coverage/result verification: reading back output to confirm success
        if any(x in target_lower for x in (
            "jacoco", "index.html", "coverage", "surefire-reports",
        )):
            return "VERIFY"

        # Filesystem and dependency exploration: not a real build
        if any(x in target_lower for x in (
            "ls ", "find ", "tree ", "cat ", "echo ", "pwd",
            "dependency:tree", "dep:tree", "find /home/mark/.m2",
        )):
            return "EXPLORE"

        # Scaffolding (mkdir, cp, mv) — exclude: not semantically interesting
        if any(x in target_lower for x in ("mkdir", "cp ", "mv ", "chmod", "touch ")):
            return None

        # Default bash: treat as EXPLORE (grep, sed, awk, etc.)
        return "EXPLORE"

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

    # Generate cost/steps bar chart — the "money shot"
    print("\nGenerating cost vs steps bar chart...")
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use("Agg")
    import duckdb
    con = duckdb.connect()
    cost_df = con.execute(f"""
        SELECT variant,
               round(avg(cost_usd), 4)      AS mean_cost,
               round(stddev(cost_usd), 4)   AS std_cost,
               round(avg(phase_count), 1)   AS mean_steps
        FROM '{DATA_DIR}/item_results.parquet'
        GROUP BY variant ORDER BY variant
    """).df()
    con.close()
    ordered = [v for v in VARIANT_ORDER if v in cost_df["variant"].values]
    cost_df = cost_df.set_index("variant").loc[ordered].reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    plt.rcParams.update({"font.family": "serif", "font.size": 10})

    bar_colors = ["#C44E52" if "forge" in v else "#4C72B0" for v in cost_df["variant"]]

    ax = axes[0]
    bars = ax.bar(range(len(cost_df)), cost_df["mean_cost"], color=bar_colors,
                  yerr=cost_df["std_cost"], capsize=4, edgecolor="white", linewidth=0.5)
    ax.set_xticks(range(len(cost_df)))
    ax.set_xticklabels(cost_df["variant"], rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Mean cost per item (USD)", fontsize=11)
    ax.set_title("Cost per variant", fontsize=12, fontweight="bold")
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    for bar, cost in zip(bars, cost_df["mean_cost"]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"${cost:.2f}", ha="center", va="bottom", fontsize=8)

    ax = axes[1]
    bars2 = ax.bar(range(len(cost_df)), cost_df["mean_steps"], color=bar_colors,
                   edgecolor="white", linewidth=0.5)
    ax.set_xticks(range(len(cost_df)))
    ax.set_xticklabels(cost_df["variant"], rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Mean steps per item", fontsize=11)
    ax.set_title("Steps per variant", fontsize=12, fontweight="bold")
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    for bar, steps in zip(bars2, cost_df["mean_steps"]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f"{steps:.0f}", ha="center", va="bottom", fontsize=8)

    fig.suptitle("Agent efficiency by variant — cost and step count", fontsize=13)
    fig.tight_layout()
    out = OUTPUT_DIR / "cost-steps-comparison"
    fig.savefig(str(out) + ".png", dpi=150, bbox_inches="tight")
    fig.savefig(str(out) + ".pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  {out}.png")

    # Generate individual per-variant heatmaps for inline document use
    # (large, readable, one variant per file — used in the LaTeX primer)
    print("\nGenerating individual variant heatmaps...")
    classified = apply_classify(tools, classify_state)
    count_matrices = build_transition_counts(classified, STATES)
    for variant in VARIANT_ORDER:
        if variant not in count_matrices:
            continue
        P = normalize_to_probability_matrix(count_matrices[variant])
        safe_name = variant.replace("+", "-").replace(" ", "_")
        out_path = OUTPUT_DIR / f"heatmap-{safe_name}"
        make_single_transition_matrix(P, STATES, variant, out_path)
        print(f"  {out_path}.png")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Figures:      {OUTPUT_DIR}")
    print(f"  Summary:      {ANALYSIS_DIR / 'markov-findings.md'}")
