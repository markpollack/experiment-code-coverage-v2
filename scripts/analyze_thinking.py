#!/usr/bin/env python3
"""
Thinking block analysis — simple descriptive view.
Five charts:
  1. Thinking as % of generative budget (output + thinking)  [input_tokens not captured — cache bug]
  2. What was the agent thinking about? (keyword topic distribution)
  3. Thinking share vs quality score
  4. Thinking topics: passed vs failed items
  5. Thinking block length vs pass rate (more words = more confident?)
"""

import json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "code-coverage-v2" / "sessions"
DATA_DIR    = Path(__file__).resolve().parent.parent / "data" / "curated"
OUT_DIR     = Path(__file__).resolve().parent.parent / "docs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BG = "#FAFAFA"
COLORS = {
    "output":   "#74c476",
    "thinking": "#fd8d3c",
}

TOPIC_KEYWORDS = {
    "EXPLORE":  ["explore", "look at", "examine", "read", "check", "understand", "find", "search", "structure", "file"],
    "WRITE":    ["write", "creat", "implement", "add test", "generate", "draft"],
    "BUILD":    ["build", "compil", "maven", "mvnw", "run test", "execute"],
    "FIX":      ["fix", "error", "fail", "wrong", "incorrect", "broken", "issue", "problem", "exception"],
    "VERIFY":   ["coverage", "jacoco", "verify", "percent", "instruction", "pass"],
    "JAR":      ["jar", "decompil", "javap", ".m2", "cache", "binary", "artifact"],
    "META":     ["retry", "reconsider", "different approach", "try again", "already tried", "stuck", "instead"],
}

TOPIC_COLORS = {
    "EXPLORE": "#4292c6", "WRITE": "#74c476", "BUILD": "#fd8d3c",
    "FIX": "#de2d26",     "VERIFY": "#756bb1", "JAR": "#8c6d31", "META": "#969696",
}
TOPIC_ORDER = ["EXPLORE", "WRITE", "BUILD", "FIX", "VERIFY", "JAR", "META"]

VARIANT_ORDER = [
    "simple", "hardened", "hardened+kb", "hardened+preanalysis",
    "hardened+skills", "hardened+skills+preanalysis",
    "hardened+skills+preanalysis+plan-act",
]
VARIANT_SHORT = {
    "simple": "simple",
    "hardened": "hardened",
    "hardened+kb": "+kb",
    "hardened+preanalysis": "+preanalysis",
    "hardened+skills": "+skills",
    "hardened+skills+preanalysis": "+skills\n+preanalysis",
    "hardened+skills+preanalysis+plan-act": "+skills\n+preanalysis\n+plan-act",
}


# ── helpers ────────────────────────────────────────────────────────────────

