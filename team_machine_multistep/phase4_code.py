#!/usr/bin/env python3
"""
Phase 4: Relaxed/unrelaxed criteria — COM offset vs profile deviation metrics
For ALL 10,000 Frontier-E halos at z=0.

Relaxation proxy (traditional, DM-based):
  delta_1 = |FoF_COM - FoF_center| / R_200m       (COM-to-potential-minimum)
  delta_2 = |SOD_DM_COM - SOD_gas_COM| / R_500c   (DM-gas centroid offset)

Profile deviation metrics (from profile fits):
  K_0          = gas entropy at innermost valid bin (keV cm^2)
  n_entropy    = power-law slope fit to K(r) vs (r/R500c), r > 0.05 R500c
  c_fit        = best-fit NFW concentration from total density profile (1-param fit)
  c_ratio      = c_fit / c_catalog (baryonic concentration boost)
  nfw_scatter  = RMS log-residual of total density vs best-fit NFW
"""
import os, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import h5py
from scipy.optimize import minimize_scalar

# ------------------------------------------------------------------ paths ---
PROJECT_ROOT = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments"
EXPERIMENT_DIR = os.path.join(PROJECT_ROOT, "runs", "research_20260218_105441")
CATALOG = "/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5"
np.random.seed(42)

# ------------------------------------------------------------------ load catalog ---
print("Loading catalog…")
with h5py.File(CATALOG, "r") as f:
    props = f["halo_properties/data"]
    fof_mass   = np.array(props["fof_halo_mass"])     # Msun/h
    m500c      = np.array(props["sod_halo_M500c"])
    r500c      = np.array(props["sod_halo_R500c"])    # Mpc/h
    r200m      = np.array(props["sod_halo_R200m"])
    cdelta     = np.array(props["sod_halo_cdelta"])

    # COM-offset ingredients
    fof_cx  = np.array(props["fof_halo_center_x"])    # potential minimum (density peak)
    fof_cy  = np.array(props["fof_halo_center_y"])
    fof_cz  = np.array(props["fof_halo_center_z"])
    fof_cx2 = np.array(props["fof_halo_com_x"])       # FoF center of mass
    fof_cy2 = np.array(props["fof_halo_com_y"])
    fof_cz2 = np.array(props["fof_halo_com_z"])
    sod_dm_x = np.array(props["sod_halo_com_x_dm"])  # SOD DM COM
    sod_dm_y = np.array(props["sod_halo_com_y_dm"])
    sod_dm_z = np.array(props["sod_halo_com_z_dm"])
    sod_gas_x = np.array(props["sod_halo_com_x_gas"]) # SOD gas COM
    sod_gas_y = np.array(props["sod_halo_com_y_gas"])
    sod_gas_z = np.array(props["sod_halo_com_z_gas"])

    pdata = f["halo_profiles/data"]
    radius       = np.array(pdata["sod_halo_bin_radius"])
    bin_mass     = np.array(pdata["sod_halo_bin_mass"])
    gas_entropy  = np.array(pdata["sod_halo_bin_gas_entropy"])

    prof_idx = np.array(f["halo_properties/data_linked"]["sod_profile_idx"])

N = len(fof_mass)
logM = np.log10(fof_mass)
print(f"  Loaded {N:,} halos")

# ------------------------------------------------------------------ COM offsets ---
print("Computing COM offsets…")

# delta_1: FoF COM vs FoF center (potential minimum), normalised by R_200m
d1x = fof_cx2 - fof_cx
d1y = fof_cy2 - fof_cy
d1z = fof_cz2 - fof_cz
d1_abs = np.sqrt(d1x**2 + d1y**2 + d1z**2)
delta_1 = np.where(r200m > 0, d1_abs / r200m, np.nan)

# delta_2: SOD DM COM vs SOD gas COM, normalised by R_500c
d2x = sod_dm_x - sod_gas_x
d2y = sod_dm_y - sod_gas_y
d2z = sod_dm_z - sod_gas_z
d2_abs = np.sqrt(d2x**2 + d2y**2 + d2z**2)
delta_2 = np.where(r500c > 0, d2_abs / r500c, np.nan)

print(f"  delta_1 range: {np.nanpercentile(delta_1, [5,50,95])}")
print(f"  delta_2 range: {np.nanpercentile(delta_2, [5,50,95])}")

# ------------------------------------------------------------------ profile metrics ---
print("Computing profile metrics for all halos (this may take a few minutes)…")

K_0      = np.full(N, np.nan)
n_entropy= np.full(N, np.nan)
c_fit    = np.full(N, np.nan)
nfw_scat = np.full(N, np.nan)

