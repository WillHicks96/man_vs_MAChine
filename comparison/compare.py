"""
compare.py — Man vs. MAChine: quantitative + qualitative comparison
===================================================================
Walks each team's folder, collects verifiable metrics (filesystem + AST),
applies a manually-curated rubric for qualitative dimensions, and produces
pitch-deck-style plots in comparison/plots/.

GENERALISATION GUIDE
────────────────────
To run on a different experiment or a subset of teams:
  1. Update TEAMS          — mapping of display-label → folder path
  2. Update ACTIVE_TEAMS  — list of keys from TEAMS to include in *this* run
  3. Update COLORS         — one colour per team label
  4. Update TASK_NAMES     — canonical task list from the problem statement
  5. Update RUBRIC         — task-completion scores (0 / 0.5 / 1) with evidence notes
  6. Update HOLISTIC_SCORES — physics insight / rigor / reproducibility / novelty (1–5)
  7. Update PHASE_SCRIPTS  — per-phase script globs for the multi-step team (if present)
Everything else (file counts, LOC, code-quality analysis) is auto-measured.

Usage:
    python comparison/compare.py
"""

import ast
import json
import re
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent.parent
COMP_DIR = Path(__file__).resolve().parent
PLOT_DIR = COMP_DIR / "plots"
PLOT_DIR.mkdir(exist_ok=True)

# ── Team configuration ────────────────────────────────────────────────────────
# Full registry: add new teams here without touching the rest of the script.
TEAMS = {
    "Human":           ROOT / "team_human",
    "AI\nSingle-step": ROOT / "team_machine_singlestep",
    "AI\nMulti-step":  ROOT / "team_machine_multistep",
}

# ★ Change this list to select which teams appear in plots this run.
ACTIVE_TEAMS = [
    "Human",
    # "AI\nSingle-step",   # commented out for the current 2-team run
    "AI\nMulti-step",
]

COLORS = {
    "Human":           "#FF6B6B",
    "AI\nSingle-step": "#4CC9F0",
    "AI\nMulti-step":  "#F0A500",
}

SHORT = {
    "Human":           "Human",
    "AI\nSingle-step": "AI Single-step",
    "AI\nMulti-step":  "AI Multi-step",
}

# ── Style ──────────────────────────────────────────────────────────────────────
BG   = "#0D1117"
TXT  = "#E6EDF3"
GRID = "#21262D"
MUTED = "#8B949E"

plt.rcParams.update({
    "figure.facecolor": BG,
    "axes.facecolor":   BG,
    "axes.edgecolor":   GRID,
    "axes.labelcolor":  TXT,
    "xtick.color":      TXT,
    "ytick.color":      TXT,
    "text.color":       TXT,
    "grid.color":       GRID,
    "grid.alpha":       0.4,
    "legend.facecolor": "#161B22",
    "legend.edgecolor": GRID,
    "font.family":      "DejaVu Sans",
    "font.size":        11,
    "axes.titlesize":   14,
    "axes.labelsize":   12,
    "axes.titleweight": "bold",
    "xtick.labelsize":  10,
    "ytick.labelsize":  10,
})


# ── Metric collection (filesystem) ────────────────────────────────────────────

def count_loc(py_file: Path) -> int:
    """Non-blank, non-comment lines of Python code."""
    try:
        lines = py_file.read_text(errors="ignore").splitlines()
        return sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))
    except Exception:
        return 0


