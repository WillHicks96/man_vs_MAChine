#!/usr/bin/env python3
"""
Shortlist of 30 extreme halos per group:
  R1       — 30 most relaxed by δ1 (smallest delta_1)
  R1_andR2 — 30 most relaxed by δ2 (smallest delta_2, within R1)
  R1_andR3 — 30 most relaxed by δ3 (smallest K_core,  within R1)
  R1_andR4 — 30 most relaxed by δ4 (highest TPI,      within R1)
  R1_notR2 — 30 most unrelaxed by δ2 (largest delta_2, within R1)
  R1_notR3 — 30 most unrelaxed by δ3 (largest K_core,  within R1)
  R1_notR4 — 30 most unrelaxed by δ4 (most negative TPI, within R1)
"""
import os
import numpy as np
import h5py

EXPERIMENT_DIR = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/runs/research_20260218_105441"
CATALOG = "/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5"
OUT_FILE = os.path.join(EXPERIMENT_DIR, "halo_shortlist_30.txt")
N_SELECT = 30

# ── load ───────────────────────────────────────────────────────────────────────
print("Loading catalog…")
with h5py.File(CATALOG, "r") as f:
    props = f["halo_properties/data"]
    fof_mass      = np.array(props["fof_halo_mass"])
    r500c         = np.array(props["sod_halo_R500c"])
    r200m         = np.array(props["sod_halo_R200m"])
    t500c         = np.array(props["sod_halo_T500c"])
    t500c_bolo_ex = np.array(props["sod_halo_T500cBoloEx"])
    core_ne       = np.array(props["sod_halo_core_ne"])
    core_entropy  = np.array(props["sod_halo_core_entropy"])
    unique_tag    = np.array(props["unique_tag"])
    fof_tag       = np.array(props["fof_halo_tag"])
    fof_cx  = np.array(props["fof_halo_center_x"]);  fof_cy  = np.array(props["fof_halo_center_y"])
    fof_cz  = np.array(props["fof_halo_center_z"]);  fof_cx2 = np.array(props["fof_halo_com_x"])
    fof_cy2 = np.array(props["fof_halo_com_y"]);     fof_cz2 = np.array(props["fof_halo_com_z"])
    sod_dm_x  = np.array(props["sod_halo_com_x_dm"]); sod_dm_y  = np.array(props["sod_halo_com_y_dm"])
    sod_dm_z  = np.array(props["sod_halo_com_z_dm"]); sod_gas_x = np.array(props["sod_halo_com_x_gas"])
    sod_gas_y = np.array(props["sod_halo_com_y_gas"]); sod_gas_z = np.array(props["sod_halo_com_z_gas"])

logM = np.log10(fof_mass)

# ── criteria (identical to phase6) ────────────────────────────────────────────
d1_abs  = np.sqrt((fof_cx2-fof_cx)**2 + (fof_cy2-fof_cy)**2 + (fof_cz2-fof_cz)**2)
delta_1 = np.where(r200m > 0, d1_abs / r200m, np.nan)

d2_abs  = np.sqrt((sod_dm_x-sod_gas_x)**2 + (sod_dm_y-sod_gas_y)**2 + (sod_dm_z-sod_gas_z)**2)
delta_2 = np.where(r500c > 0, d2_abs / r500c, np.nan)

delta_3 = core_entropy

T_ratio = np.where((t500c > 0) & (t500c_bolo_ex > 0), t500c_bolo_ex / t500c, np.nan)

def robust_zscore(arr):
    finite = np.isfinite(arr)
    vals = arr[finite]
    if vals.size == 0:
        return np.full_like(arr, np.nan)
    med = np.median(vals)
    mad = np.median(np.abs(vals - med))
    if mad < 1e-30:
        mad = np.std(vals) + 1e-30
    return (arr - med) / (1.4826 * mad)

log_ne     = np.where(core_ne > 0, np.log(core_ne), np.nan)
log_Tratio = np.where(T_ratio > 0, np.log(T_ratio), np.nan)
TPI        = robust_zscore(log_ne) + robust_zscore(log_Tratio)

