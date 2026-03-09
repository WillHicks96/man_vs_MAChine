#!/usr/bin/env python3
"""
Phase 5: Three-criteria relaxation analysis
  δ1 = |FoF_COM - FoF_center| / R_200m        (DM COM offset, traditional)
  δ2 = |SOD_DM_COM - SOD_gas_COM| / R_500c    (DM-gas centroid separation)
  δ3 = K_core = sod_halo_core_entropy          (core entropy, keV cm²; low = cool-core)

Physics focus: What does each criterion probe?
  δ1 → DM coherent displacement from potential min; sensitive to major mergers
  δ2 → DM-gas decoupling; sensitive to gas sloshing, ram-pressure separation
  δ3 (K_core) → Core gas thermodynamics; cool-cores, AGN feedback, heating/cooling
                 Directly observable via X-ray spectroscopy (Chandra, XMM, eROSITA)

Classification thresholds:
  Relaxed by δ1: δ1 < 0.07       (Neto+2007, Bett+2007)
  Relaxed by δ2: δ2 < 0.07       (consistent threshold)
  Cool-core (relaxed by δ3): K_core < 150 keV cm²
    (Hudson+2010: strong CC < 30, weak CC 30-150, NCC > 150 keV cm²)
"""
import os, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Patch
from scipy.optimize import minimize_scalar
import h5py

# ------------------------------------------------------------------ paths ---
PROJECT_ROOT = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments"
EXPERIMENT_DIR = os.path.join(PROJECT_ROOT, "runs", "research_20260218_105441")
CATALOG = "/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5"
np.random.seed(42)

# ------------------------------------------------------------------ load ---
print("Loading catalog…")
with h5py.File(CATALOG, "r") as f:
    props = f["halo_properties/data"]
    fof_mass   = np.array(props["fof_halo_mass"])
    m500c      = np.array(props["sod_halo_M500c"])
    m200m      = np.array(props["sod_halo_M200m"])
    r500c      = np.array(props["sod_halo_R500c"])
    r200m      = np.array(props["sod_halo_R200m"])
    t500c      = np.array(props["sod_halo_T500c"])
    t500c_bolo = np.array(props["sod_halo_T500cBolo"])
    l500c_bolo = np.array(props["sod_halo_L500cBolo"])
    y500c      = np.array(props["sod_halo_Y500c"])
    cdelta     = np.array(props["sod_halo_cdelta"])
    sfr        = np.array(props["sod_halo_sfr"])
    mass_agn   = np.array(props["sod_halo_mass_agn"])
    bhr        = np.array(props["sod_halo_bhr"])
    core_tcool = np.array(props["sod_halo_core_tcool"])
    core_entropy = np.array(props["sod_halo_core_entropy"])
    gas_frac_2500 = np.array(props["sod_halo_GasFracShell2500c"])

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

    pdata = f["halo_profiles/data"]
    radius       = np.array(pdata["sod_halo_bin_radius"])
    bin_mass     = np.array(pdata["sod_halo_bin_mass"])
    gas_ne       = np.array(pdata["sod_halo_bin_gas_ne"])
    gas_entropy  = np.array(pdata["sod_halo_bin_gas_entropy"])
    gas_pthermal = np.array(pdata["sod_halo_bin_gas_pthermal"])
    xray_lumin   = np.array(pdata["sod_halo_bin_hot_gas_lumin_bolo"])

    prof_idx = np.array(f["halo_properties/data_linked"]["sod_profile_idx"])

N = len(fof_mass)
logM = np.log10(fof_mass)
print(f"  Loaded {N:,} halos")

# ------------------------------------------------------------------ δ1 and δ2 ---
d1_abs  = np.sqrt((fof_cx2-fof_cx)**2 + (fof_cy2-fof_cy)**2 + (fof_cz2-fof_cz)**2)
delta_1 = np.where(r200m > 0, d1_abs / r200m, np.nan)

d2_abs  = np.sqrt((sod_dm_x-sod_gas_x)**2 + (sod_dm_y-sod_gas_y)**2 + (sod_dm_z-sod_gas_z)**2)
delta_2 = np.where(r500c > 0, d2_abs / r500c, np.nan)

