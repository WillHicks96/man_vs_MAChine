#!/usr/bin/env python3
"""
Full shortlist of 30 extreme halos per group — 32 groups total.

INDIVIDUAL CRITERIA (8 groups):
  R1    — 30 most DM-relaxed         (smallest delta_1 within valid)
  notR1 — 30 most DM-disturbed       (largest  delta_1 within valid)
  R2    — 30 most gas-coherent       (smallest delta_2 within valid)
  notR2 — 30 most gas-displaced      (largest  delta_2 within valid)
  R3    — 30 strongest cool-core K   (smallest K_core  within valid)
  notR3 — 30 most non-cool-core K    (largest  K_core  within valid)
  R4    — 30 highest TPI cool-core   (highest  TPI     within valid)
  notR4 — 30 lowest TPI             (lowest   TPI     within valid)

PAIRWISE CRITERIA (24 groups = 6 pairs × 4 sign combinations):
  Pairs: {R1,R2}, {R1,R3}, {R1,R4}, {R2,R3}, {R2,R4}, {R3,R4}
  For each pair {Ri, Rj}: Ri_andRj, Ri_notRj, notRi_andRj, notRi_notRj
  Sorting: for Ri_andRj / Ri_notRj → sort by Rj criterion
           for notRi_andRj          → sort by Rj criterion
           for notRi_notRj          → sort by Ri criterion (most extreme notRi)

Identifiers per halo: row_index, unique_tag, fof_halo_tag,
                       delta_1, delta_2, K_core, TPI
"""
import os
import numpy as np
import h5py

EXPERIMENT_DIR = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/runs/research_20260218_105441"
CATALOG = "/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5"
OUT_FILE = os.path.join(EXPERIMENT_DIR, "halo_shortlist_30_fullR.txt")
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

delta_3 = core_entropy  # [keV cm²]

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

R1 = valid & (delta_1 < THR_D1);   nR1 = valid & (delta_1 >= THR_D1)
R2 = valid & (delta_2 < THR_D2);   nR2 = valid & (delta_2 >= THR_D2)
R3 = valid & (delta_3 < THR_KE);   nR3 = valid & (delta_3 >= THR_KE)
R4 = valid & (TPI > THR_TPI);      nR4 = valid & (TPI <= THR_TPI)

print(f"  valid={valid.sum():,}  R1={R1.sum():,}  notR1={nR1.sum():,}")
print(f"  R2={R2.sum():,}  notR2={nR2.sum():,}")
print(f"  R3={R3.sum():,}  notR3={nR3.sum():,}")
print(f"  R4={R4.sum():,}  notR4={nR4.sum():,}")

# ── helper: pick top N by sort key ────────────────────────────────────────────
def select_extreme(mask, sort_arr, n=N_SELECT, ascending=True):
    """Return indices of the n most extreme halos within mask."""
    idx = np.where(mask)[0]
    vals = sort_arr[idx]
    finite = np.isfinite(vals)
    idx, vals = idx[finite], vals[finite]
    order = np.argsort(vals) if ascending else np.argsort(vals)[::-1]
    return idx[order[:n]]