def classify_block(text: str) -> str:
    t = text.lower()
    scores = {topic: sum(1 for kw in kws if kw in t)
              for topic, kws in TOPIC_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "META"


def load_thinking_blocks():
    """Walk all session JSON files, collect thinking blocks per variant + item."""
    records = []
    for session_dir in sorted(RESULTS_DIR.iterdir()):
        for jf in session_dir.glob("*.json"):
            if jf.name == "session.json":
                continue
            variant = jf.stem
            try:
                data = json.loads(jf.read_text())
            except Exception:
                continue
            for item in data.get("items", []):
                item_id = item.get("itemSlug", "unknown")
                passed  = item.get("passed", False)
                ir = item.get("invocationResult", {})
                for phase in ir.get("phases", []):
                    for block in phase.get("thinkingBlocks", []):
                        if block.strip():
                            records.append({
                                "variant": variant,
                                "item_id": item_id,
                                "passed":  passed,
                                "topic":   classify_block(block),
                                "length":  len(block),
                            })
    return pd.DataFrame(records)


# ── chart 1: thinking share of generative budget ─────────────────────────

def chart_thinking_share():
    """
    Show thinking tokens as % of (output + thinking).
    Input tokens are excluded — prompt caching means input_tokens in this dataset
    captures only bare non-cached context (~14 tokens), not the full cache read.
    """
    df = pd.read_parquet(DATA_DIR / "item_results.parquet")
    df = df[df["output_tokens"] + df["thinking_tokens"] > 0].copy()
    df["gen_total"] = df["output_tokens"] + df["thinking_tokens"]
    df["thinking_pct"] = 100 * df["thinking_tokens"] / df["gen_total"]
    df["output_pct"]   = 100 * df["output_tokens"]   / df["gen_total"]

    agg = (df.groupby("variant")[["output_pct", "thinking_pct"]]
             .mean()
             .reindex([v for v in VARIANT_ORDER if v in df["variant"].unique()]))

    fig, ax = plt.subplots(figsize=(9, 4), facecolor=BG)
    ax.set_facecolor(BG)

    labels = [VARIANT_SHORT.get(v, v) for v in agg.index]
    x = np.arange(len(labels))
    w = 0.55

    bottom = np.zeros(len(agg))
    for col, label, color in [
        ("output_pct",   "Output",   COLORS["output"]),
        ("thinking_pct", "Thinking", COLORS["thinking"]),
    ]:
        vals = agg[col].values
        ax.bar(x, vals, w, bottom=bottom, color=color, label=label)
        # label bars where thinking slice is big enough to read
        if col == "thinking_pct":
            for xi, (v, b) in enumerate(zip(vals, bottom)):
                if v > 4:
                    ax.text(xi, b + v / 2, f"{v:.0f}%",
                            ha="center", va="center", fontsize=7.5, color="white", fontweight="bold")
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylabel("% of generative budget", fontsize=9)
    ax.set_title("Thinking vs output  (% of output + thinking tokens)", fontsize=11)
    ax.legend(loc="upper right", fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)

    note = "Note: input_tokens excludes prompt-cache reads in this dataset"
    ax.text(0.01, -0.13, note, transform=ax.transAxes,
            fontsize=7, color="#666", style="italic")

    fig.tight_layout()
    out = OUT_DIR / "thinking-token-breakdown.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  {out}")


# ── chart 2: what was it thinking about? ──────────────────────────────────

def chart_thinking_topics(df_blocks: pd.DataFrame):
    if df_blocks.empty:
        print("  No thinking blocks found — skipping chart 2.")
        return

    counts = df_blocks["topic"].value_counts().reindex(TOPIC_ORDER).dropna()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), facecolor=BG)
    fig.suptitle("What was the agent thinking about?", fontsize=12)

    # left: overall pie
    colors = [TOPIC_COLORS[t] for t in counts.index]
    ax1.set_facecolor(BG)
    wedges, texts, autotexts = ax1.pie(
        counts.values, labels=counts.index, colors=colors,
        autopct="%1.0f%%", startangle=90, textprops={"fontsize": 9},
        pctdistance=0.75,
    )
    # prevent label overlap on small slices
    for text in texts:
        text.set_fontsize(8.5)
    ax1.set_title("All variants combined", fontsize=10)

    # right: stacked bar by variant
    ax2.set_facecolor(BG)
    variants = [v for v in VARIANT_ORDER if v in df_blocks["variant"].unique()]
    bottoms = np.zeros(len(variants))
    for topic in TOPIC_ORDER:
        vals = []
        for v in variants:
            sub = df_blocks[df_blocks["variant"] == v]
            total = len(sub)
            vals.append(100 * len(sub[sub["topic"] == topic]) / total if total else 0)
        ax2.bar(range(len(variants)), vals, bottom=bottoms,
                color=TOPIC_COLORS[topic], label=topic)
        bottoms += np.array(vals)

    ax2.set_xticks(range(len(variants)))
    ax2.set_xticklabels([VARIANT_SHORT.get(v, v) for v in variants], fontsize=7.5)
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax2.set_title("By variant  (EXPLORE dominates regardless of scaffolding)", fontsize=10)
    ax2.legend(loc="upper right", fontsize=7.5, ncol=2)
    ax2.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    out = OUT_DIR / "thinking-topics.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  {out}")


# ── chart 3: thinking share vs quality ────────────────────────────────────