# ------------------------------------------------------------------ δ3 = core entropy (catalog) ---
# K_core = sod_halo_core_entropy [keV cm²]
# Low entropy → cool-core → thermally relaxed (low cooling time, high central density)
# High entropy → non-cool-core → heated by AGN feedback or past mergers
# Hudson+2010: strong CC < 30, weak CC 30-150, NCC > 150 keV cm²
# This is directly observable: X-ray spectroscopy within ~0.05 R500c
delta_3 = core_entropy  # low = relaxed (cool-core)

print(f"  δ3 (core entropy) percentiles [5,25,50,75,95]: "
      f"{np.nanpercentile(delta_3, [5,25,50,75,95])}")
print(f"  δ1 percentiles [5,25,50,75,95]: "
      f"{np.nanpercentile(delta_1, [5,25,50,75,95])}")
print(f"  δ2 percentiles [5,25,50,75,95]: "
      f"{np.nanpercentile(delta_2, [5,25,50,75,95])}")

# Also compute c_X as supplementary diagnostic (though dynamic range is narrow in Frontier-E)
print("\nComputing c_X (supplementary diagnostic)…")
c_X = np.full(N, np.nan)
for i in range(N):
    if r500c[i] <= 0:
        continue
    pi = prof_idx[i]
    r  = radius[pi]
    Lx = xray_lumin[pi]
    r_n = r / r500c[i]
    outer = (r_n <= 1.0) & (Lx > 0)
    inner = (r_n <= 0.15) & (Lx > 0)
    Lx_outer = Lx[outer].sum()
    Lx_inner = Lx[inner].sum()
    if Lx_outer > 0:
        c_X[i] = Lx_inner / Lx_outer
print(f"  c_X percentiles [5,25,50,75,95]: {np.nanpercentile(c_X[np.isfinite(c_X)], [5,25,50,75,95])}")

# ------------------------------------------------------------------ classification ---
THR_D1 = 0.07     # Neto+2007: FoF COM offset
THR_D2 = 0.07     # DM-gas centroid separation
THR_KE = 150.0    # keV cm² — cool-core / non-cool-core (Hudson+2010)

# Global valid mask (shape: N=10000) — DO NOT overwrite inside loops
valid = (np.isfinite(delta_1) & np.isfinite(delta_2) & np.isfinite(delta_3) &
         (delta_1 > 0) & (delta_2 > 0) & (delta_3 > 0) & (logM >= 13.5))

# Relaxed flags (True = relaxed)
R1 = valid & (delta_1 < THR_D1)        # DM COM offset: small = relaxed
R2 = valid & (delta_2 < THR_D2)        # DM-gas centroid: small = aligned = relaxed
R3 = valid & (delta_3 < THR_KE)        # Core entropy: low = cool-core = thermally relaxed

# Concordant classifications
all_R = R1 & R2 & R3           # All three agree: relaxed
all_U = valid & ~R1 & ~R2 & ~R3  # All three agree: unrelaxed

# Physically interesting discordant categories
R1R2_notR3 = R1 & R2 & ~R3    # DM relaxed (both offsets), no cool-core → AGN-heated or prior merger
R3_notR1   = R3 & ~R1         # Cool-core but DM disturbed → sloshing cool-cores!
R1_notR2   = R1 & ~R2         # DM COM aligned, but DM-gas separated → gas sloshing/minor merger

print(f"\n  Valid halos:             {valid.sum():,}")
print(f"  R3 cool-core (K<150):    {R3.sum():,} ({100*R3.sum()/valid.sum():.1f}%)")
print(f"  All relaxed (R1∩R2∩R3):  {all_R.sum():,} ({100*all_R.sum()/valid.sum():.1f}%)")
print(f"  All unrelaxed:           {all_U.sum():,} ({100*all_U.sum()/valid.sum():.1f}%)")
print(f"  R1∩R2 but no cool core:  {R1R2_notR3.sum():,} ({100*R1R2_notR3.sum()/valid.sum():.1f}%)")
print(f"  Cool-core but DM-disturbed (sloshing?): {R3_notR1.sum():,} ({100*R3_notR1.sum()/valid.sum():.1f}%)")
print(f"  DM-COM relaxed but DM-gas separated:    {R1_notR2.sum():,} ({100*R1_notR2.sum()/valid.sum():.1f}%)")

