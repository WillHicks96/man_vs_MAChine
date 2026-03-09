#!/usr/bin/env python3
"""
Phase 6: Nuanced δ₄ (Thermal Profile Indicator) + Comprehensive Stacked Profile Analysis

δ₄ = TPI = z(ln core_ne) + z(ln T_ratio)
    where T_ratio = T500cBoloEx / T500c  (core-excised / global bolometric temperature)
    z() = robust z-score via median absolute deviation

    High TPI → high core electron density AND strong core temperature drop
             → strong cool-core state
    Low TPI  → low core density OR minimal temperature drop
             → AGN-heated or mechanically disrupted core

    Why more nuanced than δ₃ (K_core alone)?
      K_core = T_core × n_e^{-2/3}  —  single number, fixed T-n_e coupling
      TPI keeps n_e (density peak amplitude) and T-ratio (spectral temperature
      structure) as SEPARATE observables. A cluster with high n_e but high T
      (shock-heated dense core) has moderate K_core but a distinct TPI signature.
      TPI also uses T500cBoloEx which is a non-local, survey-accessible observable.

Main figures:
  Fig 1: 5 profile rows × 4 criterion columns (comprehensive stacked profiles)
         Col 0: R1 vs ~R1 (DM baseline, all halos)
         Col 1: R1∩R2 vs R1∩~R2 (within DM-relaxed: gas–DM alignment)
         Col 2: R1∩R3 vs R1∩~R3 (within DM-relaxed: core entropy)
         Col 3: R1∩R4 vs R1∩~R4 (within DM-relaxed: TPI score)
         All panels: shaded radial zones (core / inner / body / outskirts)
         Cols 1-3: faint ~R1 and R1 reference lines as context

  Fig 2: 3 criterion rows × 5 profile cols — log₁₀ ratio [R1∩Rx / R1∩~Rx]
         Highlights where in radius each criterion is most discriminating
         Annotated with astrophysical implications per radial zone

  Fig 3: δ₄ diagnostic — core_ne vs T_ratio scatter, and TPI vs K_core comparison
"""
import os, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, FancyArrowPatch
import matplotlib.ticker as mticker
import h5py

PROJECT_ROOT = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments"
EXPERIMENT_DIR = os.path.join(PROJECT_ROOT, "runs", "research_20260218_105441")
CATALOG = "/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5"
np.random.seed(42)

# ------------------------------------------------------------------ load ---
print("Loading catalog…")
with h5py.File(CATALOG, "r") as f:
    props = f["halo_properties/data"]
    fof_mass     = np.array(props["fof_halo_mass"])
    m500c        = np.array(props["sod_halo_M500c"])
    r500c        = np.array(props["sod_halo_R500c"])
    r200m        = np.array(props["sod_halo_R200m"])
    t500c        = np.array(props["sod_halo_T500c"])
    t500c_bolo_ex= np.array(props["sod_halo_T500cBoloEx"])  # core-excised
    l500c_bolo   = np.array(props["sod_halo_L500cBolo"])
    y500c        = np.array(props["sod_halo_Y500c"])
    core_ne      = np.array(props["sod_halo_core_ne"])       # core electron density
    core_tcool   = np.array(props["sod_halo_core_tcool"])
    core_entropy = np.array(props["sod_halo_core_entropy"])
    bhr          = np.array(props["sod_halo_bhr"])
    # COM vectors
    fof_cx  = np.array(props["fof_halo_center_x"]);  fof_cy  = np.array(props["fof_halo_center_y"])
    fof_cz  = np.array(props["fof_halo_center_z"]);  fof_cx2 = np.array(props["fof_halo_com_x"])
    fof_cy2 = np.array(props["fof_halo_com_y"]);     fof_cz2 = np.array(props["fof_halo_com_z"])
    sod_dm_x  = np.array(props["sod_halo_com_x_dm"]); sod_dm_y  = np.array(props["sod_halo_com_y_dm"])
    sod_dm_z  = np.array(props["sod_halo_com_z_dm"]); sod_gas_x = np.array(props["sod_halo_com_x_gas"])
    sod_gas_y = np.array(props["sod_halo_com_y_gas"]); sod_gas_z = np.array(props["sod_halo_com_z_gas"])
    # profiles
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