def shell_density_fast(r_bins, M_enc):
    """Vectorized shell density (N-1 values)."""
    dM = np.diff(np.maximum(M_enc, 0))
    r_b, r_a = r_bins[1:], r_bins[:-1]
    dV = (4./3.) * np.pi * (r_b**3 - r_a**3)
    return dM / np.maximum(dV, 1e-30)

def nfw_cost_1d(c_try, r_mid, rho_data, M500c_i, R500c_i):
    """1-parameter NFW cost: fit c only, rho_s set analytically."""
    r_s   = R500c_i / c_try
    denom = np.log(1.0 + c_try) - c_try / (1.0 + c_try)
    rho_s = M500c_i / (4.0 * np.pi * r_s**3 * denom)
    x     = r_mid / r_s
    rho_nfw = rho_s / (x * (1.0 + x)**2)
    valid = (rho_data > 0) & (rho_nfw > 0)
    if valid.sum() < 4:
        return 1e9
    return np.mean((np.log(rho_data[valid]) - np.log(rho_nfw[valid]))**2)

n_fail = 0
for i in range(N):
    pi  = prof_idx[i]
    r   = radius[pi]
    r_n = r / r500c[i] if r500c[i] > 0 else np.ones_like(r)
    K   = gas_entropy[pi]

    # --- central entropy K_0 (innermost bin with K > 0) ---
    valid_K = np.where(K > 0)[0]
    if len(valid_K) > 0:
        K_0[i] = K[valid_K[0]]

    # --- entropy slope (polyfit on log-log) ---
    mask_K = (K > 0) & (r_n > 0.05)
    if mask_K.sum() >= 4:
        try:
            slope, intercept = np.polyfit(np.log(r_n[mask_K]), np.log(K[mask_K]), 1)
            n_entropy[i] = slope
        except Exception:
            pass

    # --- NFW concentration fit (1D optimization) ---
    if r500c[i] <= 0 or m500c[i] <= 0:
        continue
    M   = bin_mass[pi]
    r_mid = 0.5 * (r[:-1] + r[1:])
    rho = shell_density_fast(r, M)
    valid_rho = (rho > 0) & (r_mid > 0)
    if valid_rho.sum() < 5:
        continue

    try:
        result = minimize_scalar(
            nfw_cost_1d,
            bounds=(0.5, 40.0), method="bounded",
            args=(r_mid[valid_rho], rho[valid_rho], m500c[i], r500c[i]))
        if result.success:
            c_fit[i] = result.x
            # also compute scatter at best-fit c
            r_s   = r500c[i] / result.x
            denom = np.log(1.0 + result.x) - result.x / (1.0 + result.x)
            rho_s = m500c[i] / (4.0 * np.pi * r_s**3 * denom)
            x     = r_mid[valid_rho] / r_s
            rho_nfw = rho_s / (x * (1.0 + x)**2)
            nfw_scat[i] = np.std(np.log(rho[valid_rho]) - np.log(rho_nfw))
    except Exception:
        n_fail += 1

    if i > 0 and i % 1000 == 0:
        print(f"  {i}/{N} halos processed…")

c_ratio = c_fit / np.maximum(cdelta, 0.1)
print(f"  Done. {n_fail} NFW fit failures.")
print(f"  K_0 range (valid): {np.nanpercentile(K_0[K_0>0], [5,50,95])}")
print(f"  n_entropy range:   {np.nanpercentile(n_entropy, [5,50,95])}")
print(f"  c_fit range:       {np.nanpercentile(c_fit[c_fit>0], [5,50,95])}")
print(f"  c_ratio range:     {np.nanpercentile(c_ratio[c_ratio>0], [5,50,95])}")

# ------------------------------------------------------------------ masks for valid halos ---
good = (
    np.isfinite(delta_1) & (delta_1 > 0) &
    np.isfinite(K_0) & (K_0 > 0) &
    np.isfinite(n_entropy) &
    np.isfinite(c_fit) & (c_fit > 0) &
    np.isfinite(c_ratio) & (c_ratio > 0) &
    np.isfinite(nfw_scat) & (nfw_scat > 0) &
    (logM >= 13.5)
)
print(f"  Valid halos for correlation plots: {good.sum():,}")

# ------------------------------------------------------------------ FIGURES ---

# ======== Figure 1: 2x4 correlation matrix delta_1 vs 4 metrics ========
fig, axes = plt.subplots(2, 4, figsize=(20, 9))
fig.suptitle(r"Frontier-E $z=0$: COM-offset ($\delta_1$) vs. Profile Deviation Metrics", fontsize=13)