# ------------------------------------------------------------------ Figure 1: 3-way comparison ---
fig, axes = plt.subplots(1, 3, figsize=(17, 5.5))
fig.suptitle("Three Relaxation Criteria: Pairwise Comparisons (Frontier-E z=0, N=10,000)", fontsize=12)

pair_plots = [
    (delta_1, delta_2,
     r"$\delta_1$ (FoF COM offset / $R_{200m}$)",
     r"$\delta_2$ (DM–gas centroid / $R_{500c}$)",
     THR_D1, THR_D2, True, True,
     "R/R: DM & gas aligned", "R/U: DM aligned, gas offset", "U/R: DM offset, gas aligned", "U/U"),
    (delta_1, delta_3,
     r"$\delta_1$ (FoF COM offset / $R_{200m}$)",
     r"$K_\mathrm{core}$ [keV cm$^2$] (high = non-cool-core)",
     THR_D1, THR_KE, True, False,
     "DM-relaxed + CC", "DM-relaxed, no CC\n(AGN-heated?)", "DM-disturbed + CC\n(sloshing?)", "Both disturbed"),
    (delta_2, delta_3,
     r"$\delta_2$ (DM–gas centroid / $R_{500c}$)",
     r"$K_\mathrm{core}$ [keV cm$^2$] (high = non-cool-core)",
     THR_D2, THR_KE, True, False,
     "Gas-aligned + CC", "Gas-aligned, no CC", "Gas-offset + CC\n(sloshing?)", "Both disturbed"),
]

for ax, (x, y, xlabel, ylabel, xth, yth, xlog, ylog,
          lbl_q1, lbl_q2, lbl_q3, lbl_q4) in zip(axes, pair_plots):
    g = valid & np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
    sc = ax.scatter(x[g], y[g], c=logM[g], cmap="viridis",
                    s=2.5, alpha=0.25, rasterized=True)
    ax.axvline(xth, color="crimson", ls="--", lw=1.5, label=f"thr={xth:.2f}")
    ax.axhline(yth, color="steelblue", ls="--", lw=1.5, label=f"thr={yth:.0f}")
    if xlog:
        ax.set_xscale("log")
    if ylog:
        ax.set_yscale("log")
    ax.set_xlabel(xlabel, fontsize=9.5)
    ax.set_ylabel(ylabel, fontsize=9.5)
    ax.grid(True, alpha=0.2)

    Q1 = (x[g] < xth) & (y[g] < yth)
    Q2 = (x[g] >= xth) & (y[g] < yth)
    Q3 = (x[g] < xth) & (y[g] >= yth)
    Q4 = (x[g] >= xth) & (y[g] >= yth)
    ax.text(0.03, 0.97, f"{lbl_q1}\nN={Q1.sum():,}", transform=ax.transAxes, fontsize=7.5,
            va="top", color="green", fontweight="bold")
    ax.text(0.55, 0.97, f"{lbl_q2}\nN={Q2.sum():,}", transform=ax.transAxes, fontsize=7.5,
            va="top", color="darkorange")
    ax.text(0.03, 0.12, f"{lbl_q3}\nN={Q3.sum():,}", transform=ax.transAxes, fontsize=7.5,
            va="top", color="purple")
    ax.text(0.55, 0.12, f"{lbl_q4}\nN={Q4.sum():,}", transform=ax.transAxes, fontsize=7.5,
            va="top", color="firebrick")
    ax.legend(fontsize=7.5, loc="center right")

cb = plt.colorbar(sc, ax=axes[-1], shrink=0.85)
cb.set_label(r"$\log_{10} M_\mathrm{FoF}$", fontsize=9)
plt.tight_layout()
out1 = os.path.join(EXPERIMENT_DIR, "phase5_three_criteria_comparison.png")
fig.savefig(out1, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"\nSaved: {out1}")