def chart_thinking_vs_quality():
    df = pd.read_parquet(DATA_DIR / "item_results.parquet")
    df["gen_total"] = df["output_tokens"] + df["thinking_tokens"]
    df["thinking_pct"] = 100 * df["thinking_tokens"] / df["gen_total"].replace(0, pd.NA)

    agg = df.groupby("variant").agg(
        thinking_pct=("thinking_pct", "mean"),
        quality=("t3_quality", "mean"),
        cost=("cost_usd", "mean"),
    ).reindex([v for v in VARIANT_ORDER if v in df["variant"].unique()])

    fig, ax = plt.subplots(figsize=(7, 4.5), facecolor=BG)
    ax.set_facecolor(BG)

    ax.scatter(
        agg["thinking_pct"], agg["quality"],
        s=agg["cost"] * 40, c="#fd8d3c", alpha=0.8, edgecolors="#555", linewidths=0.6,
    )
    for v, row in agg.iterrows():
        ax.annotate(VARIANT_SHORT.get(v, v),
                    (row["thinking_pct"], row["quality"]),
                    textcoords="offset points", xytext=(6, 2), fontsize=7.5)

    ax.set_xlabel("Thinking tokens as % of generative budget", fontsize=9)
    ax.set_ylabel("Quality score (T3)", fontsize=9)
    ax.set_title("Thinking share vs quality  (bubble size = avg cost)", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()

    out = OUT_DIR / "thinking-vs-quality.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  {out}")


# ── chart 4: thinking topics — passed vs failed ────────────────────────────

def chart_topics_pass_vs_fail(df_blocks: pd.DataFrame):
    """
    Do passing and failing items think differently?
    Side-by-side stacked bars: one for passed=True, one for passed=False.
    """
    if df_blocks.empty:
        print("  No thinking blocks found — skipping chart 4.")
        return

    passed_df = df_blocks[df_blocks["passed"] == True]
    failed_df = df_blocks[df_blocks["passed"] == False]

    if passed_df.empty or failed_df.empty:
        print("  Not enough pass/fail data — skipping chart 4.")
        return

    fig, ax = plt.subplots(figsize=(6, 4.5), facecolor=BG)
    ax.set_facecolor(BG)

    groups = [("Passed", passed_df), ("Failed", failed_df)]
    x = np.arange(len(groups))
    w = 0.5
    bottoms = np.zeros(len(groups))

    for topic in TOPIC_ORDER:
        vals = []
        for _, sub in groups:
            total = len(sub)
            vals.append(100 * len(sub[sub["topic"] == topic]) / total if total else 0)
        ax.bar(x, vals, w, bottom=bottoms, color=TOPIC_COLORS[topic], label=topic)
        for xi, (v, b) in enumerate(zip(vals, bottoms)):
            if v > 5:
                ax.text(xi, b + v / 2, f"{v:.0f}%",
                        ha="center", va="center", fontsize=8.5, color="white", fontweight="bold")
        bottoms += np.array(vals)

    ax.set_xticks(x)
    ax.set_xticklabels([g[0] for g in groups], fontsize=11)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_title("Thinking topics: passed vs failed items", fontsize=11)
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    ax.spines[["top", "right"]].set_visible(False)

    n_passed = df_blocks[df_blocks["passed"]]["item_id"].nunique()
    n_failed = df_blocks[~df_blocks["passed"]]["item_id"].nunique()
    ax.text(0.02, -0.1,
            f"n={n_passed} passed items, n={n_failed} failed items (thinking blocks, all variants)",
            transform=ax.transAxes, fontsize=7, color="#666", style="italic")

    fig.tight_layout()
    out = OUT_DIR / "thinking-pass-vs-fail.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  {out}")


# ── chart 5: thinking block length vs pass rate ────────────────────────────