metrics = [
    (K_0,       r"$K_0$  [keV cm$^2$] (central entropy)",     True),
    (n_entropy, r"Entropy slope $n$ ($K\propto r^n$)",         False),
    (c_fit,     r"$c_\mathrm{fit}$ (NFW total density)",       False),
    (c_ratio,   r"$c_\mathrm{fit}/c_\mathrm{cat}$",           False),
]
rows = [delta_1, delta_2]
row_labels = [
    r"$\delta_1 = |\mathbf{r}_\mathrm{COM} - \mathbf{r}_\mathrm{center}| / R_{200m}$",
    r"$\delta_2 = |\mathbf{r}_\mathrm{DM} - \mathbf{r}_\mathrm{gas}| / R_{500c}$",
]

for row_i, (delta_arr, dlabel) in enumerate(zip(rows, row_labels)):
    g = good & np.isfinite(delta_arr) & (delta_arr > 0)
    for col_i, (metric, mlabel, log_metric) in enumerate(metrics):
        ax = axes[row_i, col_i]
        sc = ax.scatter(metric[g], delta_arr[g],
                        c=logM[g], cmap="viridis",
                        s=3, alpha=0.3, rasterized=True,
                        vmin=logM[g].min(), vmax=logM[g].max())
        if log_metric:
            ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(mlabel, fontsize=9)
        ax.set_ylabel(dlabel, fontsize=8.5)
        ax.grid(True, alpha=0.2)

        # Compute Spearman correlation
        from scipy.stats import spearmanr
        valid = g & np.isfinite(metric) & np.isfinite(delta_arr)
        rho, pval = spearmanr(metric[valid], delta_arr[valid])
        ax.set_title(rf"Spearman $\rho={rho:.2f}$ (p={pval:.1e})", fontsize=8.5)

        if col_i == 3 and row_i == 0:
            cb = plt.colorbar(sc, ax=ax, shrink=0.8, pad=0.02)
            cb.set_label(r"$\log_{10} M_\mathrm{FoF}$", fontsize=8)

