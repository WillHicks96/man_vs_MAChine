#!/usr/bin/env python3
"""
Comprehensive stacked profile analysis — ALL valid halos, no R1 conditioning.

Mirrors phase6_stacked_profiles_comprehensive.png but replaces the secondary
criteria columns (originally conditioned on R1) with the same criteria applied
to the FULL valid population:

  Col 0: R1 vs ~R1  (DM relaxation, baseline — same as original)
  Col 1: R2 vs ~R2  (gas–DM centroid offset, ALL valid halos)
  Col 2: R3 vs ~R3  (core entropy K_core, ALL valid halos)
  Col 3: R4 vs ~R4  (Thermal Profile Indicator TPI, ALL valid halos)

Output: phase6_stacked_profiles_comprehensive_allR.png
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import h5py

PROJECT_ROOT   = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments"
EXPERIMENT_DIR = os.path.join(PROJECT_ROOT, "runs", "research_20260218_105441")
CATALOG = "/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5"
np.random.seed(42)

# ── load catalog + profiles ────────────────────────────────────────────────────
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
    fof_cx  = np.array(props["fof_halo_center_x"]);  fof_cy  = np.array(props["fof_halo_center_y"])
    fof_cz  = np.array(props["fof_halo_center_z"]);  fof_cx2 = np.array(props["fof_halo_com_x"])
    fof_cy2 = np.array(props["fof_halo_com_y"]);     fof_cz2 = np.array(props["fof_halo_com_z"])
    sod_dm_x  = np.array(props["sod_halo_com_x_dm"]); sod_dm_y  = np.array(props["sod_halo_com_y_dm"])
    sod_dm_z  = np.array(props["sod_halo_com_z_dm"]); sod_gas_x = np.array(props["sod_halo_com_x_gas"])
    sod_gas_y = np.array(props["sod_halo_com_y_gas"]); sod_gas_z = np.array(props["sod_halo_com_z_gas"])
    # profiles
    pdata        = f["halo_profiles/data"]
    radius       = np.array(pdata["sod_halo_bin_radius"])
    bin_mass     = np.array(pdata["sod_halo_bin_mass"])
    gas_ne       = np.array(pdata["sod_halo_bin_gas_ne"])
    gas_entropy  = np.array(pdata["sod_halo_bin_gas_entropy"])
    gas_pthermal = np.array(pdata["sod_halo_bin_gas_pthermal"])
    xray_lumin   = np.array(pdata["sod_halo_bin_hot_gas_lumin_bolo"])
    prof_idx     = np.array(f["halo_properties/data_linked"]["sod_profile_idx"])

N = len(fof_mass)
logM = np.log10(fof_mass)
print(f"  Loaded {N:,} halos")

# ── derived quantities ─────────────────────────────────────────────────────────
d1_abs  = np.sqrt((fof_cx2-fof_cx)**2 + (fof_cy2-fof_cy)**2 + (fof_cz2-fof_cz)**2)
delta_1 = np.where(r200m > 0, d1_abs / r200m, np.nan)

d2_abs  = np.sqrt((sod_dm_x-sod_gas_x)**2 + (sod_dm_y-sod_gas_y)**2 + (sod_dm_z-sod_gas_z)**2)
delta_2 = np.where(r500c > 0, d2_abs / r500c, np.nan)

delta_3 = core_entropy

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
TPI = robust_zscore(log_ne) + robust_zscore(log_Tratio)

# ── classification masks ───────────────────────────────────────────────────────
THR_D1, THR_D2, THR_KE, THR_TPI = 0.07, 0.07, 150.0, 0.0

valid = (np.isfinite(delta_1) & np.isfinite(delta_2) & np.isfinite(delta_3) &
         (delta_1 > 0) & (delta_2 > 0) & (delta_3 > 0) &
         np.isfinite(TPI) & (logM >= 13.5))

R1 = valid & (delta_1 < THR_D1);  notR1 = valid & (delta_1 >= THR_D1)
R2 = valid & (delta_2 < THR_D2);  notR2 = valid & (delta_2 >= THR_D2)
R3 = valid & (delta_3 < THR_KE);  notR3 = valid & (delta_3 >= THR_KE)
R4 = valid & (TPI > THR_TPI);     notR4 = valid & (TPI <= THR_TPI)

print(f"  valid={valid.sum():,}  R1={R1.sum():,}  notR1={notR1.sum():,}")
print(f"  R2={R2.sum():,}  notR2={notR2.sum():,}")
print(f"  R3={R3.sum():,}  notR3={notR3.sum():,}")
print(f"  R4={R4.sum():,}  notR4={notR4.sum():,}")

# ── profile interpolation ──────────────────────────────────────────────────────
r_grid = np.logspace(np.log10(0.015), np.log10(2.5), 90)

def interp_profiles(halo_indices, data_arr, r500c_arr, prof_idx_arr, radius_arr,
                    r_grid, n_halo_max=500):
    """Interpolate profiles onto r_grid; return median + 16th/84th percentiles."""
    idx = np.array(halo_indices, dtype=int)
    np.random.shuffle(idx)
    sel = idx[:n_halo_max]
    stacked = []
    for i in sel:
        pi = prof_idx_arr[i]
        r  = radius_arr[pi]
        if r500c_arr[i] <= 0:
            continue
        r_n  = r / r500c_arr[i]
        yp   = data_arr[pi]
        vmask = (yp > 0) & (r_n > 0)
        if vmask.sum() < 5:
            continue
        try:
            interp = np.interp(r_grid, r_n[vmask], yp[vmask],
                               left=np.nan, right=np.nan)
            stacked.append(interp)
        except Exception:
            pass
    if len(stacked) == 0:
        return (np.full_like(r_grid, np.nan),
                np.full_like(r_grid, np.nan),
                np.full_like(r_grid, np.nan))
    arr = np.array(stacked)
    return (np.nanmedian(arr, axis=0),
            np.nanpercentile(arr, 16, axis=0),
            np.nanpercentile(arr, 84, axis=0))

# ── 5 profile types ────────────────────────────────────────────────────────────
profile_defs = [
    (bin_mass,     r"$M(<r)\,[M_\odot\,h^{-1}]$",                    "Enclosed Mass",        True),
    (gas_ne,       r"$n_e\,[\mathrm{cm}^{-3}]$",                      "Gas Electron Density", True),
    (gas_entropy,  r"$K\,[\mathrm{keV\,cm}^2]$",                      "Gas Entropy",          True),
    (gas_pthermal, r"$P_\mathrm{th}\,[\mathrm{keV\,cm}^{-3}]$",       "Thermal Pressure",     True),
    (xray_lumin,   r"$L_X\,[\mathrm{erg\,s}^{-1}]$",                  "X-ray Luminosity",     True),
]

# ── precompute R1 / ~R1 reference profiles ────────────────────────────────────
print("\nPrecomputing R1 and ~R1 reference profiles…")
ref = {}
for pi, (parr, ylabel, ptitle, ulog) in enumerate(profile_defs):
    med_R1,   p16_R1,  p84_R1  = interp_profiles(np.where(R1)[0],    parr, r500c, prof_idx, radius, r_grid, 500)
    med_nR1,  p16_nR1, p84_nR1 = interp_profiles(np.where(notR1)[0], parr, r500c, prof_idx, radius, r_grid, 500)
    ref[pi] = (med_R1, p16_R1, p84_R1, med_nR1, p16_nR1, p84_nR1)
    print(f"  {ptitle}: R1 N={R1.sum():,}, ~R1 N={notR1.sum():,}")

# ── figure layout ──────────────────────────────────────────────────────────────
zones = [
    (0.015, 0.15, '#FFFDE7', 'Core',      0.05,  0.97, 7.5),
    (0.15,  0.5,  '#E3F2FD', 'Inner',     0.28,  0.97, 7.5),
    (0.5,   1.0,  '#F3E5F5', 'Body',      0.70,  0.97, 7.5),
    (1.0,   2.5,  '#FFFFFF', 'Outskirts', 1.65,  0.97, 7.5),
]
zone_lines = [0.15, 0.5, 1.0]

zone_physics = {
    'Core':      "AGN feedback\ncooling / BCG",
    'Inner':     "Gas sloshing\nfeedback bubbles",
    'Body':      "Merger turbulence\nbulk flows",
    'Outskirts': "Infall filaments\ngas clumping",
}

# Column definitions — ALL using full valid population
col_defs = [
    # (mask_A, mask_B, color_A, color_B, label_A, label_B, col_title, show_ref)
    (R1, notR1,
     '#1A3A7C', '#8B0000',
     r"$\delta_1 < 0.07$ (DM relaxed)", r"$\delta_1 \geq 0.07$ (DM disturbed)",
     r"$\delta_1$: DM Relaxation" + "\n(all valid halos)", False),
    (R2, notR2,
     '#005F5F', '#CC4400',
     r"R2: gas–DM aligned ($\delta_2 < 0.07$)", r"$\neg$R2: DM–gas offset ($\delta_2 \geq 0.07$)",
     r"$\delta_2$: Gas–DM Centroid Offset" + "\n(all valid halos, no R1 condition)", True),
    (R3, notR3,
     '#1B6B1B', '#6A0DAD',
     r"R3: cool core ($K < 150$)", r"$\neg$R3: non-CC ($K \geq 150$)",
     r"$\delta_3$: Core Entropy $K_\mathrm{core}$" + "\n(all valid halos, no R1 condition)", True),
    (R4, notR4,
     '#1565C0', '#B71C1C',
     r"R4: high TPI (cool core)", r"$\neg$R4: low TPI (non-CC)",
     r"$\delta_4$: Thermal Profile Indicator" + "\n(all valid halos, no R1 condition)", True),
]

print("\nBuilding figure: comprehensive stacked profiles — all-R (5×4)…")

fig, axes = plt.subplots(5, 4, figsize=(24, 20), sharex=True, sharey='row')
fig.suptitle(
    r"Stacked Median Radial Profiles — Each Criterion Applied to ALL Valid Halos (No R1 Pre-selection)"
    + "\n" + r"(Col 1 = baseline $\delta_1$; Cols 2–4 = $\delta_2, \delta_3, \delta_4$ on the full sample;"
    + " dashed context lines = R1 / $\neg$R1 medians)",
    fontsize=11.0, y=1.005)

for row_i, (parr, ylabel, ptitle, ulog) in enumerate(profile_defs):
    med_R1, p16_R1, p84_R1, med_nR1, p16_nR1, p84_nR1 = ref[row_i]

    for col_i, (mA, mB, colA, colB, labA, labB, col_title, show_ref) in enumerate(col_defs):
        ax = axes[row_i, col_i]

        # Background zone shading
        for (r_lo, r_hi, fc, zlbl, zx, zy, zfs) in zones:
            ax.axvspan(r_lo, r_hi, alpha=0.18, color=fc, zorder=0)
        for rl in zone_lines:
            ax.axvline(rl, color='#AAAAAA', ls=':', lw=0.8, alpha=0.7, zorder=1)

        # Reference lines: R1 and ~R1 as context in cols 1–3
        if show_ref:
            vm_nR1 = np.isfinite(med_nR1) & (med_nR1 > 0)
            if vm_nR1.sum() > 3:
                ax.plot(r_grid[vm_nR1], med_nR1[vm_nR1],
                        color='#AAAAAA', lw=1.1, ls='-', alpha=0.7, zorder=2,
                        label=r'$\neg$R1 context' if row_i == 0 else '')
            vm_R1 = np.isfinite(med_R1) & (med_R1 > 0)
            if vm_R1.sum() > 3:
                ax.plot(r_grid[vm_R1], med_R1[vm_R1],
                        color='#4682B4', lw=1.1, ls='--', alpha=0.8, zorder=2,
                        label='R1 context' if row_i == 0 else '')

        # Compute and plot mask A (solid thick) and B (dashed thick)
        medA, p16A, p84A = interp_profiles(np.where(mA)[0], parr, r500c, prof_idx, radius, r_grid, 500)
        medB, p16B, p84B = interp_profiles(np.where(mB)[0], parr, r500c, prof_idx, radius, r_grid, 500)

        vmA = np.isfinite(medA) & (medA > 0)
        vmB = np.isfinite(medB) & (medB > 0)

        if vmA.sum() > 3:
            ax.plot(r_grid[vmA], medA[vmA], color=colA, lw=2.5, ls='-', zorder=4,
                    label=labA if row_i == 0 else '')
            if not show_ref:
                ax.fill_between(r_grid[vmA], p16A[vmA], p84A[vmA],
                                color=colA, alpha=0.13, zorder=3)

        if vmB.sum() > 3:
            ax.plot(r_grid[vmB], medB[vmB], color=colB, lw=2.5, ls='--', zorder=4,
                    label=labB if row_i == 0 else '')
            if not show_ref:
                ax.fill_between(r_grid[vmB], p16B[vmB], p84B[vmB],
                                color=colB, alpha=0.13, zorder=3)

        ax.set_xscale('log')
        if ulog:
            ax.set_yscale('log')
        ax.grid(True, alpha=0.15, lw=0.4)
        ax.tick_params(labelsize=8)

        if col_i == 0:
            ax.set_ylabel(ylabel, fontsize=9)
        if row_i == 4:
            ax.set_xlabel(r'$r / R_{500c}$', fontsize=9.5)
        if row_i == 0:
            ax.set_title(col_title, fontsize=9, fontweight='bold', pad=7)
            for (r_lo, r_hi, fc, zlbl, zx, zy, zfs) in zones:
                r_mid = np.sqrt(r_lo * r_hi)
                ax.text(r_mid, 0.97, zlbl + "\n" + zone_physics[zlbl],
                        transform=ax.get_xaxis_transform(),
                        fontsize=6, ha='center', va='top', color='#444444',
                        bbox=dict(facecolor=fc, alpha=0.5, edgecolor='none', pad=1))
        if row_i == 0:
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                ax.legend(handles=handles, labels=labels,
                          fontsize=6.5, loc='lower right', framealpha=0.85,
                          ncol=1, handlelength=1.5, handletextpad=0.4)
        # N counts in bottom-left of last row
        if row_i == 4:
            nA = mA.sum(); nB = mB.sum()
            ax.text(0.03, 0.97, f"N={nA:,} / {nB:,}",
                    transform=ax.transAxes, fontsize=7, va='top', color='#333333')

plt.tight_layout(h_pad=0.5, w_pad=0.4)
out_path = os.path.join(EXPERIMENT_DIR, "phase6_stacked_profiles_comprehensive_allR.png")
fig.savefig(out_path, dpi=150, bbox_inches='tight')
plt.close(fig)
print(f"\nSaved: {out_path}")
print("Done.")