# ------------------------------------------------------------------ δ1, δ2, δ3 ---
d1_abs  = np.sqrt((fof_cx2-fof_cx)**2 + (fof_cy2-fof_cy)**2 + (fof_cz2-fof_cz)**2)
delta_1 = np.where(r200m > 0, d1_abs / r200m, np.nan)
d2_abs  = np.sqrt((sod_dm_x-sod_gas_x)**2 + (sod_dm_y-sod_gas_y)**2 + (sod_dm_z-sod_gas_z)**2)
delta_2 = np.where(r500c > 0, d2_abs / r500c, np.nan)
delta_3 = core_entropy  # [keV cm²]; low = cool-core

# ------------------------------------------------------------------ δ4: TPI ---
# Thermal Profile Indicator = z(ln core_ne) + z(ln T_ratio)
# T_ratio = T500cBoloEx / T500c  >1 for cool-core (excised temperature > total)
T_ratio = np.where((t500c > 0) & (t500c_bolo_ex > 0),
                   t500c_bolo_ex / t500c, np.nan)

def robust_zscore(arr):
    """Robust z-score: (x - median) / (1.4826 * MAD)  — works for any finite values"""
    finite = np.isfinite(arr)           # do NOT require > 0 (log values are negative)
    vals = arr[finite]
    if vals.size == 0:
        return np.full_like(arr, np.nan)
    med = np.median(vals)
    mad = np.median(np.abs(vals - med))
    if mad < 1e-30:
        mad = np.std(vals) + 1e-30
    return (arr - med) / (1.4826 * mad)

log_ne    = np.where(core_ne > 0,  np.log(core_ne),  np.nan)
log_Tratio= np.where(T_ratio > 0, np.log(T_ratio), np.nan)

z_ne    = robust_zscore(log_ne)
z_Tratio= robust_zscore(log_Tratio)

TPI = z_ne + z_Tratio   # high = high density + strong core T drop = cool-core

print(f"\n  δ3 (core entropy) perc [5,25,50,75,95]:  {np.nanpercentile(delta_3, [5,25,50,75,95])}")
print(f"  T_ratio perc [5,25,50,75,95]:             {np.nanpercentile(T_ratio, [5,25,50,75,95])}")
print(f"  core_ne perc [5,25,50,75,95]:             {np.nanpercentile(core_ne, [5,25,50,75,95])}")
print(f"  TPI perc [5,25,50,75,95]:                 {np.nanpercentile(TPI, [5,25,50,75,95])}")

# ------------------------------------------------------------------ classification ---
THR_D1  = 0.07
THR_D2  = 0.07
THR_KE  = 150.0   # keV cm²
THR_TPI = 0.0     # above-median combined score

# Global valid mask — NEVER overwrite inside loops
valid = (np.isfinite(delta_1) & np.isfinite(delta_2) & np.isfinite(delta_3) &
         (delta_1 > 0) & (delta_2 > 0) & (delta_3 > 0) &
         np.isfinite(TPI) & (logM >= 13.5))

R1 = valid & (delta_1 < THR_D1)
R2 = valid & (delta_2 < THR_D2)
R3 = valid & (delta_3 < THR_KE)
R4 = valid & (TPI > THR_TPI)

notR1     = valid & ~R1
R1_andR2  = R1 & (delta_2 < THR_D2)
R1_notR2  = R1 & (delta_2 >= THR_D2)
R1_andR3  = R1 & (delta_3 < THR_KE)
R1_notR3  = R1 & (delta_3 >= THR_KE)
R1_andR4  = R1 & (TPI > THR_TPI)
R1_notR4  = R1 & (TPI <= THR_TPI)

print(f"\n  valid={valid.sum():,}  R1={R1.sum():,}  ~R1={notR1.sum():,}")
print(f"  R4 (TPI>0)={R4.sum():,}  R3 (K<150)={R3.sum():,}")
print(f"  R1∩R2={R1_andR2.sum():,}  R1∩~R2={R1_notR2.sum():,}")
print(f"  R1∩R3={R1_andR3.sum():,}  R1∩~R3={R1_notR3.sum():,}")
print(f"  R1∩R4={R1_andR4.sum():,}  R1∩~R4={R1_notR4.sum():,}")
print(f"  R3 but not R4 (K-cool but not TPI-cool): {(R1_andR3 & ~(TPI>THR_TPI)).sum():,}")
print(f"  R4 but not R3 (TPI-cool but not K-cool): {(R1_andR4 & (delta_3>=THR_KE)).sum():,}")

# ------------------------------------------------------------------ profile interpolation ---
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
        vmask = (yp > 0) & (r_n > 0)   # local mask — NOT touching global 'valid'
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