plt.tight_layout()
out1 = os.path.join(EXPERIMENT_DIR, "phase4_com_offset_correlations.png")
fig.savefig(out1, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {out1}")

# ======== Figure 2: delta_1 and delta_2 distributions + 2D scatter ========
fig2, axes2 = plt.subplots(1, 3, figsize=(15, 5))
fig2.suptitle(r"Frontier-E $z=0$: COM-offset Distributions", fontsize=12)

ax = axes2[0]
g_d1 = good & np.isfinite(delta_1) & (delta_1 > 0)
ax.hist(np.log10(delta_1[g_d1]), bins=60, color="steelblue", alpha=0.8, edgecolor="w", lw=0.3)
ax.axvline(np.log10(0.07), color="red", ls="--", lw=1.5,
           label=r"$\delta_1 = 0.07$ (relaxed threshold)")
ax.set_xlabel(r"$\log_{10}(\delta_1)$", fontsize=11)
ax.set_ylabel("N", fontsize=11)
ax.set_title(r"$\delta_1 = |\mathbf{r}_\mathrm{COM} - \mathbf{r}_\mathrm{center}| / R_{200m}$", fontsize=10)
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes2[1]
g_d2 = good & np.isfinite(delta_2) & (delta_2 > 0)
ax.hist(np.log10(delta_2[g_d2]), bins=60, color="darkorange", alpha=0.8, edgecolor="w", lw=0.3)
ax.axvline(np.log10(0.07), color="red", ls="--", lw=1.5, label=r"$\delta_2 = 0.07$")
ax.set_xlabel(r"$\log_{10}(\delta_2)$", fontsize=11)
ax.set_ylabel("N", fontsize=11)
ax.set_title(r"$\delta_2 = |\mathbf{r}_\mathrm{DM} - \mathbf{r}_\mathrm{gas}| / R_{500c}$", fontsize=10)
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

ax = axes2[2]
g_both = good & g_d1 & g_d2
ax.scatter(delta_1[g_both], delta_2[g_both],
           c=logM[g_both], cmap="viridis", s=3, alpha=0.3, rasterized=True)
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel(r"$\delta_1$ (FoF COM offset)", fontsize=11)
ax.set_ylabel(r"$\delta_2$ (DM-gas offset)", fontsize=11)
ax.set_title(r"$\delta_1$ vs $\delta_2$ (colored by $\log M$)", fontsize=10)
from scipy.stats import spearmanr
rho, pval = spearmanr(delta_1[g_both], delta_2[g_both])
ax.set_title(rf"$\delta_1$ vs $\delta_2$ — Spearman $\rho={rho:.2f}$", fontsize=10)
ax.grid(True, alpha=0.2)

plt.tight_layout()
out2 = os.path.join(EXPERIMENT_DIR, "phase4_offsets_distributions.png")
fig2.savefig(out2, dpi=150, bbox_inches="tight")
plt.close(fig2)
print(f"Saved: {out2}")

# ======== Figure 3: K_0 and c_fit/c_cat histograms coloured by delta_1 ========
# Split into relaxed (delta_1 < 0.07) and unrelaxed (delta_1 >= 0.07)
# Threshold from Neto+2007, Klypin+2016
g_rel   = good & g_d1 & (delta_1 < 0.07)
g_unrel = good & g_d1 & (delta_1 >= 0.07)

fig3, axes3 = plt.subplots(1, 3, figsize=(15, 5))
fig3.suptitle(r"Profile metrics split by $\delta_1$ threshold ($\delta_1 = 0.07$)", fontsize=12)

for ax_i, (arr, xlabel, use_log) in enumerate([
    (K_0,       r"$K_0$ [keV cm$^2$]",       True),
    (n_entropy, r"Entropy slope $n$",          False),
    (c_ratio,   r"$c_\mathrm{fit}/c_\mathrm{cat}$", False),
]):
    ax = axes3[ax_i]
    if use_log:
        vals_r = np.log10(arr[g_rel][arr[g_rel] > 0])
        vals_u = np.log10(arr[g_unrel][arr[g_unrel] > 0])
        xlabel = r"$\log_{10}$(" + xlabel + ")"
    else:
        vals_r = arr[g_rel][np.isfinite(arr[g_rel])]
        vals_u = arr[g_unrel][np.isfinite(arr[g_unrel])]

    bins = np.linspace(min(np.percentile(vals_r, 1), np.percentile(vals_u, 1)),
                       max(np.percentile(vals_r, 99), np.percentile(vals_u, 99)), 50)
    ax.hist(vals_r, bins=bins, color="steelblue", alpha=0.65, label=f"Relaxed ($\\delta_1<0.07$, N={g_rel.sum():,})", density=True)
    ax.hist(vals_u, bins=bins, color="firebrick", alpha=0.65, label=f"Unrelaxed ($\\delta_1\\geq0.07$, N={g_unrel.sum():,})", density=True)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel("Density", fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # KS test
    from scipy.stats import ks_2samp
    ks_stat, ks_p = ks_2samp(vals_r, vals_u)
    ax.set_title(f"KS stat={ks_stat:.3f}, p={ks_p:.1e}", fontsize=10)

plt.tight_layout()
out3 = os.path.join(EXPERIMENT_DIR, "phase4_profile_metrics_by_relaxation.png")
fig3.savefig(out3, dpi=150, bbox_inches="tight")
plt.close(fig3)
print(f"Saved: {out3}")

# ------------------------------------------------------------------ save results ---
results4 = {
    "n_halos_total": int(N),
    "n_halos_valid": int(good.sum()),
    "n_relaxed_d1":   int(g_rel.sum()),
    "n_unrelaxed_d1": int(g_unrel.sum()),
    "delta1_percentiles": np.nanpercentile(delta_1[g_d1], [5,25,50,75,95]).tolist(),
    "delta2_percentiles": np.nanpercentile(delta_2[g_d2], [5,25,50,75,95]).tolist(),
    "K0_median_relaxed":   float(np.nanmedian(K_0[g_rel])),
    "K0_median_unrelaxed": float(np.nanmedian(K_0[g_unrel])),
    "entropy_slope_median_relaxed":   float(np.nanmedian(n_entropy[g_rel])),
    "entropy_slope_median_unrelaxed": float(np.nanmedian(n_entropy[g_unrel])),
    "c_ratio_median_relaxed":   float(np.nanmedian(c_ratio[g_rel & (c_ratio > 0)])),
    "c_ratio_median_unrelaxed": float(np.nanmedian(c_ratio[g_unrel & (c_ratio > 0)])),
    "plots": ["phase4_com_offset_correlations.png",
              "phase4_offsets_distributions.png",
              "phase4_profile_metrics_by_relaxation.png"]
}
with open(os.path.join(EXPERIMENT_DIR, "phase4_results.json"), "w") as fout:
    json.dump(results4, fout, indent=2)

print("\n=== Phase 4 Summary ===")
print(f"  Valid halos:                  {good.sum():,}")
print(f"  Relaxed   (delta_1 < 0.07):  {g_rel.sum():,}")
print(f"  Unrelaxed (delta_1 >= 0.07): {g_unrel.sum():,}")
print(f"  K_0 median relaxed:           {results4['K0_median_relaxed']:.1f} keV cm^2")
print(f"  K_0 median unrelaxed:         {results4['K0_median_unrelaxed']:.1f} keV cm^2")
print(f"  Entropy slope median relaxed:   {results4['entropy_slope_median_relaxed']:.2f}")
print(f"  Entropy slope median unrelaxed: {results4['entropy_slope_median_unrelaxed']:.2f}")
print(f"  c_ratio median relaxed:         {results4['c_ratio_median_relaxed']:.2f}")
print(f"  c_ratio median unrelaxed:       {results4['c_ratio_median_unrelaxed']:.2f}")
print("Done.")
