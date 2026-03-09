#!/usr/bin/env python3
"""
4-field multifield visualizations: 6 most massive halos per group.
Each row = one halo; columns = Dark Matter | Stars | Gas | Gas Temperature.
Stars (2nd) column carries a textbox with δ₁, δ₂, K_core, TPI values.
Output: halo_viz/<group>/multifield_4field_random6_massive.png
"""
import os
import h5py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import opencosmo as oc
from opencosmo.analysis import halo_projection_array

# ── paths ─────────────────────────────────────────────────────────────────────
EXPERIMENT_DIR = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/runs/research_20260218_105441"
PARTICLE_DIR   = "/data/a/cpac/nramachandra/Projects/AmSC/particle_data"
OUTPUT_ROOT    = os.path.join(EXPERIMENT_DIR, "halo_viz")

# Full catalog used by phase6 to derive TPI population z-scores
CATALOG = "/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5"

FILE_MAP = {
    "R1":       "R1.hdf5",
    "R1_andR2": "R1andR2.hdf5",
    "R1_andR3": "R1andR3.hdf5",
    "R1_andR4": "R1andR4.hdf5",
    "R1_notR2": "R1notR2.hdf5",
    "R1_notR3": "R1notR3.hdf5",
    "R1_notR4": "R1notR4.hdf5",
}

N_HALOS = 6

FIELDS  = [("dm",  "particle_mass"),
           ("star", "particle_mass"),
           ("gas",  "particle_mass"),
           ("gas",  "temperature")]
LABELS  = ["Dark Matter", "Stars", "Gas", "Gas Temp"]
CMAPS   = ["pink", "gist_yarg_r", "plasma_r", "rainbow_r"]

# ── build per-halo criteria lookup from full catalog ──────────────────────────
def robust_zscore(x):
    med = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - med))
    return np.where(mad > 0, (x - med) / (1.4826 * mad), 0.0)

print("Loading full catalog to compute relaxation criteria …")
with h5py.File(CATALOG, "r") as f:
    g   = f["halo_properties"]["data"]
    def col(name): return np.array(g[name])

    tags      = col("unique_tag").astype(np.int64)
    r200m     = col("sod_halo_R200m")
    r500c     = col("sod_halo_R500c")
    fof_cx    = col("fof_halo_center_x");  fof_cy  = col("fof_halo_center_y");  fof_cz  = col("fof_halo_center_z")
    fof_comx  = col("fof_halo_com_x");     fof_comy = col("fof_halo_com_y");     fof_comz = col("fof_halo_com_z")
    sod_dm_x  = col("sod_halo_com_x_dm");  sod_dm_y = col("sod_halo_com_y_dm"); sod_dm_z = col("sod_halo_com_z_dm")
    sod_gas_x = col("sod_halo_com_x_gas"); sod_gas_y = col("sod_halo_com_y_gas"); sod_gas_z = col("sod_halo_com_z_gas")
    k_core    = col("sod_halo_core_entropy")      # δ₃ [keV cm²]
    core_ne   = col("sod_halo_core_ne")
    T500c     = col("sod_halo_T500c")
    T500cBoloEx = col("sod_halo_T500cBoloEx")

# δ₁ = |fof_center - fof_CoM| / R_200m
d1_abs  = np.sqrt((fof_cx-fof_comx)**2 + (fof_cy-fof_comy)**2 + (fof_cz-fof_comz)**2)
delta_1 = np.where(r200m > 0, d1_abs / r200m, np.nan)

# δ₂ = |DM_CoM - gas_CoM| / R_500c
d2_abs  = np.sqrt((sod_dm_x-sod_gas_x)**2 + (sod_dm_y-sod_gas_y)**2 + (sod_dm_z-sod_gas_z)**2)
delta_2 = np.where(r500c > 0, d2_abs / r500c, np.nan)

# δ₃ = K_core [keV cm²]
delta_3 = k_core

# δ₄ = TPI = z(ln core_ne) + z(ln T_ratio); T_ratio = T500cBoloEx / T500c
valid_tpi = (core_ne > 0) & (T500c > 0) & (T500cBoloEx > 0)
log_ne     = np.where(valid_tpi, np.log(core_ne),           np.nan)
log_Tratio = np.where(valid_tpi, np.log(T500cBoloEx/T500c), np.nan)
TPI = robust_zscore(log_ne) + robust_zscore(log_Tratio)