# ------------------------------------------------------------------ Precompute reference profiles ---
print("\nPrecomputing reference profiles (R1 and ~R1)…")
profile_defs = [
    (bin_mass,     r"$M(<r)\,[M_\odot\,h^{-1}]$",          "Enclosed Mass",      True),
    (gas_ne,       r"$n_e\,[\mathrm{cm}^{-3}]$",            "Gas Electron Density", True),
    (gas_entropy,  r"$K\,[\mathrm{keV\,cm}^2]$",            "Gas Entropy",         True),
    (gas_pthermal, r"$P_\mathrm{th}\,[\mathrm{keV\,cm}^{-3}]$","Thermal Pressure",True),
    (xray_lumin,   r"$L_X\,[\mathrm{erg\,s}^{-1}]$",        "X-ray Luminosity",    True),
]
ref = {}
for pi, (parr, ylabel, ptitle, ulog) in enumerate(profile_defs):
    med_R1,   p16_R1,   p84_R1   = interp_profiles(np.where(R1)[0],    parr, r500c, prof_idx, radius, r_grid, 500)
    med_notR1, p16_nR1, p84_nR1  = interp_profiles(np.where(notR1)[0], parr, r500c, prof_idx, radius, r_grid, 500)
    ref[pi] = (med_R1, p16_R1, p84_R1, med_notR1, p16_nR1, p84_nR1)
    print(f"  {ptitle}: R1 N={R1.sum():,}, ~R1 N={notR1.sum():,}")

# ------------------------------------------------------------------ FIGURE 1: Comprehensive stacked profiles ---
print("\nBuilding Figure 1: Comprehensive stacked profiles (5×4)…")

# Radial zone definitions: (r_lo, r_hi, face_color, label, label_x, label_y_frac, fontsize)
zones = [
    (0.015, 0.15, '#FFFDE7', 'Core', 0.05,  0.97, 7.5),
    (0.15,  0.5,  '#E3F2FD', 'Inner', 0.28,  0.97, 7.5),
    (0.5,   1.0,  '#F3E5F5', 'Body',  0.70,  0.97, 7.5),
    (1.0,   2.5,  '#FFFFFF', 'Outskirts', 1.65, 0.97, 7.5),
]
zone_lines = [0.15, 0.5, 1.0]

# Column definitions
col_defs = [
    # (mask_A, mask_B, color_A, color_B, label_A, label_B, col_title, show_ref)
    (R1, notR1,
     '#1A3A7C', '#8B0000',
     r"$\delta_1 < 0.07$ (DM relaxed)", r"$\delta_1 \geq 0.07$ (DM disturbed)",
     r"Baseline: DM Relaxation ($\delta_1$)" + "\n(all 10,000 halos)", False),
    (R1_andR2, R1_notR2,
     '#005F5F', '#CC4400',
     r"R1 $\cap$ R2  (gas–DM aligned)", r"R1 $\cap$ $\neg$R2  (DM–gas offset)",
     r"$\delta_2$: Gas–DM Centroid Offset" + "\n(within DM-relaxed R1)", True),
    (R1_andR3, R1_notR3,
     '#1B6B1B', '#6A0DAD',
     r"R1 $\cap$ R3  (cool core, $K < 150$)", r"R1 $\cap$ $\neg$R3  (non-CC, $K \geq 150$)",
     r"$\delta_3$: Core Entropy $K_\mathrm{core}$" + "\n(within DM-relaxed R1)", True),
    (R1_andR4, R1_notR4,
     '#1565C0', '#B71C1C',
     r"R1 $\cap$ R4  (high TPI, cool core)", r"R1 $\cap$ $\neg$R4  (low TPI, non-CC)",
     r"$\delta_4$: Thermal Profile Indicator" + "\n(within DM-relaxed R1)", True),
]

fig1, axes1 = plt.subplots(5, 4, figsize=(24, 20),
                            sharex=True, sharey='row')
fig1.suptitle(
    r"Stacked Median Radial Profiles — DM Relaxation as Baseline, Stratified by Three Secondary Criteria"
    + "\n" + r"(shaded bands: 16th–84th percentile for $\delta_1$ baseline; lines for secondary criteria)",
    fontsize=11.5, y=1.005)

# Physical zone labels for the top of the figure — will be added to row 0 panels
zone_physics = {
    'Core':     "AGN feedback\ncooling / BCG",
    'Inner':    "Gas sloshing\nfeedback bubbles",
    'Body':     "Merger turbulence\nbulk flows",
    'Outskirts':"Infall filaments\ngas clumping",
}

