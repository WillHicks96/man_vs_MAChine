"""
Generate a presentation-ready version of the Output Inventory bar chart
(left panel of fig4_code.png) with the summary table below it.
White background, LaTeX fonts, large text for publication quality.

Usage:
    python comparison/fig4_inventory_only.py
"""

import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── Import data helpers from compare.py ──────────────────────────────────────
from comparison.compare import (
    ACTIVE_TEAMS, COLORS, SHORT, PLOT_DIR, collect_all,
)

# ── LaTeX / publication style ────────────────────────────────────────────────
BG    = "#FFFFFF"
TXT   = "#1a1a1a"
GRID  = "#cccccc"
MUTED = "#444444"

plt.rcParams.update({
    "text.usetex":        False,
    "mathtext.fontset":   "cm",
    "font.family":        "serif",
    "font.serif":         ["CMU Serif", "Computer Modern Roman",
                           "DejaVu Serif", "Times New Roman", "serif"],
    "font.size":          20,
    "figure.facecolor":   BG,
    "axes.facecolor":     BG,
    "axes.edgecolor":     "#888888",
    "axes.linewidth":     1.5,
    "axes.labelcolor":    TXT,
    "axes.titlesize":     26,
    "axes.labelsize":     22,
    "axes.titleweight":   "bold",
    "xtick.color":        TXT,
    "ytick.color":        TXT,
    "xtick.labelsize":    20,
    "ytick.labelsize":    20,
    "text.color":         TXT,
    "grid.color":         GRID,
    "grid.alpha":         0.5,
    "legend.facecolor":   "#f5f5f5",
    "legend.edgecolor":   "#cccccc",
    "legend.fontsize":    20,
})


def bar_label(ax, rects, fmt="{:.0f}", offset=2, fontsize=16):
    for rect in rects:
        h = rect.get_height()
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            h + offset,
            fmt.format(h),
            ha="center", va="bottom",
            color=TXT, fontsize=fontsize, fontweight="bold",
        )


def main():
    metrics, _phase_data, _code_quality = collect_all()

    # ── Bar chart ────────────────────────────────────────────────────────────
    categories = [
        ("pub_plots", "Pub-ready Plots"),
        ("py_files",  "Python Scripts"),
    ]
    n_cat   = len(categories)
    n_team  = len(ACTIVE_TEAMS)
    x       = np.arange(n_cat)
    width   = min(0.35, 0.8 / n_team)
    offsets = np.linspace(-(n_team - 1) / 2, (n_team - 1) / 2, n_team) * width

    fig, ax = plt.subplots(figsize=(8, 8))
    fig.subplots_adjust(bottom=0.28)

    for i, label in enumerate(ACTIVE_TEAMS):
        vals  = [metrics[label][key] for key, _ in categories]
        rects = ax.bar(x + offsets[i], vals, width,
                       label=SHORT[label], color=COLORS[label], alpha=0.88, zorder=3)
        bar_label(ax, rects, offset=0.5, fontsize=18)

    ax.set_xticks(x)
    ax.set_xticklabels([name for _, name in categories], fontsize=20)
    ax.set_ylabel("Count", fontsize=22)
    ax.set_title("Output Inventory per Team", pad=18, fontsize=24, fontweight="bold")
    ax.yaxis.grid(True, zorder=0)
    ax.set_ylim(0, 40)
    ax.set_axisbelow(True)
    ax.legend(fontsize=20, ncol=2)

    # ── Summary table below the chart ────────────────────────────────────────
    tbl_rows = [[SHORT[l],
                 str(metrics[l]["functions"]),
                 str(metrics[l]["total_loc"])]
                for l in ACTIVE_TEAMS]
    tbl_cols = ["Team", "Functions", "Lines of code"]

    ax_tbl = fig.add_axes([0.12, 0.02, 0.76, 0.18])
    ax_tbl.axis("off")

    tbl = ax_tbl.table(
        cellText=tbl_rows,
        colLabels=tbl_cols,
        cellLoc="center",
        loc="center",
        bbox=[0.05, 0.0, 0.9, 1.0],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(18)
    tbl.scale(1, 1.8)
    tbl.auto_set_column_width([0, 1, 2])

    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor(GRID)
        if r == 0:
            cell.set_facecolor("#e8e8e8")
            cell.set_text_props(color=TXT, fontweight="bold")
        else:
            team_key = ACTIVE_TEAMS[r - 1]
            cell.set_facecolor(COLORS[team_key] if c == 0 else "#f5f5f5")
            cell.set_text_props(
                color="white" if c == 0 else TXT,
                fontweight="bold" if c == 0 else "normal",
            )

    # ── Disclaimer ───────────────────────────────────────────────────────────
    fig.text(
        0.5, -0.02,
        "* Two independent, single-trial explorations of the same scientific question\n"
        "   \u2014 but with fundamentally different approaches. Not a task-for-task comparison.",
        ha="center", va="top",
        fontsize=16, color=MUTED, style="italic",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f0f0f0",
                  edgecolor="#cccccc", alpha=0.9),
    )

    outpath = PLOT_DIR / "fig4_output_inventory.png"
    fig.savefig(outpath, dpi=200, bbox_inches="tight", facecolor=BG)
    print(f"  \u2192 {outpath}")
    plt.close(fig)


if __name__ == "__main__":
    main()