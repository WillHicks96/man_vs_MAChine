"""
Generate a presentation-ready version of the code quality radar plot (left panel only).
White background, LaTeX fonts, large text for publication quality.

Usage:
    python comparison/fig8_radar_only.py
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
    # LaTeX-style fonts via mathtext (no full LaTeX install needed)
    "text.usetex":        False,
    "mathtext.fontset":   "cm",          # Computer Modern
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


def main():
    metrics, _phase_data, code_quality = collect_all()

    code_teams = [l for l in ACTIVE_TEAMS if metrics[l]["py_files"] > 0]
    if not code_teams:
        print("  (skipping – no team has saved Python files)")
        return

    dims   = ["Readability", "Portability", "Robustness", "Extendability"]
    angles = np.linspace(0, 2 * np.pi, len(dims), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))

    ax.set_facecolor(BG)
    ax.spines["polar"].set_color(GRID)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["1", "2", "3", "4", "5"], color=MUTED, fontsize=17)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dims, fontsize=22, color=TXT, fontweight="bold")
    # Push dimension labels outward to avoid overlap with data
    for lbl in ax.get_xticklabels():
        lbl.set_position((0, 0.14))
    # Fine-tune horizontal alignment for the right-side label ("Readability")
    tick_labels = ax.get_xticklabels()
    tick_labels[0].set_ha("left")       # Readability (0°, right side)
    tick_labels[1].set_ha("center")     # Portability (top)
    tick_labels[2].set_ha("right")      # Robustness (left side)
    tick_labels[3].set_ha("center")     # Extendability (bottom)

    for label in code_teams:
        vals = [code_quality[label][d] for d in dims] + \
               [code_quality[label][dims[0]]]
        ax.plot(angles, vals, "o-", lw=3.5, markersize=9,
                color=COLORS[label], label=SHORT[label])
        ax.fill(angles, vals, alpha=0.40, color=COLORS[label])

    ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1.02), fontsize=20,
              framealpha=0.9)
    ax.set_title(r"Code Quality Scores (1$\endash$5, auto-measured)",
                 pad=38, fontsize=24, fontweight="bold")

    fig.subplots_adjust(bottom=0.18)

    fig.text(
        0.5, 0.03,
        "* Two independent, single-trial explorations of the same scientific question\n"
        "   \u2014 but with fundamentally different approaches. Not a task-for-task comparison.",
        ha="center", va="bottom",
        fontsize=18, color=MUTED, style="italic",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f0f0f0",
                  edgecolor="#cccccc", alpha=0.9),
    )

    outpath = PLOT_DIR / "fig8_code_quality_radar.png"
    fig.savefig(outpath, dpi=200, bbox_inches="tight", facecolor=BG)
    print(f"  \u2192 {outpath}")
    plt.close(fig)


if __name__ == "__main__":
    main()