for row_i, (parr, ylabel, ptitle, ulog) in enumerate(profile_defs):
    med_R1, p16_R1, p84_R1, med_nR1, p16_nR1, p84_nR1 = ref[row_i]

    for col_i, (mA, mB, colA, colB, labA, labB, col_title, show_ref) in enumerate(col_defs):
        ax = axes1[row_i, col_i]

        # Background zone shading
        for (r_lo, r_hi, fc, zlbl, zx, zy, zfs) in zones:
            ax.axvspan(r_lo, r_hi, alpha=0.18, color=fc, zorder=0)
        for rl in zone_lines:
            ax.axvline(rl, color='#AAAAAA', ls=':', lw=0.8, alpha=0.7, zorder=1)

        # Reference lines (cols 1-3 only)
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
                        label='R1 overall' if row_i == 0 else '')

        # Compute and plot mask A (solid thick) and B (dashed thick)
        medA, p16A, p84A = interp_profiles(np.where(mA)[0], parr, r500c, prof_idx, radius, r_grid, 500)
        medB, p16B, p84B = interp_profiles(np.where(mB)[0], parr, r500c, prof_idx, radius, r_grid, 500)

        vmA = np.isfinite(medA) & (medA > 0)
        vmB = np.isfinite(medB) & (medB > 0)

        if vmA.sum() > 3:
            ax.plot(r_grid[vmA], medA[vmA], color=colA, lw=2.5, ls='-', zorder=4,
                    label=labA if row_i == 0 else '')
            if not show_ref:   # fill bands only for baseline column
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

        # Left y-axis label
        if col_i == 0:
            ax.set_ylabel(ylabel, fontsize=9)
        # Bottom x-axis label
        if row_i == 4:
            ax.set_xlabel(r'$r / R_{500c}$', fontsize=9.5)
        # Column titles (top row)
        if row_i == 0:
            ax.set_title(col_title, fontsize=9, fontweight='bold', pad=7)
            # Zone physics labels inside plot
            for (r_lo, r_hi, fc, zlbl, zx, zy, zfs) in zones:
                r_mid = np.sqrt(r_lo * r_hi)
                ax.text(r_mid, 0.97, zlbl + "\n" + zone_physics[zlbl],
                        transform=ax.get_xaxis_transform(),
                        fontsize=6, ha='center', va='top', color='#444444',
                        bbox=dict(facecolor=fc, alpha=0.5, edgecolor='none', pad=1))
        # Legend in first row
        if row_i == 0:
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                ax.legend(handles=handles, labels=labels,
                          fontsize=6.5, loc='lower right', framealpha=0.85,
                          ncol=1, handlelength=1.5, handletextpad=0.4)
        # N counts in top-left of each panel
        nA = mA.sum(); nB = mB.sum()
        if row_i == 4:
            ax.text(0.03, 0.97, f"N={nA:,} / {nB:,}",
                    transform=ax.transAxes, fontsize=7, va='top', color='#333333')

plt.tight_layout(h_pad=0.5, w_pad=0.4)
out1 = os.path.join(EXPERIMENT_DIR, "phase6_stacked_profiles_comprehensive.png")
fig1.savefig(out1, dpi=150, bbox_inches='tight')
plt.close(fig1)
print(f"Saved: {out1}")

# ------------------------------------------------------------------ FIGURE 2: Ratio profiles ---
print("\nBuilding Figure 2: Ratio profiles (R1∩Rx / R1∩~Rx)…")

