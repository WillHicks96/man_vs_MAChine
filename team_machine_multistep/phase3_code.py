#!/usr/bin/env python3
"""
Phase 3: Direct profile fitting for 5 key profiles
- Total density: NFW (free rho_s, r_s)
- Gas density:   single beta-model (free ne0, r_c, beta)
- Entropy:       power law K = A * (r/R500c)^n (free A, n)
- Pressure:      generalized-NFW UPP (free P0, c500)
- X-ray lumin.:  beta-model (free L0, r_c, beta)

For each profile: top panel = data + best-fit; bottom panel = data/fit ratio
"""
import os, sys, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import h5py
from scipy.optimize import curve_fit
from scipy.stats import median_abs_deviation

# ------------------------------------------------------------------ paths ---
PROJECT_ROOT = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments"
EXPERIMENT_DIR = os.path.join(PROJECT_ROOT, "runs", "research_20260218_105441")
CATALOG = "/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5"
PHASE1 = os.path.join(EXPERIMENT_DIR, "phase1_results.json")
np.random.seed(42)

# ------------------------------------------------------------------ load ---
print("Loading catalog…")
with h5py.File(CATALOG, "r") as f:
    props = f["halo_properties/data"]
    fof_mass = np.array(props["fof_halo_mass"])
    m500c    = np.array(props["sod_halo_M500c"])
    r500c    = np.array(props["sod_halo_R500c"])
    t500c    = np.array(props["sod_halo_T500c"])
    cdelta   = np.array(props["sod_halo_cdelta"])

    pdata = f["halo_profiles/data"]
    radius       = np.array(pdata["sod_halo_bin_radius"])     # (N,51) Mpc/h
    bin_mass     = np.array(pdata["sod_halo_bin_mass"])       # (N,51) enclosed Msun/h
    gas_ne       = np.array(pdata["sod_halo_bin_gas_ne"])     # (N,51) cm^-3
    gas_entropy  = np.array(pdata["sod_halo_bin_gas_entropy"])# (N,51) keV cm^2
    gas_pthermal = np.array(pdata["sod_halo_bin_gas_pthermal"])# keV/cm^3
    xray_lumin   = np.array(pdata["sod_halo_bin_hot_gas_lumin_bolo"]) # erg/s

    prof_idx = np.array(f["halo_properties/data_linked"]["sod_profile_idx"])

with open(PHASE1) as f:
    res1 = json.load(f)
chosen = np.array(res1["chosen_halo_indices"])
logM   = np.log10(fof_mass)
labels = [f"H{i+1}: lgM={logM[c]:.2f}" for i, c in enumerate(chosen)]

cmap   = plt.colormaps["plasma"]
colors = [cmap(i / 9) for i in range(10)]

# ------------------------------------------------------------------ density helpers ---
def shell_density(r_bins, M_enc):
    """Mean density in each shell (N-1 values at midpoints)."""
    rho = np.zeros(len(r_bins) - 1)
    for i in range(len(r_bins) - 1):
        dM = M_enc[i+1] - M_enc[i]
        dV = (4./3.) * np.pi * (r_bins[i+1]**3 - r_bins[i]**3)
        rho[i] = max(dM, 0.) / max(dV, 1e-30)
    return rho

# ------------------------------------------------------------------ model functions ---
def nfw_density(r, rho_s, r_s):
    x = r / r_s
    return rho_s / (x * (1.0 + x)**2)

def beta_model_ne(r, ne0, r_c, beta):
    return ne0 / (1.0 + (r / r_c)**2)**(1.5 * beta)

def entropy_powerlaw(r_n, A, n):
    """K(r/R500c) = A * (r/R500c)^n"""
    return A * r_n**n

def upp_fit(r_n, P0, c500, gamma=0.3081, alpha=1.0510, beta=5.4905):
    """Arnaud+2010 UPP with free P0 and c500 (shape params fixed)."""
    u = np.maximum(c500 * r_n, 1e-6)
    return P0 / (u**gamma * (1.0 + u**alpha)**((beta - gamma) / alpha))

def xray_beta(r, L0, r_c, beta):
    """L_X profile (beta-model in X-ray, since L_X ~ ne^2 T^0.5)."""
    return L0 / (1.0 + (r / r_c)**2)**(3.0 * beta - 0.5)