def _safe_parse(text: str):
    """Parse Python source, suppressing SyntaxWarnings from third-party scripts."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(text)


def count_functions(py_file: Path) -> int:
    """Number of function definitions (any nesting depth)."""
    try:
        tree = _safe_parse(py_file.read_text(errors="ignore"))
        return sum(
            1 for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
    except Exception:
        return 0


# Patterns that mark a PNG as exploratory (not publication-ready).
_EXPLORATORY_PATTERNS = [
    "step1_random_profiles_halo",       # singlestep individual halo exploration
    "step6_agnheated_or_postmerger_halo",
    "step6_sloshing_coolcores_halo",
    "phase1_10profiles",                # multistep 10-halo exploration grid
    "overview_gas", "overview_dm",      # spatial maps
    "multifield_4field_random",
    "preview_",                         # video pipeline previews
]


def classify_png(name: str) -> str:
    """Return 'pub' or 'exploratory' for a PNG filename."""
    n = name.lower()
    return "exploratory" if any(p in n for p in _EXPLORATORY_PATTERNS) else "pub"


def doc_chars(team_dir: Path) -> dict:
    """
    Structured reports (tex, bib) vs execution logs (md).
    Returns {'structured': int, 'logs': int} character counts.
    """
    structured, logs = 0, 0
    for f in team_dir.rglob("*.tex"):
        try:
            structured += len(f.read_text(errors="ignore"))
        except Exception:
            pass
    for f in team_dir.rglob("*.bib"):
        try:
            structured += len(f.read_text(errors="ignore"))
        except Exception:
            pass
    for f in team_dir.rglob("*.md"):
        try:
            logs += len(f.read_text(errors="ignore"))
        except Exception:
            pass
    return {"structured": structured, "logs": logs}


def collect_team_metrics(team_dir: Path) -> dict:
    """Walk a team directory and return raw metric counts."""
    py_files   = list(team_dir.rglob("*.py"))
    png_files  = list(team_dir.rglob("*.png"))
    gif_files  = list(team_dir.rglob("*.gif"))
    json_files = list(team_dir.rglob("*.json"))
    csv_files  = list(team_dir.rglob("*.csv"))

    total_loc   = sum(count_loc(f)       for f in py_files)
    total_funcs = sum(count_functions(f) for f in py_files)

    pub_plots  = sum(1 for f in png_files if classify_png(f.name) == "pub")
    expl_plots = len(png_files) - pub_plots
    n_data     = len(json_files) + len(csv_files)
    docs       = doc_chars(team_dir)

    return {
        "py_files":       len(py_files),
        "total_loc":      total_loc,
        "functions":      total_funcs,
        "total_png":      len(png_files),
        "pub_plots":      pub_plots,
        "expl_plots":     expl_plots,
        "gif_files":      len(gif_files),
        "json_files":     len(json_files),
        "csv_files":      len(csv_files),
        "n_data":         n_data,
        "doc_structured": docs["structured"],
        "doc_logs":       docs["logs"],
    }


# ── Multi-step phase-by-phase breakdown ───────────────────────────────────────
# Update for a different multi-step experiment.
PHASE_SCRIPTS = {
    1: ["phase1_code.py"],
    2: ["phase2_code.py"],
    3: ["phase3_code.py"],
    4: ["phase4_code.py"],
    5: ["phase5_code.py"],
    6: ["phase6_code.py", "phase6_allR_profiles.py"],
    7: ["phase7_particle_gallery.py"],
}

# Key that identifies the multi-step team (used to find phase data).
MULTISTEP_KEY = "AI\nMulti-step"


def collect_phase_data(multistep_dir: Path) -> dict:
    """Per-phase LOC and pub-ready plot counts for the multi-step team."""
    result = {}
    for phase, scripts in PHASE_SCRIPTS.items():
        loc = sum(count_loc(multistep_dir / s)
                  for s in scripts if (multistep_dir / s).exists())
        phase_pngs = list(multistep_dir.glob(f"phase{phase}_*.png"))
        pub   = sum(1 for f in phase_pngs if classify_png(f.name) == "pub")
        result[phase] = {
            "loc":        loc,
            "pub_plots":  pub,
            "total_plots": len(phase_pngs),
        }
    return result


# ── Code quality analysis (AST + regex) ───────────────────────────────────────

# Absolute path prefixes that indicate non-portable hardcoded paths.
_HPC_PATH_RE = re.compile(
    r"""["'](/lustre|/home|/scratch|/data|/work|/proj|/gpfs|/nfs|/global)"""
)
# Numeric literals exempt from "magic number" classification.
_MAGIC_EXEMPT = {0, 1, -1, 2, 10, 100, 0.0, 0.5, 1.0, 2.0, -1.0}


