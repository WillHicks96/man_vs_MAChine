#!/usr/bin/env python3
"""
Export halo identifiers for each relaxation sub-group used in
phase6_stacked_profiles_comprehensive.png (columns 2, 3, 4).

Groups exported (all within DM-relaxed R1):
  R1          — all DM-relaxed halos (δ1 < 0.07)
  R1_andR2    — R1 ∩ R2  (δ2 < 0.07,  gas-coherent)
  R1_notR2    — R1 ∩ ~R2 (δ2 >= 0.07, gas-displaced)
  R1_andR3    — R1 ∩ R3  (K_core < 150 keV cm², cool-core by entropy)
  R1_notR3    — R1 ∩ ~R3 (K_core >= 150 keV cm², non-cool-core)
  R1_andR4    — R1 ∩ R4  (TPI > 0, cool-core by TPI)
  R1_notR4    — R1 ∩ ~R4 (TPI <= 0, non-cool-core by TPI)

Identifiers saved:
  unique_tag  — simulation-unique halo tag (primary identifier)
  fof_halo_tag — FoF halo tag
  row_index   — 0-based row index in the HDF5 catalog (for direct slicing)
"""
import os
import numpy as np
import h5py

EXPERIMENT_DIR = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/runs/research_20260218_105441"
CATALOG = "/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5"
OUT_FILE = os.path.join(EXPERIMENT_DIR, "halo_group_ids.txt")

# ── load required columns ──────────────────────────────────────────────────────
print("Loading catalog…")
with h5py.File(CATALOG, "r") as f:
    props = f["halo_properties/data"]
    fof_mass      = np.array(props["fof_halo_mass"])
    m500c         = np.array(props["sod_halo_M500c"])
    r500c         = np.array(props["sod_halo_R500c"])
    r200m         = np.array(props["sod_halo_R200m"])
    t500c         = np.array(props["sod_halo_T500c"])
    t500c_bolo_ex = np.array(props["sod_halo_T500cBoloEx"])
    core_ne       = np.array(props["sod_halo_core_ne"])
    core_entropy  = np.array(props["sod_halo_core_entropy"])
    # Identifiers
    unique_tag    = np.array(props["unique_tag"])
    fof_tag       = np.array(props["fof_halo_tag"])
    # COM vectors for δ1, δ2
    fof_cx  = np.array(props["fof_halo_center_x"])
    fof_cy  = np.array(props["fof_halo_center_y"])
    fof_cz  = np.array(props["fof_halo_center_z"])
    fof_cx2 = np.array(props["fof_halo_com_x"])
    fof_cy2 = np.array(props["fof_halo_com_y"])
    fof_cz2 = np.array(props["fof_halo_com_z"])
    sod_dm_x  = np.array(props["sod_halo_com_x_dm"])
    sod_dm_y  = np.array(props["sod_halo_com_y_dm"])
    sod_dm_z  = np.array(props["sod_halo_com_z_dm"])
    sod_gas_x = np.array(props["sod_halo_com_x_gas"])
    sod_gas_y = np.array(props["sod_halo_com_y_gas"])
    sod_gas_z = np.array(props["sod_halo_com_z_gas"])

N = len(fof_mass)
print(f"  Loaded {N:,} halos")

# ── compute criteria (identical to phase6_code.py) ────────────────────────────
logM    = np.log10(fof_mass)

d1_abs  = np.sqrt((fof_cx2-fof_cx)**2 + (fof_cy2-fof_cy)**2 + (fof_cz2-fof_cz)**2)
delta_1 = np.where(r200m > 0, d1_abs / r200m, np.nan)

d2_abs  = np.sqrt((sod_dm_x-sod_gas_x)**2 + (sod_dm_y-sod_gas_y)**2 + (sod_dm_z-sod_gas_z)**2)
delta_2 = np.where(r500c > 0, d2_abs / r500c, np.nan)

delta_3 = core_entropy   # [keV cm²]