# ------------------------------------------------------------------ fit function ---
def safe_fit(model, x, y, p0, bounds=(-np.inf, np.inf), log_fit=True, sigma=None):
    """
    Fit model to (x, y) data. If log_fit=True, fit in log-log space.
    Returns (popt, success, y_fit).
    """
    try:
        valid = (y > 0) & (x > 0) & np.isfinite(y) & np.isfinite(x)
        if valid.sum() < 4:
            return None, False, np.ones_like(y)

        if log_fit:
            log_model = lambda xv, *p: np.log(model(xv, *p))
            popt, _ = curve_fit(log_model, x[valid], np.log(y[valid]),
                                p0=p0, bounds=bounds, maxfev=8000)
        else:
            popt, _ = curve_fit(model, x[valid], y[valid],
                                p0=p0, bounds=bounds, maxfev=8000)
        y_fit = model(x, *popt)
        return popt, True, y_fit
    except Exception as e:
        return None, False, np.ones_like(y)

# ------------------------------------------------------------------ main figure ---
# 5 profile types, each with 2 panels (top: data+fit, bottom: ratio)
# Layout: 2 rows × 5 cols
fig, axes = plt.subplots(2, 5, figsize=(24, 9), gridspec_kw={"height_ratios": [2, 1]})
fig.suptitle("Frontier-E: Profile Fits for 10 Halos — Phase 3", fontsize=14, y=1.01)

# Store fit params for reporting
fit_params = {h: {} for h in chosen}

for col_idx, (halo_idx, col, lab) in enumerate(zip(chosen, colors, labels)):
    # This loops only 10 halos for the same plot column
    pass  # We'll fill each column below

# ---------- PANEL DEFINITIONS ----------
# col 0: Total density vs NFW fit
# col 1: Gas density vs beta-model fit
# col 2: Entropy vs power-law fit
# col 3: Pressure vs UPP fit
# col 4: X-ray luminosity vs beta-model fit

col_titles = [
    "Total Density vs. NFW fit",
    r"Gas Density vs. $\beta$-model fit",
    r"Entropy vs. Power-law fit ($K\propto r^n$)",
    "Pressure vs. UPP fit",
    r"X-ray Lumin. vs. $\beta$-model fit",
]
y_labels_top = [
    r"$\rho\ [M_\odot\,h^2\,\mathrm{Mpc}^{-3}]$",
    r"$n_e\ [\mathrm{cm}^{-3}]$",
    r"$K\ [\mathrm{keV\,cm^2}]$",
    r"$P_\mathrm{th}\ [\mathrm{keV\,cm}^{-3}]$",
    r"$L_X\ [\mathrm{erg\,s}^{-1}]$",
]
y_labels_bot = [
    r"$\rho / \rho_\mathrm{NFW}^\mathrm{fit}$",
    r"$n_e / n_{e,\beta}^\mathrm{fit}$",
    r"$K / K_\mathrm{PL}^\mathrm{fit}$",
    r"$P / P_\mathrm{UPP}^\mathrm{fit}$",
    r"$L_X / L_{X,\beta}^\mathrm{fit}$",
]

for col in range(5):
    ax_top = axes[0, col]
    ax_bot = axes[1, col]
    ax_top.set_title(col_titles[col], fontsize=9.5, fontweight="bold")
    ax_top.set_ylabel(y_labels_top[col], fontsize=8.5)
    ax_bot.set_ylabel(y_labels_bot[col], fontsize=8.5)
    ax_bot.set_xlabel(r"$r / R_{500c}$", fontsize=9)
    ax_bot.axhline(1.0, color="k", ls="--", lw=1.2)
    for ax in [ax_top, ax_bot]:
        ax.set_xlim(0.02, 2.0)
        ax.axvline(1.0, color="gray", ls=":", lw=0.8)
        ax.grid(True, alpha=0.25, lw=0.5)