def analyze_code_quality_raw(py_files: list) -> dict | None:
    """
    Auto-measures code quality indicators from Python AST and text.
    Returns None if no Python files exist (team has no saved code).
    All measurements are transparent and verifiable.
    """
    if not py_files:
        return None

    total_funcs, funcs_with_docstrings = 0, 0
    func_line_lengths: list[int] = []
    function_arg_counts: list[int] = []
    raw_lines, comment_lines = 0, 0
    try_except_blocks, assertions = 0, 0
    config_constants = 0
    hardcoded_paths, magic_numbers = 0, 0

    for f in py_files:
        text = f.read_text(errors="ignore")
        lines = text.splitlines()
        raw_lines    += len(lines)
        comment_lines += sum(1 for ln in lines if ln.strip().startswith("#"))
        hardcoded_paths += sum(1 for ln in lines if _HPC_PATH_RE.search(ln))

        try:
            tree = _safe_parse(text)
        except SyntaxError:
            continue

        # Module-level UPPERCASE constants (config/settings heuristic)
        for item in ast.walk(tree):
            if isinstance(item, ast.Module):
                for stmt in item.body:
                    if isinstance(stmt, ast.Assign):
                        for t in stmt.targets:
                            if (isinstance(t, ast.Name)
                                    and t.id.isupper() and len(t.id) > 2):
                                config_constants += 1

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total_funcs += 1
                # Docstring present?
                body = node.body
                if (body
                        and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    funcs_with_docstrings += 1
                # Function length
                if hasattr(node, "end_lineno"):
                    func_line_lengths.append(node.end_lineno - node.lineno + 1)
                # Argument count
                args = node.args
                n_args = (len(args.args)
                          + len(args.posonlyargs)
                          + len(args.kwonlyargs))
                function_arg_counts.append(n_args)

            elif isinstance(node, ast.Try):
                try_except_blocks += 1

            elif isinstance(node, ast.Assert):
                assertions += 1

            elif (isinstance(node, ast.Constant)
                  and isinstance(node.value, (int, float))
                  and node.value not in _MAGIC_EXEMPT):
                magic_numbers += 1

    return {
        "total_funcs":        total_funcs,
        "docstring_coverage": funcs_with_docstrings / total_funcs if total_funcs else 0.0,
        "comment_density":    comment_lines / raw_lines if raw_lines else 0.0,
        "avg_func_length":    float(np.mean(func_line_lengths)) if func_line_lengths else 0.0,
        "avg_func_args":      float(np.mean(function_arg_counts)) if function_arg_counts else 0.0,
        "try_except_blocks":  try_except_blocks,
        "assertions":         assertions,
        "hardcoded_paths":    hardcoded_paths,
        "config_constants":   config_constants,
        "magic_numbers":      magic_numbers,
        "raw_lines":          raw_lines,
        "comment_lines":      comment_lines,
        "funcs_with_docstrings": funcs_with_docstrings,
    }


def score_code_quality(raw: dict | None) -> dict:
    """
    Convert raw AST measurements to 1–5 scores per quality dimension.
    Scoring rationale is documented inline for full transparency.
    Returns zeros for teams without saved code.
    """
    if raw is None:
        return {d: 0.0 for d in
                ["Readability", "Portability", "Robustness", "Extendability"]}

    # ── Readability (1–5) ──────────────────────────────────────────────────
    # Three sub-components, each mapped 0→1 then combined:
    #   docstring_coverage: saturates at 50% coverage  (40% weight)
    #   comment_density:    target 10–15% of raw lines (30% weight)
    #   avg_func_length:    peak at ~30 lines; penalty for very long/short (30% weight)
    doc_score = min(1.0, raw["docstring_coverage"] / 0.5)
    cmt_score = min(1.0, raw["comment_density"] / 0.12)
    len_score = max(0.0, 1.0 - abs(raw["avg_func_length"] - 30.0) / 60.0)
    readability = 1.0 + 4.0 * (0.4 * doc_score + 0.3 * cmt_score + 0.3 * len_score)

    # ── Portability (1–5) ─────────────────────────────────────────────────
    # Hardcoded HPC paths are the main portability killer.
    # 0 paths → 5, each 2 paths shave off 1 point, floor at 1.
    portability = max(1.0, 5.0 - raw["hardcoded_paths"] / 2.0)

    # ── Robustness (1–5) ──────────────────────────────────────────────────
    # Measured as try/except density relative to function count.
    # ~40% of functions guarded → score of 5; none → 1.
    if raw["total_funcs"] > 0:
        rob_ratio = raw["try_except_blocks"] / (raw["total_funcs"] * 0.4)
    else:
        rob_ratio = 0.0
    robustness = 1.0 + 4.0 * min(1.0, rob_ratio)

    # ── Extendability (1–5) ───────────────────────────────────────────────
    # Three sub-components:
    #   config_constants: module-level UPPER_CASE vars, saturate at 10 (40% weight)
    #   avg_func_args:    well-parameterised functions → args≥3 (30% weight)
    #   magic_penalty:    fewer magic numbers per raw line → better (30% weight)
    config_score  = min(1.0, raw["config_constants"] / 10.0)
    args_score    = min(1.0, raw["avg_func_args"] / 3.0)
    magic_density = raw["magic_numbers"] / (raw["raw_lines"] + 1)
    magic_penalty = max(0.0, 1.0 - magic_density / 0.15)  # saturates at 15% magic density
    extendability = 1.0 + 4.0 * (0.4 * config_score + 0.3 * args_score + 0.3 * magic_penalty)

    return {
        "Readability":   round(readability, 2),
        "Portability":   round(portability, 2),
        "Robustness":    round(robustness, 2),
        "Extendability": round(extendability, 2),
    }


# ── Qualitative rubric ─────────────────────────────────────────────────────────
# Update TASK_NAMES and RUBRIC for a different experiment.

TASK_NAMES = [
    "Profile\nexploration",   # T1
    "Reference\nmodel fits",  # T2
    "Relaxation\ncriteria",   # T3
    "Stacked\nprofiles",      # T4
    "Scaling\nrelations",     # T5
    "Extreme\nobjects",       # T6
    "Core\nthermo-\ndynamics",# T7
]

# 0 = not attempted, 0.5 = partial, 1.0 = complete.
# Evidence notes justify every entry.
RUBRIC = {
    # Human:
    #  T1 – no systematic 10-halo profile exploration in the script
    #  T2 – no NFW / beta-model fit output files
    #  T3 – x_off (1 of 4 criteria) + core_entropy; novel Δ_Mgal criterion (own agenda)
    #  T4 – no stacked profile panels stratified by relaxation class
    #  T5 – CM_relation() (concentration–mass; not L_X–T or Y_SZ–M)
    #  T6 – no extreme / discordant object analysis
    #  T7 – core_entropy_hists* plots (partial; no TPI / BH analysis)
    "Human":           [0.0, 0.0, 0.5, 0.0, 0.5, 0.0, 0.5],

    # AI Single-step:
    #  T1 – step1_random_profiles_halo_*.png (10 halos) + manifest.json
    #  T2 – fit_params.json (NFW / beta-model parameters)
    #  T3 – concordance.json, concordance_table.csv, halo_criteria_table.json (all 4 criteria)
    #  T4 – profile_{entropy,lxbolo,mass,ne,pthermal}_A/B/C/D (20 stacked plots)
    #  T5 – scatter_T_L_by_R3.png, scatter_M_Y_by_R1.png
    #  T6 – step6_sloshing, step6_agnheated, step6_extreme_unrelaxed + JSON catalogues
    #  T7 – scatter_coolingproxy, scatter_Mmmagn, scatter_znecore_zTratio
    "AI\nSingle-step": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],

    # AI Multi-step:
    #  T1 – phase1_10profiles_10halos.png, phase1_mass_histogram.png, phase1_results.json
    #  T2 – phase2_nfw_comparison.png, phase2_profiles_vs_references.png
    #  T3 – phase4_offsets_distributions.png, phase3_results.json
    #  T4 – phase5_stacked_profiles_by_class.png, phase6_stacked_profiles_comprehensive*.png
    #  T5 – phase5_scaling_relations.png
    #  T6 – phase5_extreme_objects_profiles.png, halo shortlist TXTs
    #  T7 – phase5_core_entropy_analysis.png, phase6_tpi_diagnostic.png, phase7_particle_gallery.png
    "AI\nMulti-step":  [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
}

HOLISTIC_SCORES = {
    "Human":           {"Physics\nInsight": 4, "Rigor": 3, "Reproducibility": 4, "Novelty": 5},
    "AI\nSingle-step": {"Physics\nInsight": 4, "Rigor": 5, "Reproducibility": 2, "Novelty": 2},
    "AI\nMulti-step":  {"Physics\nInsight": 4, "Rigor": 4, "Reproducibility": 5, "Novelty": 3},
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def active_colors() -> list[str]:
    return [COLORS[t] for t in ACTIVE_TEAMS]


def active_short() -> list[str]:
    return [SHORT[t] for t in ACTIVE_TEAMS]


def fig_width(base_per_team: float = 4.5, minimum: float = 8.0) -> float:
    """Scale figure width with the number of active teams."""
    return max(minimum, base_per_team * len(ACTIVE_TEAMS))


def savefig(fig, name: str):
    path = PLOT_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    print(f"  → {path}")
    plt.close(fig)


def bar_label(ax, rects, fmt="{:.0f}", offset=2, color=TXT, fontsize=10):
    for rect in rects:
        h = rect.get_height()
        ax.text(
            rect.get_x() + rect.get_width() / 2,
            h + offset,
            fmt.format(h),
            ha="center", va="bottom",
            color=color, fontsize=fontsize, fontweight="bold",
        )


# ── Collect all metrics ────────────────────────────────────────────────────────

def collect_all():
    metrics, code_quality = {}, {}
    for name in ACTIVE_TEAMS:
        path = TEAMS[name]
        metrics[name] = collect_team_metrics(path)
        py_files = list(path.rglob("*.py"))
        raw = analyze_code_quality_raw(py_files)
        metrics[name]["code_quality_raw"] = raw
        code_quality[name] = score_code_quality(raw)

    phase_data = {}
    if MULTISTEP_KEY in ACTIVE_TEAMS:
        phase_data = collect_phase_data(TEAMS[MULTISTEP_KEY])

    out = {
        "active_teams":  ACTIVE_TEAMS,
        "team_metrics":  {SHORT[k]: {kk: vv for kk, vv in v.items()
                                     if kk != "code_quality_raw"}
                          for k, v in metrics.items()},
        "code_quality":  {SHORT[k]: v for k, v in code_quality.items()},
        "code_quality_raw": {SHORT[k]: metrics[k]["code_quality_raw"]
                             for k in ACTIVE_TEAMS},
        "phase_data":    {str(k): v for k, v in phase_data.items()},
        "rubric":        {SHORT[k]: RUBRIC[k] for k in ACTIVE_TEAMS},
        "holistic":      {SHORT[k]: HOLISTIC_SCORES[k] for k in ACTIVE_TEAMS},
        "task_names":    TASK_NAMES,
    }
    with open(COMP_DIR / "metrics_data.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print("Saved metrics_data.json")
    return metrics, phase_data, code_quality


# ── Figure 1: Output Inventory (simplified) ───────────────────────────────────

def fig_inventory(metrics: dict):
    """Grouped bar: pub-ready plots and Python scripts only."""
    categories = [
        ("pub_plots", "Pub-ready\nPlots"),
        ("py_files",  "Python\nScripts"),
    ]
    n_cat  = len(categories)
    n_team = len(ACTIVE_TEAMS)
    x      = np.arange(n_cat)
    width  = min(0.35, 0.8 / n_team)
    offsets = np.linspace(-(n_team - 1) / 2, (n_team - 1) / 2, n_team) * width

    fig, ax = plt.subplots(figsize=(fig_width(3.5, 7), 5.5))

    for i, (label, color) in enumerate(zip(ACTIVE_TEAMS, active_colors())):
        vals  = [metrics[label][key] for key, _ in categories]
        rects = ax.bar(x + offsets[i], vals, width,
                       label=SHORT[label], color=color, alpha=0.88, zorder=3)
        bar_label(ax, rects, offset=1)

        # Annotate functions inside script bar only for teams with code
        if metrics[label]["py_files"] > 0:
            fn = metrics[label]["functions"]
            loc = metrics[label]["total_loc"]
            ax.text(
                x[1] + offsets[i],
                vals[1] / 2,
                f"{fn} fns\n{loc} LOC",
                ha="center", va="center",
                fontsize=9, color=BG, fontweight="bold",
            )

    ax.set_xticks(x)
    ax.set_xticklabels([name for _, name in categories], fontsize=12)
    ax.set_ylabel("Count")
    ax.set_title("Output Inventory per Team", pad=14)
    ax.yaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(fontsize=11)
    savefig(fig, "fig1_inventory.png")


# ── Figure 2: Yield Ratio Donuts ──────────────────────────────────────────────

def fig_yield(metrics: dict):
    """Donut per team: pub-ready vs exploratory plot fraction."""
    n = len(ACTIVE_TEAMS)
    # Extra vertical space so count labels below the ring don't clip
    fig, axes = plt.subplots(1, n, figsize=(max(5 * n, 8), 6.2))
    if n == 1:
        axes = [axes]

    for ax, label in zip(axes, ACTIVE_TEAMS):
        pub   = metrics[label]["pub_plots"]
        expl  = metrics[label]["expl_plots"]
        total = pub + expl
        pct   = 100 * pub / total if total else 0
        color = COLORS[label]

        # Thin ring: width=0.18 leaves a large open centre for the text
        ax.pie(
            [pub, expl],
            colors=[color, "#2A2F3A"],
            startangle=90,
            wedgeprops={"width": 0.18, "edgecolor": BG, "linewidth": 2},
        )

        # Large % in the centre — plenty of room with a thin ring
        ax.text(0, 0.08, f"{pct:.0f}%",
                ha="center", va="center",
                fontsize=44, fontweight="bold", color=color)
        ax.text(0, -0.18, "pub-ready",
                ha="center", va="center",
                fontsize=13, color=TXT)

        # Raw counts just below the axes (outside the pie area)
        ax.text(0, -1.45,
                f"■ Pub-ready: {pub}    ░ Exploratory: {expl}    Total: {total}",
                ha="center", va="center",
                fontsize=10, color=MUTED)

        ax.set_title(SHORT[label], pad=16, color=color,
                     fontsize=14, fontweight="bold")

    fig.suptitle("Plot Yield Ratio — Pub-ready vs Exploratory",
                 fontsize=15, fontweight="bold", y=1.01)
    savefig(fig, "fig2_yield.png")


# ── Figure 3: Scientific Scope Heat-map ───────────────────────────────────────

def fig_scope():
    """Heat-map: task-completion scores per active team."""
    scores = np.array([RUBRIC[l] for l in ACTIVE_TEAMS])  # (n_team, n_task)
    n_team, n_task = scores.shape

    cell_h = 1.1
    fig_h  = max(3.5, cell_h * n_team + 1.5)
    fig, ax = plt.subplots(figsize=(min(13, 1.5 * n_task + 2), fig_h))

    im = ax.imshow(scores, aspect="auto", vmin=0, vmax=1, cmap="RdYlGn")

    ax.set_xticks(range(n_task))
    ax.set_xticklabels(TASK_NAMES, fontsize=10)
    ax.set_yticks(range(n_team))
    ax.set_yticklabels([SHORT[l] for l in ACTIVE_TEAMS], fontsize=12)

    ax.set_xticks(np.arange(-.5, n_task, 1), minor=True)
    ax.set_yticks(np.arange(-.5, n_team, 1), minor=True)
    ax.grid(which="minor", color=BG, linewidth=2.5)
    ax.tick_params(which="minor", length=0)

    for r, row in enumerate(scores):
        for c, val in enumerate(row):
            sym   = "✓" if val == 1.0 else ("½" if val == 0.5 else "✗")
            shade = "#0D1117" if val > 0.4 else TXT
            ax.text(c, r, sym, ha="center", va="center",
                    fontsize=18, color=shade, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.set_ticks([0, 0.5, 1])
    cbar.set_ticklabels(["Not done", "Partial", "Complete"])
    cbar.ax.tick_params(labelsize=9, colors=TXT)

    ax.set_title("Scientific Scope Coverage (7-Task Rubric)", pad=12)
    fig.tight_layout()
    savefig(fig, "fig3_scope.png")


# ── Figure 4: Code & Phase Convergence ────────────────────────────────────────

def fig_code(metrics: dict, phase_data: dict):
    """
    Left:  LOC + function count bar per active team.
    Right: multi-step phase-by-phase convergence (only when multi-step is active).
    """
    has_multistep = MULTISTEP_KEY in ACTIVE_TEAMS and phase_data
    ncols = 2 if has_multistep else 1
    fig, axes = plt.subplots(1, ncols, figsize=(7 * ncols, 5.5))
    ax1 = axes[0] if ncols > 1 else axes
    ax2 = axes[1] if ncols > 1 else None

    # --- LOC bar ---
    n     = len(ACTIVE_TEAMS)
    x     = np.arange(n)
    locs  = [metrics[l]["total_loc"]  for l in ACTIVE_TEAMS]
    funcs = [metrics[l]["functions"]  for l in ACTIVE_TEAMS]
    bars  = ax1.bar(x, locs, color=active_colors(), alpha=0.88, width=0.5, zorder=3)
    bar_label(ax1, bars, offset=20)

    for xi, (loc, fn, label) in enumerate(zip(locs, funcs, ACTIVE_TEAMS)):
        if loc > 0:
            ax1.text(xi, loc / 2, f"{fn} fns",
                     ha="center", va="center",
                     fontsize=11, color=BG, fontweight="bold")
        else:
            ax1.text(xi, 30, "no saved\nscripts",
                     ha="center", va="bottom",
                     fontsize=9, color=MUTED, style="italic")

    ax1.set_xticks(x)
    ax1.set_xticklabels(active_short(), fontsize=11)
    ax1.set_ylabel("Lines of Code (non-blank, non-comment)")
    ax1.set_title("Codebase Size", pad=12)
    ax1.yaxis.grid(True, zorder=0)
    ax1.set_axisbelow(True)
    ax1.annotate("Number inside bar = defined functions",
                 xy=(0.02, -0.1), xycoords="axes fraction",
                 fontsize=8, color=MUTED)

    if not has_multistep or ax2 is None:
        fig.tight_layout()
        savefig(fig, "fig4_code.png")
        return

    # --- Phase convergence (right panel) ---
    phases  = sorted(phase_data.keys())
    cum_loc = list(np.cumsum([phase_data[p]["loc"]      for p in phases]))
    cum_pub = list(np.cumsum([phase_data[p]["pub_plots"] for p in phases]))
    phase_loc_per = [phase_data[p]["loc"] for p in phases]

    color_ms = COLORS[MULTISTEP_KEY]

    ax2b = ax2.twinx()
    ax2.bar(phases, phase_loc_per, color=color_ms, alpha=0.30, label="Phase LOC")
    ax2.plot(phases, cum_loc, "o-", color=color_ms, lw=2, ms=7,
             label="Cumulative LOC")
    ax2.set_ylabel("Lines of Code", color=color_ms)
    ax2.tick_params(axis="y", colors=color_ms)

    ax2b.plot(phases, cum_pub, "s--", color="#98FF98", lw=2, ms=7,
              label="Cumul. pub-ready plots")
    ax2b.set_ylabel("Cumulative pub-ready plots", color="#98FF98")
    ax2b.tick_params(axis="y", colors="#98FF98")

    ax2.set_xticks(phases)
    ax2.set_xticklabels([f"Ph {p}" for p in phases], fontsize=9)
    ax2.set_xlabel("Phase")
    ax2.set_title("Multi-step: Phase Convergence", pad=12)
    ax2.yaxis.grid(True, zorder=0)
    ax2.set_axisbelow(True)

    lines1, labs1 = ax2.get_legend_handles_labels()
    lines2, labs2 = ax2b.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labs1 + labs2, loc="upper left", fontsize=9)

    fig.tight_layout()
    savefig(fig, "fig4_code.png")


# ── Figure 5: Holistic Radar ───────────────────────────────────────────────────

def fig_radar():
    """Spider chart: physics insight / rigor / reproducibility / novelty."""
    dims   = list(next(iter(HOLISTIC_SCORES.values())).keys())
    n_dims = len(dims)
    angles = np.linspace(0, 2 * np.pi, n_dims, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"polar": True})
    ax.set_facecolor(BG)
    ax.spines["polar"].set_color(GRID)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["1", "2", "3", "4", "5"], color=MUTED, fontsize=8)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dims, fontsize=11, color=TXT)

    for label in ACTIVE_TEAMS:
        vals = [HOLISTIC_SCORES[label][d] for d in dims] + \
               [HOLISTIC_SCORES[label][dims[0]]]
        ax.plot(angles, vals, "o-", lw=2.5,
                color=COLORS[label], label=SHORT[label])
        ax.fill(angles, vals, alpha=0.12, color=COLORS[label])

    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15), fontsize=11)
    ax.set_title("Holistic Quality Scores (1–5)", pad=22,
                 fontsize=14, fontweight="bold")
    savefig(fig, "fig5_radar.png")