# ------------------------------------------------------------------ Figure 2: Stacked profiles ---
print("\nBuilding stacked profiles for 4 categories…")

r_grid = np.logspace(np.log10(0.02), np.log10(2.3), 60)

def interp_profiles(halo_indices, data_arr, r500c_arr, prof_idx_arr, radius_arr,
                    r_grid, n_halo_max=300):
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
        r_n = r / r500c_arr[i]
        yp  = data_arr[pi]
        vmask = (yp > 0) & (r_n > 0)     # local mask — NOT overwriting global 'valid'
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

categories = {
    "Concordant Relaxed\n(R1∩R2∩R3)":        (np.where(all_R)[0],      "steelblue",  "-"),
    "Concordant Unrelaxed\n(¬R1∩¬R2∩¬R3)":   (np.where(all_U)[0],      "firebrick",  "-"),
    "DM Relaxed, No Cool Core\n(R1∩R2∩¬R3)": (np.where(R1R2_notR3)[0], "darkorange", "--"),
    "Cool Core, DM Disturbed\n(R3∩¬R1)":      (np.where(R3_notR1)[0],   "purple",     "-."),
}

profile_types = [
    (bin_mass,     r"Enclosed Mass $M(<r)$ [$M_\odot\,h^{-1}$]",        True),
    (gas_ne,       r"Gas Electron Density $n_e$ [cm$^{-3}$]",            True),
    (gas_entropy,  r"Gas Entropy $K$ [keV cm$^2$]",                       True),
    (gas_pthermal, r"Thermal Pressure $P_\mathrm{th}$ [keV cm$^{-3}$]",  True),
    (xray_lumin,   r"X-ray Lumin. $L_X$ [erg s$^{-1}$]",                 True),
]
profile_titles = ["Enclosed Mass", "Gas Density", "Entropy", "Thermal Pressure", "X-ray Luminosity"]

fig2, axes2 = plt.subplots(1, 5, figsize=(23, 5.5))
fig2.suptitle("Stacked Median Radial Profiles by Relaxation Classification", fontsize=12, y=1.01)

legend_handles = [Patch(color=col, linestyle=ls, label=name)
                  for name, (_, col, ls) in categories.items()]

for col_i, (prof_arr, ylabel, use_log) in enumerate(profile_types):
    ax = axes2[col_i]
    for cat_name, (halo_idx_arr, col, ls) in categories.items():
        if len(halo_idx_arr) == 0:
            continue
        med, p16, p84 = interp_profiles(halo_idx_arr, prof_arr, r500c, prof_idx, radius, r_grid)
        valid_med = np.isfinite(med) & (med > 0)
        if valid_med.sum() > 3:
            ax.plot(r_grid[valid_med], med[valid_med], color=col, ls=ls, lw=2.5)
            ax.fill_between(r_grid[valid_med], p16[valid_med], p84[valid_med],
                            color=col, alpha=0.12)
    ax.set_xscale("log")
    if use_log:
        ax.set_yscale("log")
    ax.axvline(1.0, color="gray", ls=":", lw=1.0, alpha=0.7)
    ax.set_xlabel(r"$r / R_{500c}$", fontsize=10)
    ax.set_ylabel(ylabel, fontsize=9.5)
    ax.set_title(profile_titles[col_i], fontsize=10, fontweight="bold")
    ax.grid(True, alpha=0.25, lw=0.5)

axes2[0].legend(handles=legend_handles, loc="lower right", fontsize=8, framealpha=0.8, ncol=1)
plt.tight_layout()
out2 = os.path.join(EXPERIMENT_DIR, "phase5_stacked_profiles_by_class.png")
fig2.savefig(out2, dpi=150, bbox_inches="tight")
plt.close(fig2)
print(f"Saved: {out2}")

# ------------------------------------------------------------------ Figure 3: Scaling relations ---
fig3, axes3 = plt.subplots(2, 3, figsize=(18, 11))
fig3.suptitle("Cluster Scaling Relations by Relaxation Classification (Frontier-E z=0)", fontsize=13)