def chart_thinking_length_vs_quality(df_blocks: pd.DataFrame):
    """
    More words = more confident?
    Per-item: avg thinking block length vs pass rate.
    Each dot = one variant; also show per-item scatter.
    """
    if df_blocks.empty:
        print("  No thinking blocks found — skipping chart 5.")
        return

    df_results = pd.read_parquet(DATA_DIR / "item_results.parquet")

    # per-item avg thinking block length
    item_think = (df_blocks.groupby(["variant", "item_id"])["length"]
                  .agg(avg_block_len="mean", block_count="count")
                  .reset_index())

    merged = item_think.merge(
        df_results[["variant", "item_id", "passed", "t3_quality"]],
        on=["variant", "item_id"], how="inner"
    )

    if merged.empty:
        print("  Could not merge thinking blocks with item results — skipping chart 5.")
        return

    # per-variant aggregates
    vagg = merged.groupby("variant").agg(
        avg_len=("avg_block_len", "mean"),
        pass_rate=("passed", "mean"),
    ).reindex([v for v in VARIANT_ORDER if v in merged["variant"].unique()])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5), facecolor=BG)
    fig.suptitle("Thinking block length vs outcome  (more words = more confident?)", fontsize=12)

    # left: per-item scatter
    ax1.set_facecolor(BG)
    colors_map = {True: "#4292c6", False: "#de2d26"}
    for passed_val, label in [(True, "Passed"), (False, "Failed")]:
        sub = merged[merged["passed"] == passed_val]
        ax1.scatter(sub["avg_block_len"], sub["block_count"],
                    c=colors_map[passed_val], alpha=0.55, s=20, label=label)
    ax1.set_xlabel("Avg thinking block length (chars)", fontsize=9)
    ax1.set_ylabel("Number of thinking blocks", fontsize=9)
    ax1.set_title("Per item: length × volume", fontsize=10)
    ax1.legend(fontsize=8)
    ax1.spines[["top", "right"]].set_visible(False)

    # right: per-variant avg block length vs pass rate
    ax2.set_facecolor(BG)
    ax2.scatter(vagg["avg_len"], vagg["pass_rate"] * 100,
                s=80, c="#fd8d3c", alpha=0.9, edgecolors="#555", linewidths=0.6)
    for v, row in vagg.iterrows():
        ax2.annotate(VARIANT_SHORT.get(v, v),
                     (row["avg_len"], row["pass_rate"] * 100),
                     textcoords="offset points", xytext=(5, 2), fontsize=7.5)
    ax2.set_xlabel("Avg thinking block length (chars)", fontsize=9)
    ax2.set_ylabel("Pass rate (%)", fontsize=9)
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax2.set_title("Per variant: longer thoughts → higher pass rate?", fontsize=10)
    ax2.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    out = OUT_DIR / "thinking-length-vs-quality.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  {out}")


# ── chart 6: policy table — intent → first action ─────────────────────────

def load_intent_action_pairs():
    """
    For each thinking block, record (topic, first_tool_after_it).
    Uses proportional index mapping: thinking block i → tool use at floor(i*n_tools/n_thinking).
    Returns DataFrame with columns: variant, topic, tool.
    """
    rows = []
    for session_dir in sorted(RESULTS_DIR.iterdir()):
        for jf in session_dir.glob("*.json"):
            if jf.name == "session.json":
                continue
            try:
                data = json.loads(jf.read_text())
            except Exception:
                continue
            variant = jf.stem
            for item in data.get("items", []):
                ir = item.get("invocationResult", {})
                for phase in ir.get("phases", []):
                    tbs = phase.get("thinkingBlocks", [])
                    tus = phase.get("toolUses", [])
                    if not tbs or not tus:
                        continue
                    n_t, n_u = len(tbs), len(tus)
                    for i, tb in enumerate(tbs):
                        topic = classify_block(tb)
                        first_tool_idx = int(i * n_u / n_t)
                        tu = tus[first_tool_idx]
                        tool_name = tu["name"]
                        if tool_name == "Bash":
                            cmd = tu.get("input", {}).get("command", "")
                            tool = classify_bash_command(cmd)
                        else:
                            tool = tool_name
                        rows.append({"variant": variant, "topic": topic, "tool": tool})
    return pd.DataFrame(rows)


POLICY_TOOLS = ["Bash:EXPLORE", "Bash:BUILD", "Bash:VERIFY", "Bash:JAR",
                "Read", "Write", "Edit", "Glob", "Agent", "Bash:other"]
POLICY_TOOLS_SHORT = {
    "Bash:EXPLORE": "Bash\n(explore)", "Bash:BUILD": "Bash\n(build)",
    "Bash:VERIFY": "Bash\n(verify)", "Bash:JAR": "Bash\n(jar)",
    "Read": "Read", "Write": "Write", "Edit": "Edit",
    "Glob": "Glob", "Agent": "Agent", "Bash:other": "Bash\n(other)",
}
POLICY_TOPIC_ORDER = ["EXPLORE", "FIX", "VERIFY", "BUILD", "WRITE", "JAR", "META"]
VARIANT_HAS_SKILLS = {"hardened+skills", "hardened+skills+sae", "hardened+skills+sae+forge"}