# ── group definitions ──────────────────────────────────────────────────────────
# (name, mask, sort_array, ascending, description)
groups = [
    # ── Individual criteria ────────────────────────────────────────────────
    ("R1",    R1,  delta_1, True,  "DM-relaxed (delta1 < 0.07); sorted by smallest delta_1"),
    ("notR1", nR1, delta_1, False, "DM-disturbed (delta1 >= 0.07); sorted by largest delta_1"),
    ("R2",    R2,  delta_2, True,  "Gas-coherent (delta2 < 0.07); sorted by smallest delta_2"),
    ("notR2", nR2, delta_2, False, "Gas-displaced (delta2 >= 0.07); sorted by largest delta_2"),
    ("R3",    R3,  delta_3, True,  "Cool-core by entropy (K_core < 150); sorted by smallest K_core"),
    ("notR3", nR3, delta_3, False, "Non-cool-core by entropy (K_core >= 150); sorted by largest K_core"),
    ("R4",    R4,  TPI,     False, "Cool-core by TPI (TPI > 0); sorted by highest TPI"),
    ("notR4", nR4, TPI,     True,  "Non-cool-core by TPI (TPI <= 0); sorted by lowest TPI"),

    # ── Pairwise: {R1, R2} ─────────────────────────────────────────────────
    ("R1_andR2",    R1 & R2,   delta_2, True,  "R1 AND R2: DM-relaxed + gas-coherent; sorted by smallest delta_2"),
    ("R1_notR2",    R1 & nR2,  delta_2, False, "R1 AND NOT R2: DM-relaxed + gas-displaced; sorted by largest delta_2"),
    ("notR1_andR2", nR1 & R2,  delta_2, True,  "NOT R1 AND R2: DM-disturbed + gas-coherent; sorted by smallest delta_2"),
    ("notR1_notR2", nR1 & nR2, delta_1, False, "NOT R1 AND NOT R2: DM-disturbed + gas-displaced; sorted by largest delta_1"),

    # ── Pairwise: {R1, R3} ─────────────────────────────────────────────────
    ("R1_andR3",    R1 & R3,   delta_3, True,  "R1 AND R3: DM-relaxed + cool-core (K); sorted by smallest K_core"),
    ("R1_notR3",    R1 & nR3,  delta_3, False, "R1 AND NOT R3: DM-relaxed + non-CC (K); sorted by largest K_core"),
    ("notR1_andR3", nR1 & R3,  delta_3, True,  "NOT R1 AND R3: DM-disturbed + cool-core (K); sorted by smallest K_core"),
    ("notR1_notR3", nR1 & nR3, delta_1, False, "NOT R1 AND NOT R3: DM-disturbed + non-CC (K); sorted by largest delta_1"),

    # ── Pairwise: {R1, R4} ─────────────────────────────────────────────────
    ("R1_andR4",    R1 & R4,   TPI,     False, "R1 AND R4: DM-relaxed + TPI cool-core; sorted by highest TPI"),
    ("R1_notR4",    R1 & nR4,  TPI,     True,  "R1 AND NOT R4: DM-relaxed + TPI non-CC; sorted by lowest TPI"),
    ("notR1_andR4", nR1 & R4,  TPI,     False, "NOT R1 AND R4: DM-disturbed + TPI cool-core; sorted by highest TPI"),
    ("notR1_notR4", nR1 & nR4, delta_1, False, "NOT R1 AND NOT R4: DM-disturbed + TPI non-CC; sorted by largest delta_1"),

    # ── Pairwise: {R2, R3} ─────────────────────────────────────────────────
    ("R2_andR3",    R2 & R3,   delta_3, True,  "R2 AND R3: gas-coherent + cool-core (K); sorted by smallest K_core"),
    ("R2_notR3",    R2 & nR3,  delta_3, False, "R2 AND NOT R3: gas-coherent + non-CC (K); sorted by largest K_core"),
    ("notR2_andR3", nR2 & R3,  delta_3, True,  "NOT R2 AND R3: gas-displaced + cool-core (K); sorted by smallest K_core"),
    ("notR2_notR3", nR2 & nR3, delta_2, False, "NOT R2 AND NOT R3: gas-displaced + non-CC (K); sorted by largest delta_2"),

    # ── Pairwise: {R2, R4} ─────────────────────────────────────────────────
    ("R2_andR4",    R2 & R4,   TPI,     False, "R2 AND R4: gas-coherent + TPI cool-core; sorted by highest TPI"),
    ("R2_notR4",    R2 & nR4,  TPI,     True,  "R2 AND NOT R4: gas-coherent + TPI non-CC; sorted by lowest TPI"),
    ("notR2_andR4", nR2 & R4,  TPI,     False, "NOT R2 AND R4: gas-displaced + TPI cool-core; sorted by highest TPI"),
    ("notR2_notR4", nR2 & nR4, delta_2, False, "NOT R2 AND NOT R4: gas-displaced + TPI non-CC; sorted by largest delta_2"),

    # ── Pairwise: {R3, R4} ─────────────────────────────────────────────────
    ("R3_andR4",    R3 & R4,   TPI,     False, "R3 AND R4: cool-core by K AND TPI; sorted by highest TPI"),
    ("R3_notR4",    R3 & nR4,  TPI,     True,  "R3 AND NOT R4: K cool-core but TPI non-CC; sorted by lowest TPI"),
    ("notR3_andR4", nR3 & R4,  TPI,     False, "NOT R3 AND R4: non-CC by K but TPI cool-core; sorted by highest TPI"),
    ("notR3_notR4", nR3 & nR4, delta_3, False, "NOT R3 AND NOT R4: non-CC by K AND TPI; sorted by largest K_core"),
]

# ── write ──────────────────────────────────────────────────────────────────────
with open(OUT_FILE, "w") as out:
    out.write("# Full shortlist: 30 extreme halos per group (32 groups total)\n")
    out.write("# Catalog: filtered_haloproperties.hdf5  (run_id 5ee0c456)\n")
    out.write("# Thresholds: delta1<0.07 (R1), delta2<0.07 (R2), K_core<150 keV cm2 (R3), TPI>0 (R4)\n")
    out.write(f"# N per group: {N_SELECT}\n")
    out.write("#\n")
    out.write("# SECTION 1: Individual criteria (8 groups)\n")
    out.write("# SECTION 2: Pairwise criteria (24 groups: pairs {R1,R2},{R1,R3},{R1,R4},{R2,R3},{R2,R4},{R3,R4})\n")
    out.write("#\n")

    for name, mask, sort_arr, ascending, desc in groups:
        sel = select_extreme(mask, sort_arr, N_SELECT, ascending)
        # sort output rows by the same criterion for readability
        vals = sort_arr[sel]
        order = np.argsort(vals) if ascending else np.argsort(vals)[::-1]
        sel = sel[order]

        n_total = mask.sum()
        out.write(f"\n# ── {name}  (group size: {n_total:,}; showing {len(sel)} extreme) ─────────────────\n")
        out.write(f"# {desc}\n")
        out.write(f"# {'rank':>4}  {'row_idx':>8}  {'unique_tag':>14}  {'fof_tag':>14}"
                  f"  {'delta_1':>8}  {'delta_2':>8}  {'K_core':>9}  {'TPI':>8}\n")
        for rank, i in enumerate(sel, 1):
            out.write(f"  {rank:>4d}  {i:>8d}  {unique_tag[i]:>14d}  {fof_tag[i]:>14d}"
                      f"  {delta_1[i]:>8.5f}  {delta_2[i]:>8.5f}"
                      f"  {delta_3[i]:>9.3f}  {TPI[i]:>8.4f}\n")
        print(f"  {name:20s}  N_group={n_total:5,}  N_selected={len(sel)}")

print(f"\nDone. Full shortlist ({len(groups)} groups) written to:\n  {OUT_FILE}")