cat_colors = {
    "all_R":      ("All Relaxed (R1∩R2∩R3)",            all_R,      "steelblue",  "o", 40),
    "all_U":      ("All Unrelaxed (¬R1∩¬R2∩¬R3)",       all_U,      "firebrick",  "^", 40),
    "R1R2_notR3": ("DM Relaxed, No CC (R1∩R2∩¬R3)",     R1R2_notR3, "darkorange", "s", 30),
    "R3_notR1":   ("Cool Core, DM Disturbed (R3∩¬R1)",  R3_notR1,   "purple",     "D", 30),
}

scaling_relations = [
    (t500c, l500c_bolo,
     r"$k_B T_{500c}$ [keV]", r"$L_{X,500c}^\mathrm{bolo}$ [erg s$^{-1}$]",
     "L_X–T (bolometric)", True, True),
    (m500c, y500c,
     r"$M_{500c}$ [$M_\odot\,h^{-1}$]", r"$Y_{SZ,500c}$ [arcmin$^2$]",
     r"$Y_{SZ}$–$M_{500c}$", True, True),
    (t500c, m500c,
     r"$k_B T_{500c}$ [keV]", r"$M_{500c}$ [$M_\odot\,h^{-1}$]",
     "M–T", True, True),
    (m500c, l500c_bolo,
     r"$M_{500c}$ [$M_\odot\,h^{-1}$]", r"$L_{X,500c}^\mathrm{bolo}$ [erg s$^{-1}$]",
     r"$L_X$–$M_{500c}$", True, True),
    (delta_3, l500c_bolo,
     r"$K_\mathrm{core}$ [keV cm$^2$] (core entropy)",
     r"$L_{X,500c}^\mathrm{bolo}$ [erg s$^{-1}$]",
     r"$L_X$ vs $K_\mathrm{core}$", False, True),
    (t500c, y500c,
     r"$k_B T_{500c}$ [keV]", r"$Y_{SZ,500c}$ [arcmin$^2$]",
     r"$Y_{SZ}$–$T_{500c}$", True, True),
]

for ax_i, (xarr, yarr, xlabel, ylabel, title, xlog, ylog) in enumerate(scaling_relations):
    row = ax_i // 3; col_i = ax_i % 3
    ax = axes3[row, col_i]
    for key, (label, mask, color, marker, ms) in cat_colors.items():
        g = mask & (xarr > 0) & (yarr > 0) & np.isfinite(xarr) & np.isfinite(yarr)
        if g.sum() == 0:
            continue
        ax.scatter(xarr[g], yarr[g], c=color, marker=marker, s=ms, alpha=0.4,
                   rasterized=True, label=label if ax_i == 0 else "")
    if xlog:
        ax.set_xscale("log")
    if ylog:
        ax.set_yscale("log")
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.grid(True, alpha=0.2)
    if ax_i == 4:  # K_core panel: mark threshold
        ax.axvline(THR_KE, color="k", ls="--", lw=1.5, label=f"CC threshold {THR_KE:.0f}")
        ax.legend(fontsize=8, loc="upper right")

handles = [Patch(facecolor=col, label=label)
           for key, (label, mask, col, marker, ms) in cat_colors.items()]
axes3[0, 0].legend(handles=handles, fontsize=7.5, loc="upper left", framealpha=0.8)

plt.tight_layout()
out3 = os.path.join(EXPERIMENT_DIR, "phase5_scaling_relations.png")
fig3.savefig(out3, dpi=150, bbox_inches="tight")
plt.close(fig3)
print(f"Saved: {out3}")

# ------------------------------------------------------------------ Figure 4: Extreme objects ---
# Physically distinct extreme categories:
# "DM Relaxed, AGN-heated" → DM both offsets small, but core entropy HIGH (no cool core)
# "Sloshing cool core"      → Core entropy LOW (cool core present), but DM disturbed
# "Total chaos"             → All three criteria: unrelaxed
very_rel_noCC = valid & (delta_1 < 0.03) & (delta_2 < 0.05) & (delta_3 > 200.0)
sloshing_CC   = valid & (delta_3 < 100.0) & (delta_1 > 0.1) & (delta_2 > 0.05)
total_chaos   = valid & (delta_1 > 0.2) & (delta_2 > 0.1) & (delta_3 > 200.0)