def classify_bash_command(cmd: str) -> str:
    """Sub-classify a Bash command into a semantic action label."""
    c = cmd.lower()
    if any(x in c for x in ("jar tf", "jar -tf", "jar --list", "javap", "jar xf")):
        return "Bash:JAR"
    if any(x in c for x in (
        "mvnw", "mvn ", "./mvnw", "gradlew", "gradle ",
        "test-compile", "jacoco:report", "mvn test", "mvn verify",
    )):
        return "Bash:BUILD"
    if any(x in c for x in ("jacoco", "coverage", "surefire-reports")):
        return "Bash:VERIFY"
    if any(x in c for x in ("find ", "grep ", "ls ", "cat ", "tree ", "head ", "tail ", "wc ")):
        return "Bash:EXPLORE"
    return "Bash:other"


def chart_policy_table(df_pairs: pd.DataFrame):
    """
    Two-panel chart:
      Left  — heatmap of P(tool | intent), all variants combined
      Right — policy sharpness (max P per intent) + EXPLORE policy split by skills
    """
    if df_pairs.empty:
        print("  No intent-action pairs — skipping chart 6.")
        return

    # Build matrix
    matrix = pd.DataFrame(0.0, index=POLICY_TOPIC_ORDER, columns=POLICY_TOOLS)
    sharpness = {}
    topic_n   = {}
    for topic in POLICY_TOPIC_ORDER:
        sub = df_pairs[df_pairs["topic"] == topic]
        if len(sub) == 0:
            continue
        topic_n[topic] = len(sub)
        from collections import Counter
        cnt = Counter(sub["tool"])
        total = len(sub)
        for tool in POLICY_TOOLS:
            matrix.loc[topic, tool] = cnt.get(tool, 0) / total
        sharpness[topic] = max(cnt.values()) / total

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.5), facecolor=BG)
    fig.suptitle("Intent → Action Policy  (what the agent does after each type of thinking)",
                 fontsize=12)

    # --- left: heatmap ---
    ax1.set_facecolor(BG)
    mat_vals = matrix.values
    im = ax1.imshow(mat_vals, cmap="Blues", aspect="auto", vmin=0, vmax=1)

    ax1.set_xticks(range(len(POLICY_TOOLS)))
    ax1.set_xticklabels([POLICY_TOOLS_SHORT.get(t, t) for t in POLICY_TOOLS], fontsize=8)
    ax1.set_yticks(range(len(POLICY_TOPIC_ORDER)))
    topics_with_n = [f"{t}\n(n={topic_n.get(t, 0)})" for t in POLICY_TOPIC_ORDER]
    ax1.set_yticklabels(topics_with_n, fontsize=8.5)
    ax1.set_title("P(tool | intent)  — all variants", fontsize=10)

    for r, topic in enumerate(POLICY_TOPIC_ORDER):
        for c, tool in enumerate(POLICY_TOOLS):
            v = mat_vals[r, c]
            if v > 0.05:
                color = "white" if v > 0.55 else "black"
                ax1.text(c, r, f"{v:.0%}", ha="center", va="center",
                         fontsize=8.5, color=color, fontweight="bold")

    plt.colorbar(im, ax=ax1, fraction=0.03, pad=0.02)
    ax1.spines[["top", "right", "bottom", "left"]].set_visible(False)

    # --- right: sharpness bar + EXPLORE skills split ---
    ax2.set_facecolor(BG)

    # sharpness bars
    topics = [t for t in POLICY_TOPIC_ORDER if t in sharpness]
    sharp_vals = [sharpness[t] for t in topics]
    colors = ["#fd8d3c" if v >= 0.6 else "#4292c6" if v >= 0.45 else "#c6dbef"
              for v in sharp_vals]
    bars = ax2.barh(topics, sharp_vals, color=colors, edgecolor="#aaa", linewidth=0.4)

    for bar, v in zip(bars, sharp_vals):
        ax2.text(v + 0.01, bar.get_y() + bar.get_height() / 2,
                 f"{v:.0%}", va="center", fontsize=8.5, color="#333")

    ax2.set_xlim(0, 1.05)
    ax2.axvline(0.6, color="#de2d26", linewidth=0.8, linestyle="--", alpha=0.6)
    ax2.axvline(0.45, color="#fd8d3c", linewidth=0.8, linestyle="--", alpha=0.5)
    ax2.set_xlabel("Policy sharpness  (max P(action | intent))", fontsize=9)
    ax2.set_title("Sharp = deterministic / Diffuse = exploratory", fontsize=10)
    ax2.spines[["top", "right"]].set_visible(False)

    note = "Dashed lines at 0.45 and 0.60 — informal 'diffuse / moderate / sharp' thresholds"
    ax2.text(0.01, -0.12, note, transform=ax2.transAxes,
             fontsize=7, color="#666", style="italic")

    fig.tight_layout()
    out = OUT_DIR / "thinking-policy-table.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  {out}")