# Secondary criteria and their labels
sec_criteria = [
    (R1_andR2, R1_notR2,
     r"$\delta_2$: Gas–DM Alignment  [R1$\cap$R2 / R1$\cap\neg$R2]",
     "#005F5F",
     {   # radius-zone annotations: zone_name → (r_lo, r_hi, label text)
         'core':     "Core (< 0.15 R₅₀₀c):\nGas-aligned DM-relaxed halos have\nslightly higher pressure here\nfrom undisturbed BCG cooling",
         'inner':    "Inner (0.15–0.5 R₅₀₀c):\nSloshing halos (~R2) show elevated\nentropy & L_X — cold-front\ninterface with uplifted warm gas",
         'body':     "Body (0.5–1.0 R₅₀₀c):\nLargest δ₂ signal here — gas and\nDM centroids separated by\ngravitational sloshing motions",
         'outskirts':"Outskirts (> 1.0 R₅₀₀c):\nMass profiles converge — δ₂\ndoes not probe large-scale DM",
     }),
    (R1_andR3, R1_notR3,
     r"$\delta_3$: Core Entropy  [R1$\cap$R3 / R1$\cap\neg$R3]",
     "#1B6B1B",
     {   'core':     "Core:\nCool-core halos (R3) show 10–100×\nhigher nₑ, suppressed entropy,\nand peaked L_X — thermally\nrelaxed BCG environment",
         'inner':    "Inner:\nModerate nₑ excess in R3 —\ncore cooling extends to ~0.3 R₅₀₀c;\nentropy gradient steepens",
         'body':     "Body:\nProfiles converge outside\n~0.5 R₅₀₀c — core entropy\ncriteria is insensitive here",
         'outskirts':"Outskirts:\nNo distinction — both classes\nhave similar large-scale\naccretion history",
     }),
    (R1_andR4, R1_notR4,
     r"$\delta_4$: TPI [z($n_e$)+z($T$-ratio)]  [R1$\cap$R4 / R1$\cap\neg$R4]",
     "#1565C0",
     {   'core':     "Core:\nTPI captures BOTH density peak\nand temperature drop — steeper\nseparation than δ₃ alone for\nshock-heated dense cores",
         'inner':    "Inner:\nTPI more sensitive to nₑ\nprofile slope — separates clusters\nwith extended dense gas\nvs. compact cores",
         'body':     "Body:\nT-ratio contribution to TPI\npropagates to intermediate radii\nvia global temperature measurement",
         'outskirts':"Outskirts:\nSimilar to δ₃ — TPI is\nprimarily a core diagnostic",
     }),
]

profile_short = ["Enclosed Mass", "Gas Density", "Entropy", "Pressure", "X-ray Lumin."]
ylabels_ratio = [
    r"$\log_{10}(M_A/M_B)$",
    r"$\log_{10}(n_{e,A}/n_{e,B})$",
    r"$\log_{10}(K_A/K_B)$",
    r"$\log_{10}(P_A/P_B)$",
    r"$\log_{10}(L_{X,A}/L_{X,B})$",
]

fig2, axes2 = plt.subplots(3, 5, figsize=(22, 12),
                            sharex=True)
fig2.suptitle(
    r"Profile Ratio Maps: R1$\cap$Rx / R1$\cap\neg$Rx — Where in Radius Does Each Criterion Discriminate?"
    + "\n" + "(ratio > 0: Rx class has more; < 0: Rx class has less; shading indicates astrophysical regime)",
    fontsize=10.5, y=1.01)

# Zone shading for ratio plots (same colors but lighter)
zones_ratio = [
    (0.015, 0.15, '#FFFDE7', 'Core\n(< 0.15 R₅₀₀c)', 0.05),
    (0.15,  0.5,  '#E3F2FD', 'Inner\n(0.15–0.5)', 0.28),
    (0.5,   1.0,  '#F3E5F5', 'Body\n(0.5–1.0)', 0.70),
    (1.0,   2.5,  '#FFFFFF', 'Outskirts\n(>1.0)', 1.65),
]

# Precompute ratios
all_ratios = {}  # (crit_i, prof_i) → (r_grid, log10_ratio)
for crit_i, (mA, mB, clabel, col, annots) in enumerate(sec_criteria):
    for prof_i, (parr, ylabel, ptitle, ulog) in enumerate(profile_defs):
        medA, _, _ = interp_profiles(np.where(mA)[0], parr, r500c, prof_idx, radius, r_grid, 500)
        medB, _, _ = interp_profiles(np.where(mB)[0], parr, r500c, prof_idx, radius, r_grid, 500)
        with np.errstate(divide='ignore', invalid='ignore'):
            ratio = np.where((medA > 0) & (medB > 0), np.log10(medA / medB), np.nan)
        all_ratios[(crit_i, prof_i)] = ratio