print(f"\n  DM-relaxed but AGN-heated / no CC (K_core>200): {very_rel_noCC.sum():,}")
print(f"  Sloshing cool cores (K_core<100, DM disturbed):  {sloshing_CC.sum():,}")
print(f"  Total chaos (unrelaxed all 3):                   {total_chaos.sum():,}")
print(f"  Pure relaxed (all R):                            {all_R.sum():,}")

def pick_halos(mask, n=5):
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return np.array([], dtype=int)
    return np.random.choice(idx, min(n, len(idx)), replace=False)

halos_pure_R    = pick_halos(all_R,        5)
halos_rel_noCC  = pick_halos(very_rel_noCC, 5)
halos_sloshing  = pick_halos(sloshing_CC,   5)
halos_chaos     = pick_halos(total_chaos,   5)

extreme_cats = {
    "Pure Relaxed (R1∩R2∩R3)":            (halos_pure_R,   "steelblue",  "-"),
    "DM Relaxed, AGN-heated (no CC)":      (halos_rel_noCC, "darkorange", "--"),
    "Sloshing Cool Core (CC, DM dist.)":   (halos_sloshing, "purple",     "-."),
    "Total Chaos (unrelaxed all three)":   (halos_chaos,    "firebrick",  ":"),
}

fig4, axes4 = plt.subplots(2, 5, figsize=(24, 9))
fig4.suptitle("Extreme Objects: Individual Profiles for 4 Physically Distinct Categories",
              fontsize=12, y=1.01)

profile_types_ext = [
    (bin_mass,     r"$M(<r)$ [$M_\odot\,h^{-1}$]",       True),
    (gas_ne,       r"$n_e$ [cm$^{-3}$]",                  True),
    (gas_entropy,  r"$K$ [keV cm$^2$]",                    True),
    (gas_pthermal, r"$P_\mathrm{th}$ [keV cm$^{-3}$]",    True),
    (xray_lumin,   r"$L_X$ [erg s$^{-1}$]",               True),
]
profile_titles_ext = ["Enclosed Mass", "Gas Density", "Entropy", "Pressure", "X-ray Lumin."]

for col_i, (prof_arr, ylabel, use_log) in enumerate(profile_types_ext):
    ax_top = axes4[0, col_i]
    ax_bot = axes4[1, col_i]
    ax_top.set_title(profile_titles_ext[col_i], fontsize=10, fontweight="bold")

    # Pure-relaxed median for normalisation reference
    med_R, _, _ = interp_profiles(halos_pure_R, prof_arr, r500c, prof_idx, radius, r_grid)

    for cat_name, (halo_list, col, ls) in extreme_cats.items():
        if len(halo_list) == 0:
            continue
        for ii, halo_idx in enumerate(halo_list):
            pi  = prof_idx[halo_idx]
            r   = radius[pi]
            r_n = r / r500c[halo_idx] if r500c[halo_idx] > 0 else r
            yp  = prof_arr[pi]
            vmask = (yp > 0) & (r_n > 0.02)   # local mask — NOT touching global 'valid'
            if vmask.sum() < 3:
                continue
            alpha = 0.9 if ii == 0 else 0.5
            lw    = 2.0 if ii == 0 else 1.0
            lab   = cat_name if ii == 0 else ""
            ax_top.plot(r_n[vmask], yp[vmask], color=col, ls=ls, lw=lw,
                        alpha=alpha, label=lab)
            # Ratio to pure-relaxed median
            y_ref = np.interp(r_n[vmask], r_grid, med_R, left=np.nan, right=np.nan)
            ratio = np.where(y_ref > 0, yp[vmask] / y_ref, np.nan)
            ax_bot.plot(r_n[vmask], ratio, color=col, ls=ls, lw=lw, alpha=alpha)

    for ax in [ax_top, ax_bot]:
        ax.set_xscale("log")
        ax.axvline(1.0, color="gray", ls=":", lw=0.8, alpha=0.6)
        ax.grid(True, alpha=0.25, lw=0.4)
        ax.set_xlabel(r"$r / R_{500c}$", fontsize=9)
    if use_log:
        ax_top.set_yscale("log")
        ax_bot.set_yscale("log")
    ax_top.set_ylabel(ylabel, fontsize=9)
    ax_bot.set_ylabel(r"Profile / Relaxed median", fontsize=9)
    ax_bot.axhline(1.0, color="k", ls="--", lw=1.0)

