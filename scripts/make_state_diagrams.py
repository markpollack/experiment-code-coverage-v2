#!/usr/bin/env python3
"""
Generate high-quality state transition diagrams for the blog.

  1. state-diagram-ideal-flow.png  — EXPLORE→WRITE→BUILD→VERIFY, BUILD↔FIX
  2. state-diagram-jar-loop.png    — JAR_INSPECT cycling (hardened variant)
  3. state-diagram-jar-fixed.png   — JAR_INSPECT clean exit (hardened+skills)

Run:
    python scripts/make_state_diagrams.py
"""

import matplotlib.pyplot as plt
from pathlib import Path

from markov_agent_analysis.diagrams import (
    COLORS, BG, RADIUS, ARROW_COLOR,
    setup_ax, draw_node, draw_arrow, draw_self_loop,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "figures"

# Scale factor — all positions, radii, and offsets multiply by S
S = 0.75
R = RADIUS * S          # node radius in scaled units
LO = 0.22 * S           # arrow label offset
SLO = 0.45 * S          # self-loop label offset


def node(ax, x, y, label, color):
    draw_node(ax, x * S, y * S, label, color, radius=R)


def arrow(ax, x0, y0, x1, y1, **kw):
    kw.setdefault("label_off", LO)
    draw_arrow(ax, x0 * S, y0 * S, x1 * S, y1 * S, r0=R, r1=R, **kw)


def self_loop(ax, x, y, **kw):
    kw.setdefault("label_off", SLO)
    draw_self_loop(ax, x * S, y * S, radius=R, **kw)


# ---------------------------------------------------------------------------
# Diagram 1 — Ideal flow
# ---------------------------------------------------------------------------
def make_ideal_flow():
    fig, ax = setup_ax(figsize=(11 * S, 5 * S))

    nx = [1.5, 4.0, 7.0, 9.5]
    ny = 3.2
    fix_x, fix_y = 7.0, 1.3

    for x, label in zip(nx, ["EXPLORE", "WRITE", "BUILD", "VERIFY"]):
        node(ax, x, ny, label, COLORS[label])
    node(ax, fix_x, fix_y, "FIX", COLORS["FIX"])

    arrow(ax, nx[0], ny, nx[1], ny, rad=0.0)
    arrow(ax, nx[1], ny, nx[2], ny, rad=0.0)
    arrow(ax, nx[2], ny, nx[3], ny, rad=0.0)

    arrow(ax, nx[2], ny, fix_x, fix_y, rad=+0.25, color=COLORS["FIX"])
    arrow(ax, fix_x, fix_y, nx[2], ny, rad=+0.25, color=COLORS["FIX"])

    ax.text(5.5 * S, 4.7 * S, "Agent behavior — conceptual flow",
            ha="center", va="center", fontsize=11, color="#555555",
            fontstyle="italic")

    out = OUTPUT_DIR / "state-diagram-ideal-flow"
    fig.savefig(str(out) + ".png", dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  {out}.png")


# ---------------------------------------------------------------------------
# Diagram 2 — JAR_INSPECT cycling
# ---------------------------------------------------------------------------
def make_jar_inspect_loop():
    fig, ax = setup_ax(figsize=(8 * S, 7 * S))

    jx, jy = 4.0, 5.0
    ex, ey = 1.6, 2.0
    wx, wy = 6.4, 2.0
    fx, fy = 4.0, 1.0  # FIX node below JAR_INSPECT

    node(ax, jx, jy, "JAR\nINSPECT", COLORS["JAR_INSPECT"])
    node(ax, ex, ey, "EXPLORE",       COLORS["EXPLORE"])
    node(ax, wx, wy, "WRITE",         COLORS["WRITE"])
    node(ax, fx, fy, "FIX",           COLORS["FIX"])

    # Verified from v2.0.0 parquet: 54 transitions from JAR_INSPECT in hardened
    # Counts: →EXPLORE 10/54=0.19, →WRITE 14/54=0.26, →FIX 10/54=0.19,
    #          self-loop 9/54=0.17, EXPLORE→JAR 9/91=0.10
    arrow(ax, jx, jy, ex, ey, rad=+0.30, label="0.19", color=ARROW_COLOR)
    arrow(ax, ex, ey, jx, jy, rad=+0.30, label="0.10", color=COLORS["EXPLORE"])
    arrow(ax, jx, jy, wx, wy, rad=0.0,   label="0.26", color=ARROW_COLOR)
    arrow(ax, jx, jy, fx, fy, rad=0.0,   label="0.19", color=COLORS["FIX"])

    self_loop(ax, jx, jy, direction="top", label="0.17")

    ax.text(4.0 * S, -0.2 * S,
            "hardened variant — JAR_INSPECT accounts for 18% of all steps",
            ha="center", va="center", fontsize=8, color="#666666",
            fontstyle="italic")

    out = OUTPUT_DIR / "state-diagram-jar-loop"
    fig.savefig(str(out) + ".png", dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  {out}.png")


# ---------------------------------------------------------------------------
# Diagram 3 — JAR_INSPECT clean exit
# ---------------------------------------------------------------------------
def make_jar_inspect_fixed():
    fig, ax = setup_ax(figsize=(7 * S, 5 * S))

    jx, jy = 1.8, 2.5
    bx, by = 5.2, 3.8
    fx, fy = 5.2, 1.2

    node(ax, jx, jy, "JAR\nINSPECT", COLORS["JAR_INSPECT"])
    node(ax, bx, by, "BUILD",         COLORS["BUILD"])
    node(ax, fx, fy, "FIX",           COLORS["FIX"])

    # Verified from v2.0.0 parquet: only 5 transitions from JAR_INSPECT in hardened+skills
    arrow(ax, jx, jy, bx, by, rad=0.0, label="0.60")
    arrow(ax, jx, jy, fx, fy, rad=0.0, label="0.40")

    ax.text(3.5 * S, 0.35 * S,
            "hardened+skills — JAR_INSPECT < 2% of steps, no cycling",
            ha="center", va="center", fontsize=8, color="#666666",
            fontstyle="italic")

    out = OUTPUT_DIR / "state-diagram-jar-fixed"
    fig.savefig(str(out) + ".png", dpi=180, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  {out}.png")


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating state transition diagrams...")
    make_ideal_flow()
    make_jar_inspect_loop()
    make_jar_inspect_fixed()
    print("Done.")