for crit_i, (mA, mB, clabel, col, annots) in enumerate(sec_criteria):
    for prof_i, (parr, ylabel, ptitle, ulog) in enumerate(profile_defs):
        ax = axes2[crit_i, prof_i]
        ratio = all_ratios[(crit_i, prof_i)]

        # Zone shading
        for (r_lo, r_hi, fc, zlbl, zx) in zones_ratio:
            ax.axvspan(r_lo, r_hi, alpha=0.2, color=fc, zorder=0)
        for rl in zone_lines:
            ax.axvline(rl, color='#AAAAAA', ls=':', lw=0.8, alpha=0.7, zorder=1)
        ax.axhline(0, color='k', lw=1.2, ls='-', zorder=2, alpha=0.6)

        # Ratio profile
        vmr = np.isfinite(ratio)
        if vmr.sum() > 3:
            ax.plot(r_grid[vmr], ratio[vmr], color=col, lw=2.5, zorder=3)
            # Shade the region between 0 and the ratio (fill under the curve)
            ax.fill_between(r_grid[vmr], 0, ratio[vmr],
                            where=ratio[vmr] > 0, color=col, alpha=0.15, zorder=2)
            ax.fill_between(r_grid[vmr], 0, ratio[vmr],
                            where=ratio[vmr] < 0, color='#CC0000', alpha=0.12, zorder=2)

        ax.set_xscale('log')
        ax.grid(True, alpha=0.15, lw=0.4)
        ax.tick_params(labelsize=8)

        # Symmetric y-axis — find max deviation
        if vmr.sum() > 3:
            dev = np.nanmax(np.abs(ratio[vmr]))
            ax.set_ylim(-min(dev*1.4+0.05, 2.5), min(dev*1.4+0.05, 2.5))

        # Column title (top row)
        if crit_i == 0:
            ax.set_title(profile_short[prof_i], fontsize=9.5, fontweight='bold')
            # Zone labels
            for (r_lo, r_hi, fc, zlbl, zx) in zones_ratio:
                r_mid = np.sqrt(r_lo * r_hi)
                ax.text(r_mid, 0.98, zlbl, transform=ax.get_xaxis_transform(),
                        fontsize=6, ha='center', va='top', color='#555555')

        # Row label (criterion)
        if prof_i == 0:
            ax.set_ylabel(ylabels_ratio[prof_i] + "\n" + clabel, fontsize=8)
        if prof_i > 0 and crit_i == 0:
            ax.set_ylabel(ylabels_ratio[prof_i], fontsize=8)
        if prof_i > 0 and crit_i > 0:
            ax.set_ylabel("")

        # x-axis label
        if crit_i == 2:
            ax.set_xlabel(r'$r / R_{500c}$', fontsize=9)

        # Annotation for max deviation radius (crit_i == row label)
        if prof_i == 0 and vmr.sum() > 3:
            peak_i = np.nanargmax(np.abs(ratio[vmr]))
            peak_r = r_grid[vmr][peak_i]
            peak_v = ratio[vmr][peak_i]
            ax.annotate(f"peak at\n{peak_r:.2f} R₅₀₀c",
                        xy=(peak_r, peak_v), xytext=(peak_r*2.5, peak_v*0.6),
                        fontsize=7, color=col, ha='left',
                        arrowprops=dict(arrowstyle='->', color=col, lw=0.8))

plt.tight_layout(h_pad=0.6, w_pad=0.4)
out2 = os.path.join(EXPERIMENT_DIR, "phase6_ratio_profiles.png")
fig2.savefig(out2, dpi=150, bbox_inches='tight')
plt.close(fig2)
print(f"Saved: {out2}")

# ------------------------------------------------------------------ FIGURE 3: δ₄ diagnostic ---
print("\nBuilding Figure 3: δ₄ TPI diagnostic…")

fig3, axes3 = plt.subplots(1, 3, figsize=(18, 5.5))
fig3.suptitle(
    r"$\delta_4$ Thermal Profile Indicator (TPI): Definition, Validation, and Comparison with $\delta_3$",
    fontsize=11)

# Panel A: core_ne vs T_ratio scatter, coloured by TPI
ax = axes3[0]
g = valid & (core_ne > 0) & (T_ratio > 0) & np.isfinite(TPI)
sc = ax.scatter(core_ne[g], T_ratio[g], c=TPI[g], cmap='RdBu',
                vmin=-3, vmax=3, s=3, alpha=0.3, rasterized=True)
# Median thresholds
ax.axvline(np.nanmedian(core_ne[g]), color='k', ls='--', lw=1.0, alpha=0.6)
ax.axhline(np.nanmedian(T_ratio[g]),  color='k', ls='--', lw=1.0, alpha=0.6)
ax.set_xscale('log')
ax.set_xlabel(r"$n_{e,\mathrm{core}}$ [cm$^{-3}$] (core electron density)", fontsize=10)
ax.set_ylabel(r"$T_{500c}^\mathrm{ex} / T_{500c}$ (core temperature drop ratio)", fontsize=10)
ax.set_title("TPI components: where each halo lies", fontsize=9.5, fontweight='bold')
ax.grid(True, alpha=0.2)
cb = plt.colorbar(sc, ax=ax, shrink=0.85)
cb.set_label("TPI score (blue=cool-core, red=disrupted)", fontsize=8)
# Quadrant labels
ax.text(0.02, 0.97, "High $n_e$ + T-drop\n→ Strong cool core\n(R4)", transform=ax.transAxes,
        fontsize=7.5, va='top', color='#0000CC', fontweight='bold')