# ------------------------------------------------------------------ loop over halos ---
for i, halo_idx in enumerate(chosen):
    pi  = prof_idx[halo_idx]
    r   = radius[pi]               # (51,) Mpc/h
    r_n = r / r500c[halo_idx]      # normalised radius
    r_mid = 0.5 * (r[:-1] + r[1:])
    r_mid_n = r_mid / r500c[halo_idx]

    # === COL 0: Total density vs. NFW fit ===
    M   = bin_mass[pi]
    rho = shell_density(r, M)   # (50,) Msun/h / (Mpc/h)^3

    # Initial guess: r_s ~ 0.3*R500c, rho_s from peak density
    valid = (rho > 0) & (r_mid > 0)
    if valid.sum() > 4:
        r_s_init = 0.3 * r500c[halo_idx]
        rho_s_init = float(np.median(rho[valid])) * 10.0

        popt_nfw, ok, rho_fit = safe_fit(
            nfw_density, r_mid, rho,
            p0=[rho_s_init, r_s_init],
            bounds=([0, 0.01], [rho_s_init * 1e6, 5.0]),
            log_fit=True)

        c_fit = r500c[halo_idx] / popt_nfw[1] if (ok and popt_nfw is not None) else np.nan

        # Plot
        axes[0, 0].loglog(r_mid_n[valid], rho[valid], color=colors[i],
                          lw=1.5, alpha=0.75)
        if ok:
            axes[0, 0].loglog(r_mid_n[valid], rho_fit[valid], color=colors[i],
                              lw=1.5, ls="--", alpha=0.9)
            ratio = np.where(rho_fit > 0, rho / rho_fit, np.nan)
            axes[1, 0].semilogy(r_mid_n, ratio, color=colors[i], lw=1.5, alpha=0.75)
            fit_params[halo_idx]["nfw_c_fit"] = float(c_fit)
        else:
            axes[1, 0].axhline(1.0, color=colors[i], lw=0.5, alpha=0.3)

    # === COL 1: Gas density vs. beta-model fit ===
    ne = gas_ne[pi]
    valid_ne = (ne > 0) & (r > 0)
    if valid_ne.sum() > 4:
        ne_max = ne[valid_ne][0]
        r_c_init = 0.15 * r500c[halo_idx]
        popt_beta, ok_b, ne_fit = safe_fit(
            beta_model_ne, r,
            ne, p0=[ne_max, r_c_init, 0.67],
            bounds=([0, 0.001, 0.1], [ne_max*100, r500c[halo_idx]*2, 2.5]),
            log_fit=True)

        axes[0, 1].loglog(r_n[valid_ne], ne[valid_ne], color=colors[i],
                          lw=1.5, alpha=0.75)
        if ok_b:
            axes[0, 1].loglog(r_n[valid_ne], ne_fit[valid_ne], color=colors[i],
                              lw=1.5, ls="--", alpha=0.9)
            ratio_ne = np.where(ne_fit > 0, ne / ne_fit, np.nan)
            axes[1, 1].semilogy(r_n, ratio_ne, color=colors[i], lw=1.5, alpha=0.75)
            fit_params[halo_idx]["beta_fit"] = float(popt_beta[2]) if popt_beta is not None else np.nan
        else:
            axes[1, 1].axhline(1.0, color=colors[i], lw=0.5, alpha=0.3)

    # === COL 2: Entropy vs. power-law fit ===
    K = gas_entropy[pi]
    valid_K = (K > 0) & (r_n > 0.05)   # avoid innermost bins for power-law
    if valid_K.sum() > 4:
        K_init = float(np.median(K[valid_K]))
        popt_K, ok_K, K_fit = safe_fit(
            entropy_powerlaw, r_n, K,
            p0=[K_init, 1.1],
            bounds=([0, 0.0], [K_init * 100, 5.0]),
            log_fit=True)

        # Also do a fit to the FULL range (including core) for the deviation
        valid_K_all = (K > 0)
        K_fit_all = K_fit if ok_K else np.ones_like(K) * K_init

        axes[0, 2].loglog(r_n[valid_K], K[valid_K], color=colors[i],
                          lw=1.5, alpha=0.75)
        if ok_K:
            r_dense = np.logspace(np.log10(r_n[valid_K].min()),
                                  np.log10(r_n[valid_K].max()), 100)
            axes[0, 2].loglog(r_dense, entropy_powerlaw(r_dense, *popt_K),
                              color=colors[i], lw=1.5, ls="--", alpha=0.9)
            K_fit_full = entropy_powerlaw(r_n, *popt_K)
            ratio_K = np.where(K_fit_full > 0, K / K_fit_full, np.nan)
            axes[1, 2].semilogy(r_n[K > 0], ratio_K[K > 0], color=colors[i],
                                lw=1.5, alpha=0.75)
            fit_params[halo_idx]["entropy_slope"] = float(popt_K[1]) if popt_K is not None else np.nan

    # === COL 3: Pressure vs. UPP fit ===
    P = gas_pthermal[pi]
    valid_P = (P > 0) & (r_n > 0.05)
    if valid_P.sum() > 4:
        # Find P at ~R500c
        idx_r500 = np.argmin(np.abs(r_n - 1.0))
        P500_est = P[idx_r500] if P[idx_r500] > 0 else np.nanmedian(P[valid_P])
        popt_P, ok_P, P_fit = safe_fit(
            upp_fit, r_n, P,
            p0=[P500_est * 10.0, 1.177],
            bounds=([0, 0.1], [P500_est * 1e6, 10.0]),
            log_fit=True)

        axes[0, 3].loglog(r_n[valid_P], P[valid_P], color=colors[i],
                          lw=1.5, alpha=0.75)
        if ok_P:
            r_dense = np.logspace(np.log10(0.05), np.log10(2.0), 100)
            axes[0, 3].loglog(r_dense, upp_fit(r_dense, *popt_P),
                              color=colors[i], lw=1.5, ls="--", alpha=0.9)
            P_fit_full = upp_fit(r_n, *popt_P)
            ratio_P = np.where(P_fit_full > 0, P / P_fit_full, np.nan)
            axes[1, 3].semilogy(r_n[P > 0], ratio_P[P > 0], color=colors[i],
                                lw=1.5, alpha=0.75)
            fit_params[halo_idx]["upp_c500_fit"] = float(popt_P[1]) if popt_P is not None else np.nan

    # === COL 4: X-ray luminosity vs. beta-model fit ===
    Lx = xray_lumin[pi]
    valid_Lx = (Lx > 0) & (r > 0)
    if valid_Lx.sum() > 4:
        Lx_peak = float(Lx[valid_Lx].max())
        r_c_init = 0.1 * r500c[halo_idx]
        popt_Lx, ok_Lx, Lx_fit = safe_fit(
            xray_beta, r, Lx,
            p0=[Lx_peak, r_c_init, 0.67],
            bounds=([0, 0.001, 0.2], [Lx_peak * 100, r500c[halo_idx] * 2, 2.0]),
            log_fit=True)

        axes[0, 4].loglog(r_n[valid_Lx], Lx[valid_Lx], color=colors[i],
                          lw=1.5, alpha=0.75, label=labels[i])
        if ok_Lx:
            axes[0, 4].loglog(r_n[valid_Lx], Lx_fit[valid_Lx], color=colors[i],
                              lw=1.5, ls="--", alpha=0.9)
            ratio_Lx = np.where(Lx_fit > 0, Lx / Lx_fit, np.nan)
            axes[1, 4].semilogy(r_n[Lx > 0], ratio_Lx[Lx > 0], color=colors[i],
                                lw=1.5, alpha=0.75)

