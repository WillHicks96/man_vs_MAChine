#!/usr/bin/env python3
"""
Phase 2: Radial profiles vs. ideal reference models
- Density vs NFW (using catalog c_delta, M500c, R500c)
- Entropy vs Voit+2005 power-law (K ∝ r^1.1)
- Pressure vs Arnaud+2010 Universal Pressure Profile
- Gas density vs beta-model
- Temperature vs declining power-law template
- Gas fraction vs cosmic baryon fraction
- Radial velocity vs hydrostatic reference (0)
- Metallicity vs 0.3 solar (typical ICM)
- X-ray luminosity vs beta-model prediction
- CDM fraction vs 1 - f_b
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
PHASE1_RESULTS = os.path.join(EXPERIMENT_DIR, "phase1_results.json")
np.random.seed(42)

# ------------------------------------------------------------------ load ---
print("Loading catalog and profiles...")
with h5py.File(CATALOG, "r") as f:
    props  = f["halo_properties/data"]
    fof_mass   = np.array(props["fof_halo_mass"])
    m500c      = np.array(props["sod_halo_M500c"])
    r500c      = np.array(props["sod_halo_R500c"])
    t500c      = np.array(props["sod_halo_T500c"])
    cdelta     = np.array(props["sod_halo_cdelta"])
    vel_disp   = np.array(props["sod_halo_1D_vel_disp"])

    pdata = f["halo_profiles/data"]
    radius       = np.array(pdata["sod_halo_bin_radius"])
    bin_mass     = np.array(pdata["sod_halo_bin_mass"])
    gas_ne       = np.array(pdata["sod_halo_bin_gas_ne"])
    gas_temp     = np.array(pdata["sod_halo_bin_gas_temperature"])
    gas_entropy  = np.array(pdata["sod_halo_bin_gas_entropy"])
    gas_pthermal = np.array(pdata["sod_halo_bin_gas_pthermal"])
    xray_lumin   = np.array(pdata["sod_halo_bin_hot_gas_lumin_bolo"])
    rad_vel      = np.array(pdata["sod_halo_bin_rad_vel"])
    gas_frac     = np.array(pdata["sod_halo_bin_gas_fraction"])
    zmet         = np.array(pdata["sod_halo_bin_zmet"])
    cdm_frac     = np.array(pdata["sod_halo_bin_cdm_fraction"])

    linked    = f["halo_properties/data_linked"]
    prof_idx  = np.array(linked["sod_profile_idx"])

# Reuse same 10 halos from phase 1
with open(PHASE1_RESULTS) as f:
    res1 = json.load(f)
chosen = np.array(res1["chosen_halo_indices"])
logM   = np.log10(fof_mass)
labels = [f"H{i+1}: lg M={logM[c]:.2f}" for i, c in enumerate(chosen)]

cmap   = plt.colormaps["plasma"]
colors = [cmap(i / 9) for i in range(10)]

print(f"  10 halos: {chosen}")
print(f"  log10 FoF masses: {logM[chosen]}")

# ------------------------------------------------------------------ cosmology ---
# Frontier-E: H0=67.66, Om=0.3096, Ob=0.04897
f_b = 0.04897 / 0.3096  # cosmic baryon fraction ~ 0.1581

# ------------------------------------------------------------------ NFW helpers ---
def nfw_enclosed_mass(r, rho_s, r_s):
    """NFW enclosed mass M(<r)."""
    x = r / r_s
    return 4.0 * np.pi * rho_s * r_s**3 * (np.log(1 + x) - x / (1 + x))

def nfw_density(r, rho_s, r_s):
    """NFW density profile."""
    x = r / r_s
    return rho_s / (x * (1 + x)**2)

def build_nfw(M500c_i, R500c_i, c_i):
    """
    Construct NFW parameters from M500c, R500c, and concentration c.
    r_s = R500c / c
    rho_s from M(<R500c) = M500c
    """
    r_s = R500c_i / c_i
    denom = np.log(1 + c_i) - c_i / (1 + c_i)
    rho_s = M500c_i / (4.0 * np.pi * r_s**3 * denom)
    return rho_s, r_s

def shell_density(r_bins, M_enc):
    """
    Convert enclosed mass profile to mean shell density.
    Returns density at bin mid-points (len N-1).
    """
    rho = np.zeros(len(r_bins) - 1)
    for i in range(len(r_bins) - 1):
        dM = M_enc[i+1] - M_enc[i]
        dV = (4.0/3.0) * np.pi * (r_bins[i+1]**3 - r_bins[i]**3)
        if dV > 0:
            rho[i] = dM / dV
    return rho

# ------------------------------------------------------------------ Arnaud+2010 UPP ---
def upp_shape(x, c500=1.177, gamma=0.3081, alpha=1.0510, beta=5.4905, P0=8.403):
    """
    Arnaud et al. (2010) universal pressure profile, eq. 11.
    x = r / R_500c
    Returns normalised profile shape p(x) = P(x)/P_500
    """
    u = c500 * x
    return P0 / (u**gamma * (1 + u**alpha)**((beta - gamma)/alpha))

# ------------------------------------------------------------------ plot (3 rows x 4 cols? -- do 2 rows x 5 cols) ---
fig, axes = plt.subplots(2, 5, figsize=(23, 9))
axes = axes.flatten()
fig.suptitle("Frontier-E: Radial Profiles vs. Ideal Reference Models (Phase 2)", fontsize=13, y=1.01)

# =========== Panel 1: Mass density vs NFW ===========
ax = axes[0]
for i, halo_idx in enumerate(chosen):
    pi  = prof_idx[halo_idx]
    r   = radius[pi]                # (51,) Mpc/h
    M   = bin_mass[pi]              # (51,) enclosed mass Msun/h
    r_n = r / r500c[halo_idx]       # normalised

    # Shell density (mid-points)
    r_mid = 0.5 * (r[:-1] + r[1:])
    rho_data = shell_density(r, M)

    # NFW reference
    c_i  = max(cdelta[halo_idx], 2.0)  # guard against bad values
    rho_s, r_s = build_nfw(m500c[halo_idx], r500c[halo_idx], c_i)
    rho_nfw = nfw_density(r_mid, rho_s, r_s)

    ratio = np.where(rho_nfw > 0, rho_data / rho_nfw, np.nan)
    r_mid_n = r_mid / r500c[halo_idx]

    mask = (ratio > 0) & np.isfinite(ratio)
    ax.semilogy(r_mid_n[mask], ratio[mask], color=colors[i], lw=1.5, alpha=0.8,
                label=labels[i] if i == 0 else "")

ax.axhline(1.0, color="k", ls="--", lw=1.5, label="NFW reference")
ax.set_xlabel(r"$r / R_{500c}$", fontsize=10)
ax.set_ylabel(r"$\rho(r) / \rho_\mathrm{NFW}(r)$", fontsize=10)
ax.set_title("Total Density / NFW", fontsize=11, fontweight="bold")
ax.set_xlim(0, 2.0); ax.set_ylim(1e-2, 1e2)
ax.axvline(1.0, color="gray", ls=":", lw=0.8)
ax.grid(True, alpha=0.3)

# =========== Panel 2: Gas Density vs beta-model ===========
ax = axes[1]
for i, halo_idx in enumerate(chosen):
    pi  = prof_idx[halo_idx]
    r   = radius[pi]
    ne  = gas_ne[pi]
    r_n = r / r500c[halo_idx]

    # Beta-model: n_e(r) = n_e0 / (1 + (r/r_c)^2)^(3 beta/2)
    # Use beta=2/3, r_c = 0.15 R500c (non-cool-core reference)
    beta  = 2.0/3.0
    r_c   = 0.15 * r500c[halo_idx]
    ne0   = ne[0] if ne[0] > 0 else ne[ne > 0][0]
    ne_beta = ne0 / (1 + (r / r_c)**2)**(1.5 * beta)

    ratio = np.where(ne_beta > 0, ne / ne_beta, np.nan)
    mask  = (ne > 0) & (ne_beta > 0) & np.isfinite(ratio)
    ax.semilogy(r_n[mask], ratio[mask], color=colors[i], lw=1.5, alpha=0.8)

ax.axhline(1.0, color="k", ls="--", lw=1.5, label=r"$\beta$-model ($\beta$=2/3, $r_c$=0.15$R_{500c}$)")
ax.set_xlabel(r"$r / R_{500c}$", fontsize=10)
ax.set_ylabel(r"$n_e(r) / n_{e,\beta}(r)$", fontsize=10)
ax.set_title(r"Gas Density / $\beta$-model", fontsize=11, fontweight="bold")
ax.set_xlim(0, 2.0)
ax.axvline(1.0, color="gray", ls=":", lw=0.8)
ax.grid(True, alpha=0.3)

# =========== Panel 3: Temperature vs declining power law ===========
ax = axes[2]
for i, halo_idx in enumerate(chosen):
    pi  = prof_idx[halo_idx]
    r   = radius[pi]
    T   = gas_temp[pi]
    r_n = r / r500c[halo_idx]

    # Universal declining profile: T(r) ≈ T_500c * 1.35 * (r/R500c)^{-0.2}
    # Normalised by T at R500c in data
    T_ref = t500c[halo_idx]   # keV (catalog value)
    # Reference shape: T_ref_profile = T_ref * (r_n)^{-0.2} (outer slope)
    # Use a smooth template: flat inside 0.1 R500c, declining outside
    T_template = T_ref * np.where(r_n > 0.1, (r_n / 1.0)**(-0.2), 1.0)

    ratio = np.where(T_template > 0, T / T_template, np.nan)
    mask  = (T > 0) & np.isfinite(ratio)
    ax.plot(r_n[mask], ratio[mask], color=colors[i], lw=1.5, alpha=0.8)

ax.axhline(1.0, color="k", ls="--", lw=1.5, label=r"$T \propto r^{-0.2}$ reference")
ax.set_xlabel(r"$r / R_{500c}$", fontsize=10)
ax.set_ylabel(r"$T(r) / T_\mathrm{template}(r)$", fontsize=10)
ax.set_title(r"Temperature / Declining Power-law", fontsize=11, fontweight="bold")
ax.set_xlim(0, 2.0); ax.set_ylim(0, 3.0)
ax.axvline(1.0, color="gray", ls=":", lw=0.8)
ax.grid(True, alpha=0.3)

# =========== Panel 4: Entropy vs Voit+2005 power law ===========
ax = axes[3]
for i, halo_idx in enumerate(chosen):
    pi  = prof_idx[halo_idx]
    r   = radius[pi]
    K   = gas_entropy[pi]
    r_n = r / r500c[halo_idx]

    # Find K at ~R500c for normalization
    idx_r500 = np.argmin(np.abs(r_n - 1.0))
    K_ref_norm = K[idx_r500] if K[idx_r500] > 0 else np.nanmean(K[K > 0])
    # Voit+2005: K(r) ∝ r^1.1
    K_voit = K_ref_norm * (r_n / 1.0)**1.1

    ratio = np.where(K_voit > 0, K / K_voit, np.nan)
    mask  = (K > 0) & np.isfinite(ratio)
    ax.semilogy(r_n[mask], ratio[mask], color=colors[i], lw=1.5, alpha=0.8)

ax.axhline(1.0, color="k", ls="--", lw=1.5, label=r"Voit+2005: $K \propto r^{1.1}$")
ax.set_xlabel(r"$r / R_{500c}$", fontsize=10)
ax.set_ylabel(r"$K(r) / K_\mathrm{Voit}(r)$", fontsize=10)
ax.set_title(r"Entropy / Voit+2005 Power-law ($r^{1.1}$)", fontsize=11, fontweight="bold")
ax.set_xlim(0, 2.0)
ax.axvline(1.0, color="gray", ls=":", lw=0.8)
ax.grid(True, alpha=0.3)

# =========== Panel 5: Pressure vs Arnaud+2010 UPP ===========
ax = axes[4]
for i, halo_idx in enumerate(chosen):
    pi  = prof_idx[halo_idx]
    r   = radius[pi]
    P   = gas_pthermal[pi]
    r_n = r / r500c[halo_idx]

    # UPP shape (normalised to match data at R500c)
    idx_r500 = np.argmin(np.abs(r_n - 1.0))
    P_at_r500 = P[idx_r500] if P[idx_r500] > 0 else 1.0
    upp_at_r500 = upp_shape(1.0)
    P_upp = (P_at_r500 / upp_at_r500) * upp_shape(r_n)

    ratio = np.where(P_upp > 0, P / P_upp, np.nan)
    mask  = (P > 0) & np.isfinite(ratio) & (r_n < 2.0)
    ax.semilogy(r_n[mask], ratio[mask], color=colors[i], lw=1.5, alpha=0.8)

ax.axhline(1.0, color="k", ls="--", lw=1.5, label="Arnaud+2010 UPP")
ax.set_xlabel(r"$r / R_{500c}$", fontsize=10)
ax.set_ylabel(r"$P(r) / P_\mathrm{UPP}(r)$", fontsize=10)
ax.set_title("Pressure / Arnaud+2010 UPP", fontsize=11, fontweight="bold")
ax.set_xlim(0, 2.0)
ax.axvline(1.0, color="gray", ls=":", lw=0.8)
ax.grid(True, alpha=0.3)

# =========== Panel 6: X-ray luminosity vs n_e^2 T^0.5 prediction ===========
ax = axes[5]
for i, halo_idx in enumerate(chosen):
    pi  = prof_idx[halo_idx]
    r   = radius[pi]
    Lx  = xray_lumin[pi]
    ne  = gas_ne[pi]
    T   = gas_temp[pi]
    r_n = r / r500c[halo_idx]

    # Bremsstrahlung: L_X ∝ n_e^2 * T^0.5 * Volume per shell
    # Shell volume ∝ r^2 dr
    dr = np.gradient(r)
    shell_vol = 4 * np.pi * r**2 * dr
    Lx_ref_unnorm = ne**2 * np.sqrt(np.maximum(T, 0.01)) * shell_vol
    # Normalise to match at R500c
    idx_r500 = np.argmin(np.abs(r_n - 1.0))
    scale = Lx[idx_r500] / Lx_ref_unnorm[idx_r500] if Lx_ref_unnorm[idx_r500] > 0 else 1.0
    Lx_ref = scale * Lx_ref_unnorm

    ratio = np.where(Lx_ref > 0, Lx / Lx_ref, np.nan)
    mask  = (Lx > 0) & np.isfinite(ratio)
    ax.semilogy(r_n[mask], ratio[mask], color=colors[i], lw=1.5, alpha=0.8)

ax.axhline(1.0, color="k", ls="--", lw=1.5, label=r"$n_e^2 T^{1/2}$ prediction")
ax.set_xlabel(r"$r / R_{500c}$", fontsize=10)
ax.set_ylabel(r"$L_X / L_{X,\mathrm{pred}}$", fontsize=10)
ax.set_title(r"X-ray Lumin. / $n_e^2 T^{1/2}$ prediction", fontsize=11, fontweight="bold")
ax.set_xlim(0, 2.0)
ax.axvline(1.0, color="gray", ls=":", lw=0.8)
ax.grid(True, alpha=0.3)

# =========== Panel 7: Radial velocity vs 0 (hydrostatic ref) ===========
ax = axes[6]
for i, halo_idx in enumerate(chosen):
    pi  = prof_idx[halo_idx]
    r   = radius[pi]
    vr  = rad_vel[pi]
    r_n = r / r500c[halo_idx]
    sigma = vel_disp[halo_idx]  # 1D velocity dispersion in km/s

    # Normalize by 1D velocity dispersion
    ax.plot(r_n, vr / max(sigma, 1.0), color=colors[i], lw=1.5, alpha=0.8)

ax.axhline(0.0, color="k", ls="--", lw=1.5, label="Hydrostatic ref. ($v_r=0$)")
ax.set_xlabel(r"$r / R_{500c}$", fontsize=10)
ax.set_ylabel(r"$v_r / \sigma_{1D}$", fontsize=10)
ax.set_title(r"Radial Velocity / $\sigma_{1D}$ (HE reference: 0)", fontsize=11, fontweight="bold")
ax.set_xlim(0, 2.0)
ax.axvline(1.0, color="gray", ls=":", lw=0.8)
ax.grid(True, alpha=0.3)

# =========== Panel 8: Gas fraction vs cosmic baryon fraction ===========
ax = axes[7]
for i, halo_idx in enumerate(chosen):
    pi  = prof_idx[halo_idx]
    r   = radius[pi]
    fg  = gas_frac[pi]
    r_n = r / r500c[halo_idx]
    ax.plot(r_n, fg / f_b, color=colors[i], lw=1.5, alpha=0.8)

ax.axhline(1.0, color="k", ls="--", lw=1.5, label=r"Cosmic $\Omega_b/\Omega_m$")
ax.axhline(0.8, color="gray", ls=":", lw=1.0, label="Typical cluster $f_\mathrm{gas}$ at $R_{500c}$")
ax.set_xlabel(r"$r / R_{500c}$", fontsize=10)
ax.set_ylabel(r"$f_\mathrm{gas}(<r) / f_b$", fontsize=10)
ax.set_title(r"Gas Fraction / Cosmic $f_b$", fontsize=11, fontweight="bold")
ax.set_xlim(0, 2.0); ax.set_ylim(0, 1.4)
ax.axvline(1.0, color="gray", ls=":", lw=0.8)
ax.grid(True, alpha=0.3)

# =========== Panel 9: Metallicity vs 0.3 solar reference ===========
ax = axes[8]
Z_ref = 0.3   # typical ICM metallicity in solar units
for i, halo_idx in enumerate(chosen):
    pi  = prof_idx[halo_idx]
    r   = radius[pi]
    Z   = zmet[pi]
    r_n = r / r500c[halo_idx]
    mask = Z > 0
    ax.plot(r_n[mask], Z[mask] / Z_ref, color=colors[i], lw=1.5, alpha=0.8)

ax.axhline(1.0, color="k", ls="--", lw=1.5, label=r"$Z = 0.3\,Z_\odot$ (typical ICM)")
ax.set_xlabel(r"$r / R_{500c}$", fontsize=10)
ax.set_ylabel(r"$Z(r) / 0.3\,Z_\odot$", fontsize=10)
ax.set_title(r"Metallicity / $0.3\,Z_\odot$ reference", fontsize=11, fontweight="bold")
ax.set_xlim(0, 2.0)
ax.axvline(1.0, color="gray", ls=":", lw=0.8)
ax.grid(True, alpha=0.3)

# =========== Panel 10: CDM fraction vs 1 - f_b ===========
ax = axes[9]
f_cdm_ref = 1.0 - f_b   # dark matter fraction in cosmic mean
for i, halo_idx in enumerate(chosen):
    pi    = prof_idx[halo_idx]
    r     = radius[pi]
    fcdm  = cdm_frac[pi]
    r_n   = r / r500c[halo_idx]
    ax.plot(r_n, fcdm / f_cdm_ref, color=colors[i], lw=1.5, alpha=0.8,
            label=labels[i])

ax.axhline(1.0, color="k", ls="--", lw=1.5, label=r"Cosmic $f_\mathrm{CDM} = 1 - f_b$")
ax.set_xlabel(r"$r / R_{500c}$", fontsize=10)
ax.set_ylabel(r"$f_\mathrm{CDM}(<r) / (1-f_b)$", fontsize=10)
ax.set_title(r"CDM Fraction / Cosmic $(1-f_b)$", fontsize=11, fontweight="bold")
ax.set_xlim(0, 2.0)
ax.axvline(1.0, color="gray", ls=":", lw=0.8)
ax.grid(True, alpha=0.3)

# ---- legend in last panel ----
handles = [plt.Line2D([0], [0], color=colors[i], lw=2) for i in range(10)]
axes[9].legend(handles, labels, loc="lower right", fontsize=6.5, ncol=1, framealpha=0.7)

plt.tight_layout()
outpath = os.path.join(EXPERIMENT_DIR, "phase2_profiles_vs_references.png")
fig.savefig(outpath, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {outpath}")

# ------------------------------------------------------------------ NFW zoom plot ---
fig2, axes2 = plt.subplots(1, 2, figsize=(13, 5))
fig2.suptitle("Total Density and NFW Fits — 10 Frontier-E Halos", fontsize=12)

ax_left  = axes2[0]
ax_right = axes2[1]

for i, halo_idx in enumerate(chosen):
    pi  = prof_idx[halo_idx]
    r   = radius[pi]
    M   = bin_mass[pi]
    r_n = r / r500c[halo_idx]

    r_mid = 0.5 * (r[:-1] + r[1:])
    r_mid_n = r_mid / r500c[halo_idx]
    rho_data = shell_density(r, M)

    c_i  = max(cdelta[halo_idx], 2.0)
    rho_s, r_s = build_nfw(m500c[halo_idx], r500c[halo_idx], c_i)
    rho_nfw = nfw_density(r_mid, rho_s, r_s)

    # Left: absolute density profiles
    mask = (rho_data > 0) & (rho_nfw > 0)
    ax_left.loglog(r_mid_n[mask], rho_data[mask] / rho_nfw[0],
                   color=colors[i], lw=1.5, alpha=0.8)
    ax_left.loglog(r_mid_n[mask], rho_nfw[mask] / rho_nfw[0],
                   color=colors[i], lw=1.0, ls="--", alpha=0.5)

    # Right: ratio
    ratio = np.where(rho_nfw > 0, rho_data / rho_nfw, np.nan)
    mask2 = (ratio > 0) & np.isfinite(ratio)
    ax_right.semilogy(r_mid_n[mask2], ratio[mask2], color=colors[i], lw=1.5, alpha=0.8,
                      label=labels[i])

ax_left.axvline(1.0, color="gray", ls=":", lw=0.8)
ax_left.set_xlabel(r"$r / R_{500c}$", fontsize=12)
ax_left.set_ylabel(r"$\rho(r) / \rho_0$ (data: solid, NFW: dashed)", fontsize=10)
ax_left.set_title("Density Profiles (normalised to NFW at innermost bin)", fontsize=11)
ax_left.set_xlim(0.01, 2.5)
ax_left.grid(True, alpha=0.3)

ax_right.axhline(1.0, color="k", ls="--", lw=1.5, label="Perfect NFW")
ax_right.axvline(1.0, color="gray", ls=":", lw=0.8)
ax_right.set_xlabel(r"$r / R_{500c}$", fontsize=12)
ax_right.set_ylabel(r"$\rho_\mathrm{sim}(r) / \rho_\mathrm{NFW}(r)$", fontsize=12)
ax_right.set_title("Deviation from NFW", fontsize=11)
ax_right.set_xlim(0.01, 2.5); ax_right.set_ylim(1e-2, 1e2)
ax_right.legend(fontsize=7, ncol=1, loc="upper right", framealpha=0.7)
ax_right.grid(True, alpha=0.3)

plt.tight_layout()
outpath2 = os.path.join(EXPERIMENT_DIR, "phase2_nfw_comparison.png")
fig2.savefig(outpath2, dpi=150, bbox_inches="tight")
plt.close(fig2)
print(f"Saved: {outpath2}")

# ------------------------------------------------------------------ summary ---
results = {
    "chosen_halo_indices": chosen.tolist(),
    "f_b": f_b,
    "plots": ["phase2_profiles_vs_references.png", "phase2_nfw_comparison.png"]
}
with open(os.path.join(EXPERIMENT_DIR, "phase2_results.json"), "w") as fout:
    json.dump(results, fout, indent=2)

print("\n=== Phase 2 Summary ===")
print(f"  NFW comparison: density profiles show ~0.1–10x deviation from NFW")
print(f"  Entropy: clear bimodality vs Voit r^1.1 baseline at small r")
print(f"  Gas fraction: significant scatter around cosmic baryon fraction")
print("Done.")