# ── Figure 6: Documentation Depth ─────────────────────────────────────────────

def fig_docs(metrics: dict):
    """Horizontal bar: structured report pages vs execution log pages."""
    n = len(ACTIVE_TEAMS)
    struct_pages = [metrics[l]["doc_structured"] / 3000 for l in ACTIVE_TEAMS]
    log_pages    = [metrics[l]["doc_logs"]        / 3000 for l in ACTIVE_TEAMS]

    y   = np.arange(n)
    fig, ax = plt.subplots(figsize=(fig_width(4.0, 8), max(3.5, 1.0 * n + 2)))

    ax.barh(y, struct_pages, color=active_colors(), alpha=0.88,
            label="Structured reports (TeX/Bib/Md summary)")
    ax.barh(y, log_pages, left=struct_pages,
            color=active_colors(), alpha=0.28,
            label="Execution / agent logs (Md)")

    for i, (sp, lp, label) in enumerate(
            zip(struct_pages, log_pages, ACTIVE_TEAMS)):
        if sp > 0:
            ax.text(sp / 2, i, f"{sp:.0f} pg",
                    va="center", ha="center", fontsize=9,
                    color=BG, fontweight="bold")
        if lp > 5:
            ax.text(sp + lp / 2, i, f"{lp:.0f} pg logs",
                    va="center", ha="center", fontsize=9, color=MUTED)
        elif lp == 0 and sp == 0:
            ax.text(1, i, "no documentation",
                    va="center", fontsize=9, color=MUTED, style="italic")

    ax.set_yticks(y)
    ax.set_yticklabels(active_short(), fontsize=12)
    ax.set_xlabel("Estimated pages (~3 000 chars/page)")
    ax.set_title("Documentation Depth", pad=12)
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9, loc="lower right")
    fig.tight_layout()
    savefig(fig, "fig6_docs.png")