# ---- formatting ----
# Log axes for top panels
for col in range(5):
    axes[0, col].set_xscale("log")
    axes[0, col].set_xlim(0.02, 2.5)
    axes[1, col].set_xlim(0.02, 2.5)
    axes[1, col].set_ylim(0.05, 20.0)
    axes[1, col].set_xscale("log")

axes[0, 0].set_xscale("log")

# Legend in X-ray panel
handles = [plt.Line2D([0], [0], color=colors[i], lw=2) for i in range(10)]
axes[0, 4].legend(handles, labels, loc="lower left", fontsize=6.0, ncol=1, framealpha=0.7)

# Indicate solid=data, dashed=fit
for col in range(5):
    axes[0, col].plot([], [], 'k-',  lw=1.5, label="Data")
    axes[0, col].plot([], [], 'k--', lw=1.5, label="Best fit")
    axes[0, col].legend(loc="lower left", fontsize=6.5, framealpha=0.6)

plt.tight_layout()
outpath = os.path.join(EXPERIMENT_DIR, "phase3_profile_fits.png")
fig.savefig(outpath, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"Saved: {outpath}")

# ------------------------------------------------------------------ print fit params ---
print("\n=== Best-fit NFW concentrations (vs catalog cdelta) ===")
print(f"{'Halo':>6}  {'logM':>6}  {'c_cat':>6}  {'c_fit':>8}  {'entropy_n':>10}")
for i, halo_idx in enumerate(chosen):
    c_cat  = cdelta[halo_idx]
    c_f    = fit_params[halo_idx].get("nfw_c_fit", np.nan)
    e_n    = fit_params[halo_idx].get("entropy_slope", np.nan)
    print(f"  H{i+1:1d}    {logM[halo_idx]:6.2f}  {c_cat:6.1f}  {c_f:8.2f}  {e_n:10.2f}")

# ------------------------------------------------------------------ save results ---
results3 = {
    "chosen_halo_indices": chosen.tolist(),
    "fit_params": {str(k): v for k, v in fit_params.items()},
    "plots": ["phase3_profile_fits.png"]
}
with open(os.path.join(EXPERIMENT_DIR, "phase3_results.json"), "w") as fout:
    json.dump(results3, fout, indent=2)
print("Done.")