legend_handles4 = [plt.Line2D([0], [0], color=col, ls=ls, lw=2, label=name)
                   for name, (_, col, ls) in extreme_cats.items()]
axes4[0, 0].legend(handles=legend_handles4, fontsize=7.5, loc="lower right", framealpha=0.8)

plt.tight_layout()
out4 = os.path.join(EXPERIMENT_DIR, "phase5_extreme_objects_profiles.png")
fig4.savefig(out4, dpi=150, bbox_inches="tight")
plt.close(fig4)
print(f"Saved: {out4}")

# ------------------------------------------------------------------ Figure 5: δ3 diagnostics ---
# Now global 'valid' is still shape (N,) — safe to use here
fig5, axes5 = plt.subplots(1, 3, figsize=(16, 5))
fig5.suptitle(
    r"Core Entropy $K_\mathrm{core}$ as $\delta_3$: Distributions and Physical Correlations",
    fontsize=11)

# (A) K_core distribution split by δ1
ax = axes5[0]
g_rel   = valid & (delta_1 < THR_D1)
g_unrel = valid & (delta_1 >= THR_D1)
bins_ke = np.linspace(0, 400, 60)
ax.hist(delta_3[g_rel   & np.isfinite(delta_3)], bins=bins_ke, color="steelblue",
        alpha=0.65, density=True,
        label=rf"$\delta_1 < {THR_D1}$ (DM relaxed, N={g_rel.sum():,})")
ax.hist(delta_3[g_unrel & np.isfinite(delta_3)], bins=bins_ke, color="firebrick",
        alpha=0.65, density=True,
        label=rf"$\delta_1 \geq {THR_D1}$ (DM disturbed, N={g_unrel.sum():,})")