# Build lookup: unique_tag -> (δ₁, δ₂, K_core [keV cm²], TPI)
criteria_lookup = {
    int(t): (float(d1), float(d2), float(d3), float(tpi))
    for t, d1, d2, d3, tpi in zip(tags, delta_1, delta_2, delta_3, TPI)
}
print(f"  Criteria lookup built for {len(criteria_lookup):,} halos.")


# ── helper: annotate Stars panels (2nd column) ────────────────────────────────
def annotate_stars_panels(fig, chosen_tags, criteria_lookup, n_fields=4):
    """Add δ textboxes to the 2nd-column (Stars) axes of the figure."""
    # Collect all axes with substantial width (skip colorbars / tiny axes)
    all_axs = fig.axes
    proj_axs = [ax for ax in all_axs if ax.get_position().width > 0.05]

    # Sort row-major: descending y0 (top row first), then ascending x0 (left col first)
    proj_axs.sort(key=lambda ax: (-round(ax.get_position().y0, 3),
                                   ax.get_position().x0))

    n_rows = len(chosen_tags)
    n_cols = n_fields
    expected = n_rows * n_cols

    if len(proj_axs) != expected:
        print(f"  WARNING: expected {expected} proj axes, found {len(proj_axs)} — skipping annotation")
        return

    for row_i, tag in enumerate(chosen_tags):
        ax = proj_axs[row_i * n_cols + 1]   # column index 1 = Stars
        vals = criteria_lookup.get(tag)
        if vals is None:
            continue
        d1, d2, k3, tpi = vals
        txt = (f"$\\delta_1 = {d1:.3f}$\n"
               f"$\\delta_2 = {d2:.3f}$\n"
               f"$K_{{\\rm core}} = {k3:.0f}$ keV cm$^2$\n"
               f"TPI $= {tpi:+.2f}$")
        ax.text(0.04, 0.27, txt,
                transform=ax.transAxes,
                ha="left", va="top", fontsize=9,
                color="white",
                bbox=dict(boxstyle="round,pad=0.3",
                          facecolor="black", alpha=0.55,
                          edgecolor="none"))


# ── main loop ─────────────────────────────────────────────────────────────────
for group_name, fname in FILE_MAP.items():
    hdf5_path = os.path.join(PARTICLE_DIR, fname)
    out_dir   = os.path.join(OUTPUT_ROOT, group_name)
    out_file  = os.path.join(out_dir, "multifield_4field_random6_massive.png")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  {group_name}  →  {os.path.basename(out_file)}")

    data = oc.open(hdf5_path)

    # collect (fof_halo_mass, unique_tag) for all halos in this file
    halo_info = []
    for halo in data.halos():
        props = halo["halo_properties"]
        tag   = int(props["unique_tag"])
        m     = props["fof_halo_mass"]
        mass  = float(m.value) if hasattr(m, "value") else float(m)
        halo_info.append((mass, tag))

    # sort descending by mass, take top N_HALOS
    halo_info.sort(key=lambda x: x[0], reverse=True)
    chosen_info = halo_info[:N_HALOS]
    chosen = [tag  for _, tag in chosen_info]
    masses = [mass for mass, _  in chosen_info]

    print(f"  Top-{N_HALOS} tags:          {chosen}")
    print(f"  FoF masses (Msun/h): {[f'{m:.3e}' for m in masses]}")

    halo_ids = np.column_stack([chosen] * len(FIELDS))
    params = {
        "fields": (FIELDS,) * N_HALOS,
        "labels": (LABELS,) * N_HALOS,
        "cmaps":  (CMAPS,)  * N_HALOS,
    }

    try:
        fig = halo_projection_array(halo_ids, data, params=params,
                                    length_scale="all left")
        annotate_stars_panels(fig, chosen, criteria_lookup)
        fig.suptitle(
            f"{group_name}  —  6 most massive halos: DM | Stars | Gas | Gas Temp",
            fontsize=13, y=1.005
        )
        fig.savefig(out_file, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved: {out_file}")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback; traceback.print_exc()

print("\nAll done.")