T_ratio = np.where((t500c > 0) & (t500c_bolo_ex > 0),
                   t500c_bolo_ex / t500c, np.nan)

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

log_ne     = np.where(core_ne > 0,  np.log(core_ne),  np.nan)
log_Tratio = np.where(T_ratio > 0, np.log(T_ratio), np.nan)
TPI        = robust_zscore(log_ne) + robust_zscore(log_Tratio)

# ── classification masks ───────────────────────────────────────────────────────
THR_D1  = 0.07
THR_D2  = 0.07
THR_KE  = 150.0
THR_TPI = 0.0

valid = (np.isfinite(delta_1) & np.isfinite(delta_2) & np.isfinite(delta_3) &
         (delta_1 > 0) & (delta_2 > 0) & (delta_3 > 0) &
         np.isfinite(TPI) & (logM >= 13.5))

R1       = valid & (delta_1 < THR_D1)
R1_andR2 = R1    & (delta_2 < THR_D2)
R1_notR2 = R1    & (delta_2 >= THR_D2)
R1_andR3 = R1    & (delta_3 < THR_KE)
R1_notR3 = R1    & (delta_3 >= THR_KE)
R1_andR4 = R1    & (TPI > THR_TPI)
R1_notR4 = R1    & (TPI <= THR_TPI)

groups = [
    ("R1",       R1,       "All DM-relaxed halos (delta1 < 0.07)"),
    ("R1_andR2", R1_andR2, "R1 AND R2: DM-relaxed, gas-coherent (delta2 < 0.07)"),
    ("R1_notR2", R1_notR2, "R1 AND NOT R2: DM-relaxed, gas-displaced (delta2 >= 0.07)"),
    ("R1_andR3", R1_andR3, "R1 AND R3: DM-relaxed, cool-core by K_core (K_core < 150 keV cm2)"),
    ("R1_notR3", R1_notR3, "R1 AND NOT R3: DM-relaxed, non-cool-core (K_core >= 150 keV cm2)"),
    ("R1_andR4", R1_andR4, "R1 AND R4: DM-relaxed, cool-core by TPI (TPI > 0)"),
    ("R1_notR4", R1_notR4, "R1 AND NOT R4: DM-relaxed, not TPI cool-core (TPI <= 0)"),
]

# ── write output ───────────────────────────────────────────────────────────────
row_idx = np.arange(N, dtype=int)

with open(OUT_FILE, "w") as out:
    out.write("# Halo group IDs for phase6_stacked_profiles_comprehensive.png\n")
    out.write("# Catalog: filtered_haloproperties.hdf5  (run_id 5ee0c456)\n")
    out.write("# Thresholds: delta1<0.07 (R1), delta2<0.07 (R2),\n")
    out.write("#             K_core<150 keV cm2 (R3), TPI>0 (R4)\n")
    out.write("# Columns: row_index  fof_halo_tag  unique_tag  delta1  delta2  K_core  TPI\n")
    out.write("#\n")

    for name, mask, desc in groups:
        n = mask.sum()
        out.write(f"\n# ── {name}  ({n:,} halos) ──────────────────────────────\n")
        out.write(f"# Description: {desc}\n")
        out.write(f"# N = {n:,}\n")
        out.write(f"# {'row_index':>10}  {'fof_halo_tag':>14}  {'unique_tag':>14}"
                  f"  {'delta1':>9}  {'delta2':>9}  {'K_core':>10}  {'TPI':>9}\n")

        idx = np.where(mask)[0]
        for i in idx:
            out.write(f"  {i:>10d}  {fof_tag[i]:>14d}  {unique_tag[i]:>14d}"
                      f"  {delta_1[i]:>9.5f}  {delta_2[i]:>9.5f}"
                      f"  {delta_3[i]:>10.3f}  {TPI[i]:>9.4f}\n")

        print(f"  {name:12s}  N={n:5,}  (written)")

print(f"\nDone. IDs written to:\n  {OUT_FILE}")