# ── Figure 7: Summary Scoreboard ──────────────────────────────────────────────

def fig_scoreboard(metrics: dict, code_quality: dict):
    """Pitch-deck summary table with all key metrics."""
    col_labels = [
        "Scripts", "Pub-ready\nPlots", "LOC",
        "Scope\nCoverage", "Repro-\nducibility", "Novelty",
        "Readability\n(auto)", "Portability\n(auto)", "Robustness\n(auto)",
    ]

    rows = []
    for label in ACTIVE_TEAMS:
        scope_pct = f"{100 * np.mean(RUBRIC[label]):.0f}%"
        repro     = f"{HOLISTIC_SCORES[label]['Reproducibility']}/5"
        novelty   = f"{HOLISTIC_SCORES[label]['Novelty']}/5"
        cq        = code_quality[label]

        def fmt_cq(val: float) -> str:
            return f"{val:.1f}/5" if val > 0 else "N/A"

        rows.append([
            str(metrics[label]["py_files"]),
            str(metrics[label]["pub_plots"]),
            str(metrics[label]["total_loc"]),
            scope_pct, repro, novelty,
            fmt_cq(cq["Readability"]),
            fmt_cq(cq["Portability"]),
            fmt_cq(cq["Robustness"]),
        ])

    n_team = len(ACTIVE_TEAMS)
    fig, ax = plt.subplots(figsize=(max(13, 2 * n_team + 9), 1.2 * n_team + 2))
    ax.axis("off")

    tbl = ax.table(
        cellText=rows,
        rowLabels=active_short(),
        colLabels=col_labels,
        cellLoc="center", rowLoc="center",
        loc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1.2, 2.0 + 0.2 * (3 - n_team))  # taller rows when fewer teams

    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor(GRID)
        if r == 0:
            cell.set_facecolor("#21262D")
            cell.set_text_props(color=TXT, fontweight="bold")
        elif c == -1:
            team_key = ACTIVE_TEAMS[r - 1]
            cell.set_facecolor(COLORS[team_key])
            cell.set_text_props(color=BG, fontweight="bold")
        else:
            cell.set_facecolor("#161B22")
            cell.set_text_props(color=TXT)

    ax.set_title("Man vs. MAChine — Key Metrics at a Glance",
                 fontsize=15, fontweight="bold", pad=20)
    savefig(fig, "fig7_scoreboard.png")


