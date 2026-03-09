#!/usr/bin/env python3
"""
Phase 1: Frontier-E halo catalog + profiles
- Load 10,000 halos with 51 radial bins each
- Select 10 random halos spanning the mass range
- Plot 10 profile types relevant to relaxed/unrelaxed analysis
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import h5py
import json

# ------------------------------------------------------------------ paths ---
PROJECT_ROOT = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments"
EXPERIMENT_DIR = os.path.join(PROJECT_ROOT, "runs", "research_20260218_105441")
CATALOG = "/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5"

os.makedirs(EXPERIMENT_DIR, exist_ok=True)
np.random.seed(42)

# ------------------------------------------------------------------ load ---
print("Loading catalog and profiles...")
with h5py.File(CATALOG, "r") as f:
    # Halo properties
    props = f["halo_properties/data"]
    fof_mass   = np.array(props["fof_halo_mass"])     # Msun/h
    m500c      = np.array(props["sod_halo_M500c"])    # Msun/h
    r500c      = np.array(props["sod_halo_R500c"])    # Mpc/h comoving
    t500c      = np.array(props["sod_halo_T500c"])    # keV
    y500c      = np.array(props["sod_halo_Y500c"])    # arcmin^2
    l500c_bolo = np.array(props["sod_halo_L500cBolo"])  # erg/s
    cdelta     = np.array(props["sod_halo_cdelta"])
    unique_tag = np.array(props["unique_tag"])

    # Profile data (shape: N_halos x 51 bins)
    pdata = f["halo_profiles/data"]
    radius       = np.array(pdata["sod_halo_bin_radius"])       # Mpc/h, shape (N, 51)
    bin_mass     = np.array(pdata["sod_halo_bin_mass"])         # enclosed mass
    gas_ne       = np.array(pdata["sod_halo_bin_gas_ne"])       # electron density
    gas_temp     = np.array(pdata["sod_halo_bin_gas_temperature"])   # keV
    gas_entropy  = np.array(pdata["sod_halo_bin_gas_entropy"])  # keV cm^2
    gas_pthermal = np.array(pdata["sod_halo_bin_gas_pthermal"]) # thermal pressure
    gas_pkinetic = np.array(pdata["sod_halo_bin_gas_pkinetic"]) # kinetic pressure
    xray_lumin   = np.array(pdata["sod_halo_bin_hot_gas_lumin_bolo"])  # X-ray lum
    rad_vel      = np.array(pdata["sod_halo_bin_rad_vel"])      # km/s radial vel
    gas_frac     = np.array(pdata["sod_halo_bin_gas_fraction"]) # cumulative gas fraction
    zmet         = np.array(pdata["sod_halo_bin_zmet"])         # metallicity (Zsun)
    cdm_frac     = np.array(pdata["sod_halo_bin_cdm_fraction"]) # CDM fraction
    star_frac    = np.array(pdata["sod_halo_bin_star_fraction"]) # stellar fraction

    # Profile-halo linkage
    linked = f["halo_properties/data_linked"]
    prof_idx = np.array(linked["sod_profile_idx"])  # profile row for each halo

print(f"  N halos:       {len(fof_mass):,}")
print(f"  N profile rows: {radius.shape[0]:,}")
print(f"  N radial bins:  {radius.shape[1]}")
print(f"  FoF mass range: {fof_mass.min():.2e} – {fof_mass.max():.2e} Msun/h")
print(f"  M500c range:    {m500c.min():.2e} – {m500c.max():.2e} Msun/h")

# ------------------------------------------------------------------ random 10 ---
# Choose 10 halos spread across log-mass space to get diversity
logM = np.log10(fof_mass)
valid = np.where((r500c > 0) & np.all(gas_ne > 0, axis=1))[0]
print(f"  Valid halos (non-zero ne, r500c): {len(valid):,}")

# Stratified sampling across 10 mass bins
bins = np.percentile(logM[valid], np.linspace(0, 100, 11))
chosen = []
for i in range(10):
    mask = (logM[valid] >= bins[i]) & (logM[valid] < bins[i+1])
    candidates = valid[mask]
    if len(candidates) > 0:
        idx = np.random.choice(candidates)
        chosen.append(idx)
    else:
        chosen.append(np.random.choice(valid))
chosen = np.array(chosen)
print(f"  Chosen halos (indices): {chosen}")
print(f"  Their log10(FoF mass):  {logM[chosen]}")
print(f"  Their R500c (Mpc/h):    {r500c[chosen]}")

# ------------------------------------------------------------------ colours ---
cmap = cm.get_cmap("plasma", 10)
colors = [cmap(i) for i in range(10)]
labels = [f"H{i+1}: lg M={logM[c]:.2f}" for i, c in enumerate(chosen)]

# ------------------------------------------------------------------ profile normalisation ---
# Get profile rows for chosen halos
prows = prof_idx[chosen]  # profile index for each chosen halo

def get_prof(arr, indices):
    """arr is (N_halos, N_bins); indices are profile row indices."""
    return arr[indices]  # direct indexing since prof_idx is 1-to-1

def r_r500(i_halo, halo_idx):
    """Normalise radial bins by R500c of the halo."""
    r = radius[prof_idx[halo_idx]]
    return r / r500c[halo_idx]

# ------------------------------------------------------------------ profiles ---
# 10 profile types, one panel each (2 rows x 5 cols)
profile_specs = [
    ("Enclosed Mass",           bin_mass,     r"$M(<r)\ [M_\odot/h]$",   False, "bin_mass"),
    ("Gas Electron Density",    gas_ne,       r"$n_e\ [\mathrm{cm}^{-3}]$", True,  "gas_ne"),
    ("Gas Temperature",         gas_temp,     r"$T\ [\mathrm{keV}]$",     False, "gas_temp"),
    ("Gas Entropy",             gas_entropy,  r"$K\ [\mathrm{keV\,cm^2}]$", True, "gas_entropy"),
    ("Thermal Pressure",        gas_pthermal, r"$P_\mathrm{th}\ [\mathrm{keV\,cm^{-3}}]$", True, "gas_pthermal"),
    ("X-ray Bolometric Lumin.", xray_lumin,   r"$L_X\ [\mathrm{erg/s}]$",  True,  "xray_lumin"),
    ("Radial Velocity",         rad_vel,      r"$v_r\ [\mathrm{km/s}]$",  False, "rad_vel"),
    ("Gas Fraction",            gas_frac,     r"$f_\mathrm{gas}(<r)$",    False, "gas_frac"),
    ("Metallicity",             zmet,         r"$Z\ [Z_\odot]$",           False, "zmet"),
    ("CDM Fraction",            cdm_frac,     r"$f_\mathrm{CDM}(<r)$",    False, "cdm_frac"),
]

fig, axes = plt.subplots(2, 5, figsize=(22, 9))
axes = axes.flatten()
fig.suptitle("Frontier-E: 10 Radial Profiles for 10 Random Halos (z=0)", fontsize=14, y=1.01)

for ax_idx, (title, prof_arr, ylabel, do_log, key) in enumerate(profile_specs):
    ax = axes[ax_idx]
    for i, halo_idx in enumerate(chosen):
        r_norm = r_r500(i, halo_idx)            # r / R500c
        yvals  = prof_arr[prof_idx[halo_idx]]   # profile for this halo

        # Mask zeros/negatives for log plots
        if do_log:
            mask = yvals > 0
            if mask.sum() > 2:
                ax.semilogy(r_norm[mask], yvals[mask], color=colors[i],
                            lw=1.5, alpha=0.8, label=labels[i] if ax_idx == 0 else "")
        else:
            ax.plot(r_norm, yvals, color=colors[i],
                    lw=1.5, alpha=0.8, label=labels[i] if ax_idx == 0 else "")

    ax.set_xlabel(r"$r / R_{500c}$", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlim(0, 2.0)
    ax.axvline(1.0, color="gray", ls="--", lw=0.8, alpha=0.6)  # mark R500c
    ax.grid(True, alpha=0.3, lw=0.5)

# Legend in first panel
axes[0].legend(loc="upper right", fontsize=6.5, ncol=1, framealpha=0.7)

plt.tight_layout()
outpath = os.path.join(EXPERIMENT_DIR, "phase1_10profiles_10halos.png")
fig.savefig(outpath, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"\nSaved: {outpath}")

# ------------------------------------------------------------------ mass histogram ---
fig2, ax2 = plt.subplots(figsize=(7, 4))
ax2.hist(np.log10(fof_mass), bins=60, color="steelblue", alpha=0.8, edgecolor="white", lw=0.5)
for i, hi in enumerate(chosen):
    ax2.axvline(logM[hi], color=colors[i], lw=1.5, ls="-", alpha=0.9)
ax2.set_xlabel(r"$\log_{10}(M_\mathrm{FoF}\ [M_\odot/h])$", fontsize=12)
ax2.set_ylabel("Number of halos", fontsize=12)
ax2.set_title("Frontier-E z=0 Halo Mass Function (N=10,000)\nVertical lines: 10 randomly selected halos", fontsize=11)
ax2.grid(True, alpha=0.3)
plt.tight_layout()
outpath2 = os.path.join(EXPERIMENT_DIR, "phase1_mass_histogram.png")
fig2.savefig(outpath2, dpi=150, bbox_inches="tight")
plt.close(fig2)
print(f"Saved: {outpath2}")

# ------------------------------------------------------------------ save results ---
results = {
    "catalog_path": CATALOG,
    "run_id": "5ee0c456-c6a5-4265-97e1-1f66f69e20d4",
    "n_halos": int(len(fof_mass)),
    "n_profile_bins": int(radius.shape[1]),
    "fof_mass_min": float(fof_mass.min()),
    "fof_mass_max": float(fof_mass.max()),
    "m500c_min": float(m500c.min()),
    "m500c_max": float(m500c.max()),
    "chosen_halo_indices": chosen.tolist(),
    "chosen_halo_logM": logM[chosen].tolist(),
    "chosen_halo_r500c": r500c[chosen].tolist(),
    "profile_types": [p[0] for p in profile_specs],
    "plots": ["phase1_10profiles_10halos.png", "phase1_mass_histogram.png"]
}
with open(os.path.join(EXPERIMENT_DIR, "phase1_results.json"), "w") as f:
    json.dump(results, f, indent=2)

print("\n=== Phase 1 Summary ===")
print(f"  Catalog: Frontier-E hydro, z=0, N=10,000 halos")
print(f"  Profile bins: 51 radial bins per halo (0.0125 to ~2 Mpc/h)")
print(f"  10 chosen halos span log10(M) = {logM[chosen].min():.2f} – {logM[chosen].max():.2f}")
print(f"  10 profile types plotted (relevant for relaxed/unrelaxed)")
print("Done.")