ax.text(0.60, 0.02, "Low $n_e$, no T-drop\n→ Disrupted/AGN-heated\n(~R4)", transform=ax.transAxes,
        fontsize=7.5, va='bottom', color='#CC0000')
ax.text(0.02, 0.02, "High $n_e$, no T-drop\n→ Dense shock-heated\n(ambiguous by $K$)", transform=ax.transAxes,
        fontsize=7.5, va='bottom', color='#888800')
ax.text(0.60, 0.97, "Low $n_e$ + T-drop\n→ Compact cool group\n(also ambiguous)", transform=ax.transAxes,
        fontsize=7.5, va='top', color='#008800')

# Panel B: TPI vs K_core — where δ₃ and δ₄ agree/disagree
ax = axes3[1]
g2 = valid & np.isfinite(TPI) & (core_entropy > 0)
# Colour by agreement
agree_CC   = (TPI[g2] > 0)  & (core_entropy[g2] < THR_KE)   # both say cool-core
agree_NCC  = (TPI[g2] <= 0) & (core_entropy[g2] >= THR_KE)  # both say non-CC
discord_R3 = (TPI[g2] <= 0) & (core_entropy[g2] < THR_KE)   # K says CC, TPI says no
discord_R4 = (TPI[g2] > 0)  & (core_entropy[g2] >= THR_KE)  # TPI says CC, K says no

colors_d = np.where(agree_CC,  '#1565C0',
           np.where(agree_NCC, '#B71C1C',
           np.where(discord_R3,'#7B1FA2',
                                '#E65100')))
ax.scatter(TPI[g2], core_entropy[g2], c=colors_d, s=3, alpha=0.25, rasterized=True)
ax.axvline(0, color='k', ls='--', lw=1.2, alpha=0.7)
ax.axhline(THR_KE, color='k', ls='--', lw=1.2, alpha=0.7)
ax.set_xlabel("TPI score (δ₄)", fontsize=10)
ax.set_ylabel(r"$K_\mathrm{core}$ [keV cm$^2$] (δ₃)", fontsize=10)
ax.set_title(r"Agreement between $\delta_3$ and $\delta_4$", fontsize=9.5, fontweight='bold')
ax.grid(True, alpha=0.2)
# Legend
from matplotlib.lines import Line2D
leg_els = [
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#1565C0', ms=6,
           label=f"Both CC (δ₃∩δ₄): {agree_CC.sum():,}"),
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#B71C1C', ms=6,
           label=f"Both NCC: {agree_NCC.sum():,}"),
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#7B1FA2', ms=6,
           label=f"K-CC but TPI-NCC: {discord_R3.sum():,}"),
    Line2D([0],[0], marker='o', color='w', markerfacecolor='#E65100', ms=6,
           label=f"TPI-CC but K-NCC: {discord_R4.sum():,}"),
]
ax.legend(handles=leg_els, fontsize=7.5, loc='upper right', framealpha=0.85)
# Annotations for quadrants
ax.text(1.5, 200, "Dense + T-drop\nbut K too high\n(merger shock?)", fontsize=7,
        color='#E65100', ha='center')
ax.text(-2.5, 80, "K-CC but low TPI\n(cooling with weak\ndensity peak)", fontsize=7,
        color='#7B1FA2', ha='center')

# Panel C: stacked median entropy and n_e profiles for the 4 discordant groups
ax = axes3[2]
r_g2 = np.logspace(np.log10(0.02), np.log10(2.0), 60)
idx_all = np.where(g2)[0]

groups_disc = {
    "Both CC\n(δ₃ ∩ δ₄)":       (idx_all[agree_CC],   '#1565C0', '-',  2.5),
    "Both NCC\n(¬δ₃ ∩ ¬δ₄)":   (idx_all[agree_NCC],  '#B71C1C', '-',  2.5),
    "K-CC, TPI-NCC\n(¬δ₄ ∩ δ₃)":(idx_all[discord_R3], '#7B1FA2', '--', 2.0),
    "TPI-CC, K-NCC\n(δ₄ ∩ ¬δ₃)":(idx_all[discord_R4], '#E65100', '--', 2.0),
}
for glabel, (gidx, gcol, gls, glw) in groups_disc.items():
    if len(gidx) == 0:
        continue
    med, _, _ = interp_profiles(gidx, gas_entropy, r500c, prof_idx, radius, r_g2, 300)
    vmg = np.isfinite(med) & (med > 0)
    if vmg.sum() > 3:
        ax.plot(r_g2[vmg], med[vmg], color=gcol, ls=gls, lw=glw, label=glabel)