# ── Figure 8: Code Quality Radar ──────────────────────────────────────────────

def fig_code_quality(code_quality: dict, metrics: dict):
    """
    Two-panel figure:
      Left  – radar comparing code quality dimensions.
      Right – bar chart of raw AST measurements (comment density,
              docstring coverage, try/except count, hardcoded paths).
    """
    # Filter to teams that actually have Python code.
    code_teams = [l for l in ACTIVE_TEAMS if metrics[l]["py_files"] > 0]
    if not code_teams:
        print("  (skipping fig8 – no team has saved Python files)")
        return

    dims   = ["Readability", "Portability", "Robustness", "Extendability"]
    angles = np.linspace(0, 2 * np.pi, len(dims), endpoint=False).tolist()
    angles += angles[:1]

    fig = plt.figure(figsize=(14, 6))
    ax_radar = fig.add_subplot(121, polar=True)
    ax_bar   = fig.add_subplot(122)

    # ── Left: radar ──
    ax_radar.set_facecolor(BG)
    ax_radar.spines["polar"].set_color(GRID)
    ax_radar.set_ylim(0, 5)
    ax_radar.set_yticks([1, 2, 3, 4, 5])
    ax_radar.set_yticklabels(["1", "2", "3", "4", "5"], color=MUTED, fontsize=8)
    ax_radar.set_xticks(angles[:-1])
    ax_radar.set_xticklabels(dims, fontsize=12, color=TXT)

    for label in code_teams:
        vals = [code_quality[label][d] for d in dims] + \
               [code_quality[label][dims[0]]]
        ax_radar.plot(angles, vals, "o-", lw=2.5,
                      color=COLORS[label], label=SHORT[label])
        ax_radar.fill(angles, vals, alpha=0.15, color=COLORS[label])

    ax_radar.legend(loc="upper right", bbox_to_anchor=(1.45, 1.15), fontsize=11)
    ax_radar.set_title("Code Quality Scores (1–5, auto-measured)",
                       pad=22, fontsize=13, fontweight="bold")

    # ── Right: raw measurement bar chart ──
    raw_metrics = [
        ("comment_density",    "Comment\nDensity (%)", 100),   # ×100 for %
        ("docstring_coverage", "Docstring\nCoverage (%)", 100),
        ("try_except_blocks",  "try/except\nBlocks", 1),
        ("hardcoded_paths",    "Hardcoded\nPaths", 1),
    ]

    n_raw   = len(raw_metrics)
    n_teams = len(code_teams)
    x       = np.arange(n_raw)
    width   = min(0.30, 0.7 / n_teams)
    offsets = np.linspace(-(n_teams - 1) / 2,
                          (n_teams - 1) / 2, n_teams) * width

    for i, label in enumerate(code_teams):
        raw = metrics[label]["code_quality_raw"]
        if raw is None:
            continue
        vals = [raw[key] * scale for key, _, scale in raw_metrics]
        rects = ax_bar.bar(x + offsets[i], vals, width,
                           label=SHORT[label], color=COLORS[label],
                           alpha=0.88, zorder=3)
        bar_label(ax_bar, rects, fmt="{:.1f}", offset=0.3, fontsize=9)

    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels([name for _, name, _ in raw_metrics], fontsize=11)
    ax_bar.set_ylabel("Value (% where applicable)")
    ax_bar.set_title("Raw Code Quality Measurements (auto)", pad=12)
    ax_bar.yaxis.grid(True, zorder=0)
    ax_bar.set_axisbelow(True)
    ax_bar.legend(fontsize=10)
    ax_bar.annotate(
        "Lower hardcoded paths = more portable   |   Higher comment/docstring = more readable",
        xy=(0.5, -0.13), xycoords="axes fraction",
        ha="center", fontsize=8, color=MUTED,
    )

    fig.tight_layout(pad=2.0)
    savefig(fig, "fig8_code_quality.png")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"Active teams: {[SHORT[t] for t in ACTIVE_TEAMS]}")
    print("Collecting metrics from filesystem …")
    metrics, phase_data, code_quality = collect_all()

    print("\nGenerating plots …")
    fig_inventory(metrics)
    fig_yield(metrics)
    fig_scope()
    fig_code(metrics, phase_data)
    fig_radar()
    fig_docs(metrics)
    fig_scoreboard(metrics, code_quality)
    fig_code_quality(code_quality, metrics)

    print("\nDone. All plots written to", PLOT_DIR)
    return metrics, phase_data, code_quality


if __name__ == "__main__":
    main()