ax.axvline(THR_KE, color="k", ls="--", lw=1.5, label=f"CC threshold {THR_KE:.0f} keV cm²")
ax.set_xlabel(r"$K_\mathrm{core}$ [keV cm$^2$]", fontsize=10)
ax.set_ylabel("Density", fontsize=10)
ax.set_title(r"$K_\mathrm{core}$ distribution by $\delta_1$", fontsize=10, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# (B) K_core vs core cooling time (independent catalog check)
ax = axes5[1]
g_tcool = valid & (core_tcool > 0) & np.isfinite(core_tcool)
sc = ax.scatter(core_tcool[g_tcool], delta_3[g_tcool],
                c=logM[g_tcool], cmap="viridis", s=3, alpha=0.3, rasterized=True)
ax.axhline(THR_KE, color="k", ls="--", lw=1.5, label=f"K threshold {THR_KE:.0f}")
ax.set_xscale("log")
ax.set_xlabel(r"$t_\mathrm{cool}$ [Gyr] (core cooling time)", fontsize=10)
ax.set_ylabel(r"$K_\mathrm{core}$ [keV cm$^2$]", fontsize=10)
ax.set_title(r"$K_\mathrm{core}$ vs core cooling time", fontsize=10, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.2)
plt.colorbar(sc, ax=ax, label=r"$\log_{10} M$", shrink=0.8)

# (C) δ1 vs K_core coloured by AGN black-hole accretion rate
ax = axes5[2]
g_bhr = valid & (bhr > 0) & np.isfinite(bhr)
sc2 = ax.scatter(delta_1[g_bhr], delta_3[g_bhr],
                 c=np.log10(np.maximum(bhr[g_bhr], 1e-10)), cmap="plasma",
                 s=3, alpha=0.3, rasterized=True)
ax.axvline(THR_D1, color="k",        ls="--", lw=1.5)
ax.axhline(THR_KE, color="steelblue", ls="--", lw=1.5)
ax.set_xscale("log")
ax.set_xlabel(r"$\delta_1$ (FoF COM offset)", fontsize=10)
ax.set_ylabel(r"$K_\mathrm{core}$ [keV cm$^2$]", fontsize=10)
ax.set_title(r"$\delta_1$ vs $K_\mathrm{core}$ (colour = AGN $\dot{M}_\mathrm{BH}$)",
             fontsize=10, fontweight="bold")
ax.grid(True, alpha=0.2)
plt.colorbar(sc2, ax=ax, label=r"$\log_{10}(\dot{M}_\mathrm{BH})$", shrink=0.8)
# Annotate quadrants
ax.text(0.02, 0.03, "Relaxed + CC\n(DM+gas calm)", transform=ax.transAxes, fontsize=7.5,
        va="bottom", color="green", fontweight="bold")
ax.text(0.58, 0.03, "Unrelaxed + CC\n(sloshing?)", transform=ax.transAxes, fontsize=7.5,
        va="bottom", color="purple")
ax.text(0.02, 0.97, "DM relaxed, no CC\n(AGN-heated?)", transform=ax.transAxes, fontsize=7.5,
        va="top", color="darkorange")
ax.text(0.58, 0.97, "Unrelaxed, no CC\n(major merger)", transform=ax.transAxes, fontsize=7.5,
        va="top", color="firebrick")

plt.tight_layout()
out5 = os.path.join(EXPERIMENT_DIR, "phase5_core_entropy_analysis.png")
fig5.savefig(out5, dpi=150, bbox_inches="tight")
plt.close(fig5)
print(f"Saved: {out5}")

# ------------------------------------------------------------------ Save results ---
results5 = {
    "delta3_definition": "sod_halo_core_entropy [keV cm^2]; low = cool-core = thermally relaxed",
    "thresholds": {"delta1": THR_D1, "delta2": THR_D2, "K_core_threshold": THR_KE},
    "n_valid": int(valid.sum()),
    "n_all_relaxed":    int(all_R.sum()),
    "n_all_unrelaxed":  int(all_U.sum()),
    "n_R1R2_notR3":     int(R1R2_notR3.sum()),
    "n_sloshing_CC":    int(R3_notR1.sum()),
    "n_R1_notR2":       int(R1_notR2.sum()),
    "n_extreme_noCC":   int(very_rel_noCC.sum()),
    "n_extreme_sloshing": int(sloshing_CC.sum()),
    "n_extreme_chaos":  int(total_chaos.sum()),
    "Kcore_percentiles": np.nanpercentile(
        delta_3[valid & np.isfinite(delta_3)], [5,25,50,75,95]).tolist(),
    "c_X_percentiles": np.nanpercentile(c_X[valid & np.isfinite(c_X)], [5,25,50,75,95]).tolist(),
    "plots": [out1, out2, out3, out4, out5]
}
with open(os.path.join(EXPERIMENT_DIR, "phase5_results.json"), "w") as fout:
    json.dump(results5, fout, indent=2)

print("\n=== Phase 5 Summary ===")
print(f"  δ3 = core entropy (K_core), threshold = {THR_KE} keV cm²")
print(f"  Valid halos:                {valid.sum():,}")
print(f"  R3 (cool-core, K<{THR_KE:.0f}):   {R3.sum():,} ({100*R3.sum()/valid.sum():.1f}%)")
print(f"  Concordant relaxed:         {all_R.sum():,} ({100*all_R.sum()/valid.sum():.1f}%)")
print(f"  Concordant unrelaxed:       {all_U.sum():,} ({100*all_U.sum()/valid.sum():.1f}%)")
print(f"  DM-relaxed but no CC:       {R1R2_notR3.sum():,} — AGN-heated or minor merger?")
print(f"  Cool-core but DM disturbed: {R3_notR1.sum():,} — sloshing cool cores?")
print("Done.")