ax.axvline(0.15, color='gray', ls=':', lw=0.8, alpha=0.6)
ax.axvline(1.0,  color='gray', ls=':', lw=0.8, alpha=0.6)
ax.axhline(THR_KE, color='k', ls='--', lw=1.0, alpha=0.5, label=f"$K_{{core}}$ threshold\n({THR_KE:.0f} keV cm²)")
ax.set_xscale('log')
ax.set_xlabel(r'$r / R_{500c}$', fontsize=10)
ax.set_ylabel(r"Entropy $K$ [keV cm$^2$]", fontsize=10)
ax.set_title("Entropy profiles: δ₃ vs δ₄ concordance groups", fontsize=9.5, fontweight='bold')
ax.legend(fontsize=7.5, loc='upper left', framealpha=0.85)
ax.grid(True, alpha=0.2)
# Only set log scale if axis has valid positive data
try:
    ax.set_yscale('log')
except Exception:
    pass
ax.text(0.04, 150, 'Core', fontsize=7, color='gray')
ax.text(0.55, 150, r'$R_{500c}$', fontsize=7, color='gray')

plt.tight_layout()
out3 = os.path.join(EXPERIMENT_DIR, "phase6_tpi_diagnostic.png")
fig3.savefig(out3, dpi=150, bbox_inches='tight')
plt.close(fig3)
print(f"Saved: {out3}")

# ------------------------------------------------------------------ Save results ---
# Count discordant δ₃/δ₄ cases
g_disc = valid & np.isfinite(TPI) & (core_entropy > 0)
n_agree_CC   = int((valid & (TPI > 0) & (delta_3 < THR_KE)).sum())
n_agree_NCC  = int((valid & (TPI <= 0) & (delta_3 >= THR_KE)).sum())
n_K_not_TPI  = int((valid & (TPI <= 0) & (delta_3 < THR_KE)).sum())
n_TPI_not_K  = int((valid & (TPI > 0) & (delta_3 >= THR_KE)).sum())

results6 = {
    "delta4_definition": "TPI = z(ln core_ne) + z(ln T_ratio); T_ratio = T500cBoloEx/T500c",
    "thresholds": {"delta1": THR_D1, "delta2": THR_D2, "K_core": THR_KE, "TPI": THR_TPI},
    "n_valid": int(valid.sum()),
    "n_R4": int(R4.sum()),
    "n_R1_andR2": int(R1_andR2.sum()), "n_R1_notR2": int(R1_notR2.sum()),
    "n_R1_andR3": int(R1_andR3.sum()), "n_R1_notR3": int(R1_notR3.sum()),
    "n_R1_andR4": int(R1_andR4.sum()), "n_R1_notR4": int(R1_notR4.sum()),
    "delta3_delta4_concordance": {
        "both_CC": n_agree_CC, "both_NCC": n_agree_NCC,
        "K_CC_TPI_NCC": n_K_not_TPI, "TPI_CC_K_NCC": n_TPI_not_K,
    },
    "TPI_percentiles": np.nanpercentile(TPI[valid], [5,25,50,75,95]).tolist(),
    "T_ratio_percentiles": np.nanpercentile(T_ratio[valid & np.isfinite(T_ratio)],
                                             [5,25,50,75,95]).tolist(),
    "plots": [out1, out2, out3]
}
with open(os.path.join(EXPERIMENT_DIR, "phase6_results.json"), "w") as fout:
    json.dump(results6, fout, indent=2)

print("\n=== Phase 6 Summary ===")
print(f"  δ4 (TPI) > 0 classified as cool-core: {R4.sum():,} ({100*R4.sum()/valid.sum():.1f}%)")
print(f"  δ3-δ4 concordance: both CC={n_agree_CC:,}, both NCC={n_agree_NCC:,}")
print(f"  K cool-core but TPI not: {n_K_not_TPI:,}  (TPI adds nuance over K alone)")
print(f"  TPI cool-core but K not: {n_TPI_not_K:,}  (dense shock-heated cores?)")
print("Done.")