# ── masks ──────────────────────────────────────────────────────────────────────
THR_D1, THR_D2, THR_KE, THR_TPI = 0.07, 0.07, 150.0, 0.0

valid = (np.isfinite(delta_1) & np.isfinite(delta_2) & np.isfinite(delta_3) &
         (delta_1 > 0) & (delta_2 > 0) & (delta_3 > 0) &
         np.isfinite(TPI) & (logM >= 13.5))

R1       = valid & (delta_1 < THR_D1)
R1_andR2 = R1 & (delta_2 < THR_D2)
R1_notR2 = R1 & (delta_2 >= THR_D2)
R1_andR3 = R1 & (delta_3 < THR_KE)
R1_notR3 = R1 & (delta_3 >= THR_KE)
R1_andR4 = R1 & (TPI > THR_TPI)
R1_notR4 = R1 & (TPI <= THR_TPI)

# ── helper: pick top N by sort key ────────────────────────────────────────────
def select_extreme(mask, sort_arr, n=N_SELECT, ascending=True):
    """Return indices of the n most extreme halos within mask, sorted by sort_arr."""
    idx = np.where(mask)[0]
    vals = sort_arr[idx]
    finite = np.isfinite(vals)
    idx, vals = idx[finite], vals[finite]
    order = np.argsort(vals) if ascending else np.argsort(vals)[::-1]
    return idx[order[:n]]

# ── group definitions ──────────────────────────────────────────────────────────
#  (name, mask, sort_array, ascending, sort_label, extreme_label)
groups = [
    ("R1",       R1,       delta_1, True,  "delta_1",  "smallest delta_1 (most DM-relaxed)"),
    ("R1_andR2", R1_andR2, delta_2, True,  "delta_2",  "smallest delta_2 (most gas-coherent within R1)"),
    ("R1_andR3", R1_andR3, delta_3, True,  "K_core",   "smallest K_core (most cool-core within R1)"),
    ("R1_andR4", R1_andR4, TPI,     False, "TPI",      "highest TPI (strongest TPI cool-core within R1)"),
    ("R1_notR2", R1_notR2, delta_2, False, "delta_2",  "largest delta_2 (most gas-displaced within R1)"),
    ("R1_notR3", R1_notR3, delta_3, False, "K_core",   "largest K_core (most heated core within R1)"),
    ("R1_notR4", R1_notR4, TPI,     True,  "TPI",      "most negative TPI (most non-cool-core by TPI, within R1)"),
]

# ── write ──────────────────────────────────────────────────────────────────────
with open(OUT_FILE, "w") as out:
    out.write("# Shortlist: 30 extreme halos per group\n")
    out.write("# Catalog: filtered_haloproperties.hdf5  (run_id 5ee0c456)\n")
    out.write("# Thresholds: delta1<0.07, delta2<0.07, K_core<150 keV cm2, TPI>0\n")
    out.write(f"# N per group: {N_SELECT}\n")
    out.write("#\n")

    for name, mask, sort_arr, ascending, sort_col, extreme_desc in groups:
        sel = select_extreme(mask, sort_arr, N_SELECT, ascending)
        # sort output rows by the sort criterion for readability
        vals = sort_arr[sel]
        order = np.argsort(vals) if ascending else np.argsort(vals)[::-1]
        sel = sel[order]

        out.write(f"\n# ── {name}  ({N_SELECT} halos) ──────────────────────────────\n")
        out.write(f"# Selection: {extreme_desc}\n")
        out.write(f"# {'rank':>4}  {'row_idx':>8}  {'unique_tag':>14}  {'fof_tag':>14}"
                  f"  {'delta_1':>8}  {'delta_2':>8}  {'K_core':>9}  {'TPI':>8}\n")
        for rank, i in enumerate(sel, 1):
            out.write(f"  {rank:>4d}  {i:>8d}  {unique_tag[i]:>14d}  {fof_tag[i]:>14d}"
                      f"  {delta_1[i]:>8.5f}  {delta_2[i]:>8.5f}"
                      f"  {delta_3[i]:>9.3f}  {TPI[i]:>8.4f}\n")
        print(f"  {name:12s}  {extreme_desc}")

print(f"\nDone. Shortlist written to:\n  {OUT_FILE}")