def chart_explore_skills_split(df_pairs: pd.DataFrame):
    """
    EXPLORE thinking → tool distribution: with-skills vs without-skills variants.
    Shows that skills shift EXPLORE from Bash-first to Read-first.
    """
    if df_pairs.empty:
        print("  No intent-action pairs — skipping chart 7.")
        return

    exp = df_pairs[df_pairs["topic"] == "EXPLORE"].copy()
    exp["group"] = exp["variant"].map(
        lambda v: "With +skills" if v in VARIANT_HAS_SKILLS else "Without +skills"
    )

    from collections import Counter

    fig, ax = plt.subplots(figsize=(7, 4), facecolor=BG)
    ax.set_facecolor(BG)

    groups = ["Without +skills", "With +skills"]
    x = np.arange(len(groups))
    w = 0.55
    bottoms = np.zeros(len(groups))

    group_tools = {}
    for g in groups:
        sub = exp[exp["group"] == g]
        cnt = Counter(sub["tool"])
        total = len(sub)
        group_tools[g] = {tool: cnt.get(tool, 0) / total for tool in POLICY_TOOLS}

    tool_colors = {
        "Bash:EXPLORE": "#fd8d3c", "Bash:BUILD": "#cc4e00", "Bash:VERIFY": "#ff9900",
        "Bash:JAR": "#8c5e00", "Bash:other": "#e0c090",
        "Read": "#4292c6", "Write": "#74c476",
        "Edit": "#756bb1", "Glob": "#8c6d31", "Agent": "#969696",
    }

    for tool in POLICY_TOOLS:
        vals = [group_tools[g].get(tool, 0) * 100 for g in groups]
        label = POLICY_TOOLS_SHORT.get(tool, tool).replace("\n", " ")
        ax.bar(x, vals, w, bottom=bottoms, color=tool_colors.get(tool, "#cccccc"), label=label)
        for xi, (v, b) in enumerate(zip(vals, bottoms)):
            if v > 5:
                ax.text(xi, b + v / 2, f"{v:.0f}%",
                        ha="center", va="center", fontsize=9, color="white", fontweight="bold")
        bottoms += np.array(vals)

    n_without = len(exp[exp["group"] == "Without +skills"])
    n_with    = len(exp[exp["group"] == "With +skills"])
    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"Without +skills\n(n={n_without} EXPLORE blocks)",
         f"With +skills\n(n={n_with} EXPLORE blocks)"],
        fontsize=9,
    )
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_title("EXPLORE intent: how skills shift the first action",
                 fontsize=11)
    ax.legend(loc="upper right", fontsize=8, ncol=3)
    ax.spines[["top", "right"]].set_visible(False)

    note = "Skills shift EXPLORE from Bash-first to Read-first — orientation strategy changes"
    ax.text(0.01, -0.12, note, transform=ax.transAxes,
            fontsize=8, color="#333", style="italic")

    fig.tight_layout()
    out = OUT_DIR / "thinking-explore-skills-split.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  {out}")


# ── main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating thinking analysis charts…")
    chart_thinking_share()

    print("  Loading thinking blocks from raw JSON (this takes ~30s)…")
    df_blocks = load_thinking_blocks()
    if not df_blocks.empty:
        print(f"  Loaded {len(df_blocks)} thinking blocks across "
              f"{df_blocks['variant'].nunique()} variants, "
              f"{df_blocks['item_id'].nunique()} items")

    chart_thinking_topics(df_blocks)
    chart_thinking_vs_quality()
    chart_topics_pass_vs_fail(df_blocks)
    chart_thinking_length_vs_quality(df_blocks)

    print("  Building intent→action pairs…")
    df_pairs = load_intent_action_pairs()
    if not df_pairs.empty:
        print(f"  Built {len(df_pairs)} intent-action pairs")
    chart_policy_table(df_pairs)
    chart_explore_skills_split(df_pairs)
    print("Done.")
