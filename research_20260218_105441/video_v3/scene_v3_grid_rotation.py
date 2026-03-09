"""
scene_v3_grid_rotation.py — Synced 2-column 2×2 grid rotation with animated profiles.

Layout (per frame)
------------------
  LEFT 620px  |  8px sep  |  CENTER 664px profiles  |  8px sep  |  RIGHT 620px

  LEFT  : 2×2 grid of RELAXED halo projections (rotating)
  CENTER: 5 stacked radial profile panels — dark background, animated reveal
          relaxed lines appear first, then unrelaxed lines fade in
  RIGHT : 2×2 grid of UNRELAXED halo projections (same rotation angle)

Changes in this version (v3.2):
  - SIDE_W increased 460→620 (wider halo panels, more square 2×2 tiles)
  - CENTER_W reduced to 664px
  - Field name labels moved FROM center top TO side panel headers (left & right)
  - Profile row titles as text boxes inside each subplot
  - Y-axis limits computed from global valid dataset (consistent with phase6)
  - Halo selection uses random sampling (not just most massive)

Functions
---------
compute_profiles_for_scene(catalog_path, col_idx)
    Load catalog data and compute stacked profiles for one comparison column.
    col_idx: 0=R1/notR1, 1=R1∩R2/R1∖R2, 2=R1∩R3/R1∖R3, 3=R1∩R4/R1∖R4

render_profile_panel(profile_data, relax_label, unrelax_label, ...)
    Pre-render 3 PIL RGB images: (dark-bg, relax-only, both-lines).

scene_synced_grid_rotation(...)
    Generator — yields 1920×1080 PIL RGB frames.
"""

import sys
import os

_V2_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "video_v2")
sys.path.insert(0, _V2_DIR)

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from video_utils import (
    W, H, FPS,
    CMAP_DM, CMAP_STARS, CMAP_GAS, CMAP_TEMP,
    FIELD_ACCENT_RGB,
    smoothstep, blend, add_glow, add_vignette, composite_rgba, make_text_overlay,
)
from PIL import Image, ImageDraw

import opencosmo as oc    # type: ignore
import h5py


# ── Layout constants ──────────────────────────────────────────────────────────

SIDE_W   = 720            # left / right panel widths (px)  ← wider (was 460)
SEP      = 8              # separator width (px)
SEP_COL  = (155, 162, 185)  # bright steel-gray — clearly visible
CENTER_W = W - 2 * SIDE_W - 2 * SEP  # 464 px
HEADER_H = 70
FOOTER_H = 50
GRID_H   = H - HEADER_H - FOOTER_H  # 960

TILE_W   = SIDE_W // 2   # 360 px per tile column
TILE_H   = GRID_H  // 2  # 480 px per tile row
PROJ     = 340            # square projection size (n_bins) — fills tile with 10px padding

pad_x = (TILE_W - PROJ) // 2   # 10
pad_y = (TILE_H - PROJ) // 2   # 70

RIGHT_X = SIDE_W + SEP + CENTER_W + SEP  # 1200

# Canvas paste coordinates for the 8 tiles
#   tiles 0-3: left panel
#   tiles 4-7: right panel
TILE_XY = []
for side_x in (0, RIGHT_X):
    for row in range(2):
        for col in range(2):
            tx = side_x + col * TILE_W + pad_x
            ty = HEADER_H + row * TILE_H + pad_y
            TILE_XY.append((tx, ty))

# Profile panel region
PROF_X = SIDE_W + SEP      # 628
PROF_Y = HEADER_H          # 70
PROF_W = CENTER_W           # 664
PROF_H = GRID_H             # 960


# ── Field definitions ─────────────────────────────────────────────────────────

FIELDS = [
    ("dm",   "mass",        CMAP_DM,    False, "Dark Matter"),
    ("star", "mass",        CMAP_STARS, False, "Stars"),
    ("gas",  "mass",        CMAP_GAS,   True,  "Gas"),
    ("gas",  "temperature", CMAP_TEMP,  True,  "Gas Temperature"),
]
N_FIELDS = len(FIELDS)

# Profile row titles (shown as text boxes inside each subplot)
PROFILE_ROW_TITLES = [
    "Total Mass Profile",
    "Electron Density Profile",
    "Entropy Profile",
    "Thermal Pressure Profile",
    "Luminosity Profile",
]

# Profile accent colors
COL_RELAX_RGB   = (72,  196, 248)   # bright cyan-blue  (relaxed side)
COL_UNRELAX_RGB = (248, 120,  64)   # bright orange      (unrelaxed side)


# ── Catalog & profile computation ─────────────────────────────────────────────

def _robust_zscore(arr):
    finite = np.isfinite(arr)
    vals = arr[finite]
    if vals.size == 0:
        return np.full_like(arr, np.nan)
    med = np.median(vals)
    mad = np.median(np.abs(vals - med))
    if mad < 1e-30:
        mad = np.std(vals) + 1e-30
    return (arr - med) / (1.4826 * mad)


def _compute_ylimits_from_raw(valid_indices, parr, prof_idx_arr, n_max=2000, seed=99):
    """
    Compute y-limits from raw (un-interpolated) profile bin data across all valid halos.
    More reliable than using interpolated medians because it captures the full data range.
    """
    rng = np.random.default_rng(seed)
    idx = rng.choice(valid_indices, size=min(n_max, len(valid_indices)), replace=False)
    vals = []
    for i in idx:
        pi = prof_idx_arr[i]
        yp = parr[pi]
        good = yp[yp > 0]
        if len(good) > 0:
            vals.extend(good.tolist())
    if not vals:
        return (1e-10, 1.0)
    vals = np.array(vals)
    ylo = np.percentile(vals, 0.2) * 0.3
    yhi = np.percentile(vals, 99.8) * 3.0
    return (max(ylo, 1e-50), max(yhi, ylo * 10))


def _interp_profiles(halo_indices, data_arr, r500c_arr, prof_idx_arr,
                     radius_arr, r_grid, n_halo_max=500, seed=42):
    rng = np.random.default_rng(seed)
    idx = rng.choice(halo_indices, size=min(n_halo_max, len(halo_indices)),
                     replace=False)
    stacked = []
    for i in idx:
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
    if not stacked:
        return np.full_like(r_grid, np.nan)
    return np.nanmedian(np.array(stacked), axis=0)


def compute_profiles_for_scene(catalog_path, col_idx):
    """
    Load the HACC halo catalog and compute stacked radial profile medians for
    one comparison column.

    col_idx
    -------
    0 : R1  vs  notR1
    1 : R1∩R2  vs  R1∖R2
    2 : R1∩R3  vs  R1∖R3
    3 : R1∩R4  vs  R1∖R4

    Returns
    -------
    dict with keys:
        'r_grid'    : 1D array of r/R500c values
        'relax'     : list of 5 median-profile arrays (one per profile type)
        'unrelax'   : list of 5 median-profile arrays
        'ylabels'   : list of 5 y-axis label strings
        'ylimits'   : list of 5 (ymin, ymax) tuples (consistent with phase6)
    """
    print(f"  [profiles] Loading catalog from {os.path.basename(catalog_path)} …")
    with h5py.File(catalog_path, "r") as f:
        props = f["halo_properties/data"]
        fof_mass     = np.array(props["fof_halo_mass"])
        r500c        = np.array(props["sod_halo_R500c"])
        r200m        = np.array(props["sod_halo_R200m"])
        t500c        = np.array(props["sod_halo_T500c"])
        t500c_bolo_ex= np.array(props["sod_halo_T500cBoloEx"])
        core_entropy = np.array(props["sod_halo_core_entropy"])
        core_ne      = np.array(props["sod_halo_core_ne"])
        fof_cx   = np.array(props["fof_halo_center_x"])
        fof_cy   = np.array(props["fof_halo_center_y"])
        fof_cz   = np.array(props["fof_halo_center_z"])
        fof_cx2  = np.array(props["fof_halo_com_x"])
        fof_cy2  = np.array(props["fof_halo_com_y"])
        fof_cz2  = np.array(props["fof_halo_com_z"])
        sod_dm_x = np.array(props["sod_halo_com_x_dm"])
        sod_dm_y = np.array(props["sod_halo_com_y_dm"])
        sod_dm_z = np.array(props["sod_halo_com_z_dm"])
        sod_gx   = np.array(props["sod_halo_com_x_gas"])
        sod_gy   = np.array(props["sod_halo_com_y_gas"])
        sod_gz   = np.array(props["sod_halo_com_z_gas"])

        pdata        = f["halo_profiles/data"]
        radius       = np.array(pdata["sod_halo_bin_radius"])
        bin_mass     = np.array(pdata["sod_halo_bin_mass"])
        gas_ne       = np.array(pdata["sod_halo_bin_gas_ne"])
        gas_entropy  = np.array(pdata["sod_halo_bin_gas_entropy"])
        gas_pthermal = np.array(pdata["sod_halo_bin_gas_pthermal"])
        xray_lumin   = np.array(pdata["sod_halo_bin_hot_gas_lumin_bolo"])
        prof_idx     = np.array(f["halo_properties/data_linked"]["sod_profile_idx"])

    logM = np.log10(fof_mass)

    d1_abs  = np.sqrt((fof_cx2-fof_cx)**2 + (fof_cy2-fof_cy)**2 + (fof_cz2-fof_cz)**2)
    delta_1 = np.where(r200m > 0, d1_abs / r200m, np.nan)
    d2_abs  = np.sqrt((sod_dm_x-sod_gx)**2 + (sod_dm_y-sod_gy)**2 + (sod_dm_z-sod_gz)**2)
    delta_2 = np.where(r500c > 0, d2_abs / r500c, np.nan)
    delta_3 = core_entropy

    T_ratio = np.where((t500c > 0) & (t500c_bolo_ex > 0), t500c_bolo_ex / t500c, np.nan)
    log_ne     = np.where(core_ne > 0, np.log(core_ne), np.nan)
    log_Tratio = np.where(T_ratio > 0, np.log(T_ratio), np.nan)
    TPI = _robust_zscore(log_ne) + _robust_zscore(log_Tratio)

    valid = (np.isfinite(delta_1) & np.isfinite(delta_2) & np.isfinite(delta_3) &
             (delta_1 > 0) & (delta_2 > 0) & (delta_3 > 0) &
             np.isfinite(TPI) & (logM >= 13.5))

    THR_D1 = 0.07;  THR_D2 = 0.07;  THR_KE = 150.0;  THR_TPI = 0.0
    R1     = valid & (delta_1 < THR_D1)
    notR1  = valid & ~R1

    mask_pairs = [
        (R1,               notR1,          "R₁",       "¬R₁"),
        (R1 & (delta_2 < THR_D2),  R1 & (delta_2 >= THR_D2), "R₁∩R₂", "R₁∖R₂"),
        (R1 & (delta_3 < THR_KE),  R1 & (delta_3 >= THR_KE), "R₁∩R₃", "R₁∖R₃"),
        (R1 & (TPI > THR_TPI),     R1 & (TPI <= THR_TPI),    "R₁∩R₄", "R₁∖R₄"),
    ]
    mR, mU, lR, lU = mask_pairs[col_idx]
    print(f"  [profiles] col {col_idx}: {lR}={mR.sum():,}  {lU}={mU.sum():,}")

    # Full valid set for global y-limits (consistent across all scenes, like phase6)
    all_valid_idx = np.where(valid)[0]

    r_grid = np.logspace(np.log10(0.02), np.log10(2.0), 70)
    # (data_array, ylabel, log_y_scale)
    profile_defs = [
        (bin_mass,     r"$M(<r)$",          True),
        (gas_ne,       r"$n_e$",             True),
        (gas_entropy,  r"$K$",               True),
        (gas_pthermal, r"$P_\mathrm{th}$",   True),
        (xray_lumin,   r"$L_X$",             False),  # linear: data values ~39–44 code units
    ]

    # Pre-compute global y-limits once from raw profile data (captures true range)
    print("  [profiles] Computing global y-limits from raw data …")
    global_ylimits = []
    for parr, _, _log in profile_defs:
        ylo, yhi = _compute_ylimits_from_raw(all_valid_idx, parr, prof_idx, n_max=2000)
        global_ylimits.append((ylo, yhi))

    # Hard-code luminosity (index 4) limits from phase6 figure:
    # Phase6 shows 3.95×10¹ to 4.4×10¹ = literal values 39.5 to 44.0 in code units
    global_ylimits[4] = (38.0, 46.0)

    profiles_r, profiles_u, ylabels, ylimits, log_scales = [], [], [], [], []
    for i, (parr, ylabel, log_y) in enumerate(profile_defs):
        med_r = _interp_profiles(np.where(mR)[0], parr, r500c, prof_idx, radius, r_grid)
        med_u = _interp_profiles(np.where(mU)[0], parr, r500c, prof_idx, radius, r_grid)
        profiles_r.append(med_r)
        profiles_u.append(med_u)
        ylabels.append(ylabel)
        ylimits.append(global_ylimits[i])
        log_scales.append(log_y)

    return dict(r_grid=r_grid, relax=profiles_r, unrelax=profiles_u,
                ylabels=ylabels, ylimits=ylimits, log_scales=log_scales)


# ── Profile panel rendering ───────────────────────────────────────────────────

def render_profile_panel(profile_data, relax_label, unrelax_label,
                          panel_w=PROF_W, panel_h=PROF_H):
    """
    Pre-render 3 PIL RGB images (dark-bg, with-relaxed, with-both) for the
    animated center profile panel.

    Returns
    -------
    (img_dark, img_relax, img_both)  — each a PIL RGB Image of size panel_w × panel_h
    """
    DARK_BG  = '#06090f'
    C_AX     = '#8090a8'
    C_GRID   = '#141824'
    C_R      = tuple(c / 255 for c in COL_RELAX_RGB)
    C_U      = tuple(c / 255 for c in COL_UNRELAX_RGB)

    # DPI=100: figure rendered at exactly panel_w × panel_h pixels.
    # At DPI=100, 1pt ≈ 1.39px — sensible sizes for a ~464px-wide panel.
    DPI = 100
    figw = panel_w / DPI
    figh = panel_h / DPI

    r_grid     = profile_data['r_grid']
    profs_r    = profile_data['relax']
    profs_u    = profile_data['unrelax']
    ylabels    = profile_data['ylabels']
    ylimits    = profile_data['ylimits']
    log_scales = profile_data.get('log_scales', [True] * len(ylabels))
    n_rows     = len(ylabels)

    GS = dict(hspace=0.12, left=0.15, right=0.97, top=0.97, bottom=0.07)

    def _make_fig_and_axes():
        fig, axes = plt.subplots(n_rows, 1, figsize=(figw, figh),
                                  sharex=True, gridspec_kw=GS)
        if n_rows == 1:
            axes = [axes]
        fig.patch.set_facecolor(DARK_BG)
        for i, ax in enumerate(axes):
            ax.set_facecolor(DARK_BG)
            ax.tick_params(colors=C_AX, labelsize=7.5, which='both')
            for sp in ax.spines.values():
                sp.set_color('#2a3040')
                sp.set_linewidth(0.5)
            ax.set_xscale('log')
            ax.set_yscale('log' if log_scales[i] else 'linear')
            ax.grid(True, color=C_GRID, lw=0.35, which='both')
            ax.set_xlim(0.02, 2.0)
            ax.set_ylim(*ylimits[i])
            ax.set_ylabel(ylabels[i], fontsize=8.5, color=C_AX)
            # Radial zone lines
            for rv in (0.15, 0.5, 1.0):
                ax.axvline(rv, color='#2a3040', lw=0.5, ls='-', zorder=0)
            # Profile row title as text box in upper-right corner
            row_title = PROFILE_ROW_TITLES[i] if i < len(PROFILE_ROW_TITLES) else ""
            if row_title:
                ax.text(0.97, 0.96, row_title,
                        transform=ax.transAxes,
                        ha='right', va='top',
                        fontsize=7.5, color='#c8d4e8',
                        bbox=dict(facecolor='#0e1520', edgecolor='#2a3a50',
                                  boxstyle='round,pad=0.25', alpha=0.88))
        axes[-1].set_xlabel(r'$r\,/\,R_{500c}$', fontsize=8.5, color=C_AX)
        return fig, axes

    def _to_pil(fig, target_w, target_h):
        fig.canvas.draw()
        buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
        rw, rh = fig.canvas.get_width_height()
        arr = buf.reshape(rh, rw, 4)[:, :, :3].copy()
        plt.close(fig)
        img = Image.fromarray(arr)
        if img.size != (target_w, target_h):
            img = img.resize((target_w, target_h), Image.LANCZOS)
        return img

    # ── Image 1: dark bg + axes only ─────────────────────────────────────────
    fig, axes = _make_fig_and_axes()
    img_dark = _to_pil(fig, panel_w, panel_h)

    # ── Image 2: dark bg + axes + relaxed lines ───────────────────────────────
    fig, axes = _make_fig_and_axes()
    for i, ax in enumerate(axes):
        med = profs_r[i]
        vm  = np.isfinite(med) & (med > 0)
        if vm.sum() > 3:
            ax.plot(r_grid[vm], med[vm], color=C_R, lw=1.6, ls='-',
                    solid_capstyle='round', label=relax_label)
        if i == 0:
            ax.legend(fontsize=7.5, loc='upper left',
                      facecolor='#0e1320', edgecolor='#2a3040',
                      labelcolor=C_AX, framealpha=0.9, handlelength=1.0)
    img_relax = _to_pil(fig, panel_w, panel_h)

    # ── Image 3: dark bg + axes + both lines ─────────────────────────────────
    fig, axes = _make_fig_and_axes()
    for i, ax in enumerate(axes):
        med_r = profs_r[i]
        med_u = profs_u[i]
        vm_r = np.isfinite(med_r) & (med_r > 0)
        vm_u = np.isfinite(med_u) & (med_u > 0)
        if vm_r.sum() > 3:
            ax.plot(r_grid[vm_r], med_r[vm_r], color=C_R, lw=1.6, ls='-',
                    solid_capstyle='round', label=relax_label)
        if vm_u.sum() > 3:
            ax.plot(r_grid[vm_u], med_u[vm_u], color=C_U, lw=1.6, ls='-',
                    solid_capstyle='round', label=unrelax_label)
        if i == 0:
            ax.legend(fontsize=7.5, loc='upper left',
                      facecolor='#0e1320', edgecolor='#2a3040',
                      labelcolor=C_AX, framealpha=0.9, handlelength=1.0)
    img_both = _to_pil(fig, panel_w, panel_h)

    return img_dark, img_relax, img_both


# ── Particle loading ──────────────────────────────────────────────────────────

def _get_col(dataset, col):
    try:
        return np.array(dataset.data[col])
    except Exception:
        return np.array(dataset[col])


def load_group_particles(hdf5_path, tags, particle_types=("dm", "gas", "star")):
    """Load particles for multiple halo tags from one HDF5 file (single pass)."""
    tags_set = set(int(t) for t in tags)
    pt_keys  = [f"{pt}_particles" for pt in particle_types]

    data   = oc.open(hdf5_path)
    result = {}

    print(f"  Opening {os.path.basename(hdf5_path)} for {len(tags_set)} halos …")
    for halo in data.halos(pt_keys):
        props = halo["halo_properties"]
        htag  = int(props["unique_tag"])
        if htag not in tags_set:
            continue

        try:
            cx = float(props["fof_halo_center_x"])
            cy = float(props["fof_halo_center_y"])
            cz = float(props["fof_halo_center_z"])
        except Exception:
            cx = cy = cz = None

        shared_cx = cx
        shared_cy = cy
        shared_cz = cz
        halo_data = {}

        for pt, pt_key in zip(particle_types, pt_keys):
            try:
                particles = halo[pt_key]
                x_raw = _get_col(particles, "x")
                y_raw = _get_col(particles, "y")
                z_raw = _get_col(particles, "z")
                m     = _get_col(particles, "mass")

                if shared_cx is None and len(x_raw) > 0:
                    total_m = float(m.sum())
                    if total_m > 0:
                        shared_cx = float((x_raw * m).sum() / total_m)
                        shared_cy = float((y_raw * m).sum() / total_m)
                        shared_cz = float((z_raw * m).sum() / total_m)
                    else:
                        shared_cx = float(np.median(x_raw))
                        shared_cy = float(np.median(y_raw))
                        shared_cz = float(np.median(z_raw))

                cx0 = shared_cx if shared_cx is not None else 0.0
                cy0 = shared_cy if shared_cy is not None else 0.0
                cz0 = shared_cz if shared_cz is not None else 0.0

                entry = {
                    "x": (x_raw - cx0).astype(np.float32),
                    "y": (y_raw - cy0).astype(np.float32),
                    "z": (z_raw - cz0).astype(np.float32),
                    "mass": m.astype(np.float32),
                }
                if pt == "gas":
                    try:
                        entry["temperature"] = _get_col(particles, "temperature").astype(np.float32)
                    except Exception:
                        pass
                halo_data[pt] = entry
                print(f"    tag={htag}  {pt}: {len(x_raw):,} particles")
            except Exception as exc:
                print(f"    tag={htag}  WARNING: {pt_key} unavailable: {exc}")

        result[htag] = halo_data
        if len(result) == len(tags_set):
            break

    missing = tags_set - set(result.keys())
    if missing:
        print(f"  WARNING: tags not found: {missing}")

    return result


# ── Projection helper ─────────────────────────────────────────────────────────

def make_proj(x, y, z, weights, theta, phi,
              n_bins=PROJ, cmap_name="plasma_r", invert_cmap=True,
              size_px=None, p_lo=3, p_hi=99.2,
              extent_pct=82):    # ← 82nd percentile: zooms into dense core
    """
    Rotate particles and return a 2D weighted histogram as a PIL RGB Image.

    extent_pct=82 zooms in to where 82% of the particle mass lies, which
    avoids the sparse outer shell that creates the circular-edge artifact.
    """
    if size_px is None:
        size_px = n_bins

    ct, st = np.cos(theta), np.sin(theta)
    x1 = ct * x - st * y
    y1 = st * x + ct * y

    if phi != 0.0:
        cp, sp = np.cos(phi), np.sin(phi)
        px_arr = x1
        py_arr = cp * y1 - sp * z
    else:
        px_arr, py_arr = x1, y1

    r3d   = np.sqrt(x**2 + y**2 + z**2)
    r_max = float(np.percentile(r3d, extent_pct))
    if r_max <= 0:
        r_max = 1.0

    H_hist, _, _ = np.histogram2d(
        px_arr, py_arr, bins=n_bins,
        range=[[-r_max, r_max], [-r_max, r_max]],
        weights=weights,
    )
    H_hist = H_hist.T
    H_log  = np.log1p(H_hist)

    nonzero = H_log[H_log > 0]
    if len(nonzero) == 0:
        return Image.fromarray(np.zeros((size_px, size_px, 3), np.uint8))

    vmin = np.percentile(nonzero, p_lo)
    vmax = np.percentile(nonzero, p_hi)
    if vmax <= vmin:
        vmax = vmin + 1e-10

    norm = np.clip((H_log - vmin) / (vmax - vmin), 0, 1)
    if invert_cmap:
        norm = 1.0 - norm

    cmap = plt.get_cmap(cmap_name)
    rgb  = (cmap(norm)[:, :, :3] * 255).astype(np.uint8)
    rgb[H_hist <= 0] = 0

    img = Image.fromarray(rgb)
    if img.size[0] != size_px:
        img = img.resize((size_px, size_px), Image.LANCZOS)
    return img


def _render_tile(halo_data, field_idx, theta, phi, n_bins):
    pt, wf, cmap, inv, _ = FIELDS[field_idx]
    p = halo_data.get(pt)
    if p is None:
        return Image.fromarray(np.zeros((n_bins, n_bins, 3), np.uint8))
    x = p["x"];  y = p["y"];  z = p["z"]
    if wf == "temperature" and "temperature" in p:
        weights = p["mass"] * p["temperature"]
    else:
        weights = p["mass"]
    img = make_proj(x, y, z, weights, theta, phi,
                    n_bins=n_bins, cmap_name=cmap, invert_cmap=inv, size_px=n_bins)
    return add_glow(img, radius=5, intensity=0.22)


# ── Scene generator ───────────────────────────────────────────────────────────

def scene_synced_grid_rotation(
        left_tags, left_hdf5,
        right_tags, right_hdf5,
        scene_title,
        left_label, right_label,
        left_note="", right_note="",
        catalog_path=None,
        col_idx=0,
        duration=5.0,
        n_azimuthal=2,
        phi_max=np.pi / 2,
        n_bins=PROJ,
        field_cycle_sec=1.25,
        xfade_sec=0.28,
        fade_in_sec=0.45,
        fade_out_sec=0.45):
    """
    Yield 1920×1080 RGB frames for the synced 3-panel scene:
      LEFT 2×2 relaxed | CENTER profiles | RIGHT 2×2 unrelaxed

    Parameters
    ----------
    left_tags/right_tags : 4 unique_tag values for each side
    left_hdf5/right_hdf5 : particle HDF5 files
    scene_title          : bottom caption
    left_label           : top-left panel label
    right_label          : top-right panel label
    catalog_path         : path to halo catalog HDF5 (for profile computation)
    col_idx              : 0-3 — which profile comparison column to show
    """
    n_frames    = int(duration * FPS)
    frames_fin  = int(fade_in_sec  * FPS)
    frames_fout = int(fade_out_sec * FPS)

    # ── Pre-compute profile panel images ──────────────────────────────────────
    if catalog_path is not None and os.path.exists(catalog_path):
        print("  Pre-computing radial profiles …")
        prof_data = compute_profiles_for_scene(catalog_path, col_idx)
        img_prof_dark, img_prof_relax, img_prof_both = render_profile_panel(
            prof_data,
            relax_label   = left_label.split("·")[-1].strip() if "·" in left_label else left_label,
            unrelax_label = right_label.split("·")[-1].strip() if "·" in right_label else right_label,
        )
        has_profiles = True
    else:
        print("  WARNING: catalog not found — skipping profile panel")
        img_prof_dark = Image.new("RGB", (PROF_W, PROF_H), (6, 9, 15))
        img_prof_relax = img_prof_dark
        img_prof_both  = img_prof_dark
        has_profiles   = False

    # ── Pre-load halo particles ───────────────────────────────────────────────
    print(f"  Loading LEFT group ({left_label}) …")
    left_data  = load_group_particles(left_hdf5,  list(left_tags),  ("dm", "star", "gas"))
    print(f"  Loading RIGHT group ({right_label}) …")
    right_data = load_group_particles(right_hdf5, list(right_tags), ("dm", "star", "gas"))

    ordered_data = [left_data.get(int(t))  for t in left_tags] + \
                   [right_data.get(int(t)) for t in right_tags]

    # ── Pre-build text overlays ───────────────────────────────────────────────
    # Group labels + notes in header area of each side panel
    label_ov = make_text_overlay([
        {"text": left_label,
         "x": SIDE_W // 2, "y": 22,
         "size": 22, "color_rgb": COL_RELAX_RGB, "bold": True, "stroke_w": 2},
        {"text": left_note,
         "x": SIDE_W // 2, "y": 46,
         "size": 12, "color_rgb": (100, 160, 190), "bold": False, "stroke_w": 1},
        {"text": right_label,
         "x": RIGHT_X + SIDE_W // 2, "y": 22,
         "size": 22, "color_rgb": COL_UNRELAX_RGB, "bold": True, "stroke_w": 2},
        {"text": right_note,
         "x": RIGHT_X + SIDE_W // 2, "y": 46,
         "size": 12, "color_rgb": (190, 130, 100), "bold": False, "stroke_w": 1},
    ])

    # Split scene_title at ": " for 2-line display at top of frame
    _title_parts = scene_title.split(": ", 1)
    _title_line1 = _title_parts[0]
    _title_line2 = _title_parts[1] if len(_title_parts) > 1 else ""
    title_ov = make_text_overlay([
        {"text": _title_line1,
         "x": W // 2, "y": 16,
         "size": 19, "color_rgb": (240, 246, 255), "bold": True, "stroke_w": 2},
        {"text": _title_line2,
         "x": W // 2, "y": 44,
         "size": 17, "color_rgb": (195, 215, 245), "bold": True, "stroke_w": 2},
    ])

    # Field name overlays: one per field, for LEFT panel and RIGHT panel separately
    # (no longer shown in center — placed at bottom of header on each side panel)
    field_name_ovs_L = []
    field_name_ovs_R = []
    for _, _, cmap, _, lbl in FIELDS:
        accent = FIELD_ACCENT_RGB.get(cmap, (200, 200, 200))
        ov_L = make_text_overlay([
            {"text": lbl,
             "x": SIDE_W // 2, "y": 60,
             "size": 13, "color_rgb": accent, "bold": False, "stroke_w": 1},
        ])
        ov_R = make_text_overlay([
            {"text": lbl,
             "x": RIGHT_X + SIDE_W // 2, "y": 60,
             "size": 13, "color_rgb": accent, "bold": False, "stroke_w": 1},
        ])
        field_name_ovs_L.append(ov_L)
        field_name_ovs_R.append(ov_R)

    # Profile timing within the scene
    t_prof_start   = 0.4    # profiles panel fades in
    t_relax_start  = 0.7    # relaxed lines appear
    t_unrelax_start= 2.3    # unrelaxed lines appear
    t_hold_end     = duration - fade_out_sec

    xfade_frac = xfade_sec / field_cycle_sec

    # ── Frame loop ────────────────────────────────────────────────────────────
    print(f"  Generating {n_frames} frames …")

    for i in range(n_frames):
        t = i / FPS

        # Global fade
        if i < frames_fin:
            fade = smoothstep(i / max(frames_fin, 1))
        elif i >= n_frames - frames_fout and frames_fout > 0:
            fade = smoothstep(1 - (i - (n_frames - frames_fout)) / max(frames_fout, 1))
        else:
            fade = 1.0

        # Rotation angles (same for all halos)
        t_norm = t / duration
        theta  = 2 * np.pi * n_azimuthal * t_norm
        phi    = phi_max * np.sin(2 * np.pi * t_norm)

        # Field cycling
        cycle_pos   = (t / field_cycle_sec) % N_FIELDS
        fi          = int(cycle_pos) % N_FIELDS
        fj          = (fi + 1) % N_FIELDS
        within_slot = cycle_pos - int(cycle_pos)
        xfade_alpha = max(0.0, (within_slot - (1.0 - xfade_frac)) / xfade_frac)

        # Profile animation alphas
        a_prof   = smoothstep(min(max(t - t_prof_start,   0) / 0.5, 1)) * fade
        a_relax  = smoothstep(min(max(t - t_relax_start,  0) / 0.6, 1)) * fade
        a_unrelax= smoothstep(min(max(t - t_unrelax_start,0) / 0.6, 1)) * fade

        # ── Render canvas ─────────────────────────────────────────────────────
        canvas = Image.new("RGB", (W, H), (0, 0, 0))

        # Halo tiles (left 4 + right 4)
        for tile_idx, (tx, ty) in enumerate(TILE_XY):
            hdata = ordered_data[tile_idx]
            if hdata is None:
                continue
            img_fi = _render_tile(hdata, fi, theta, phi, n_bins)
            if xfade_alpha > 0.0:
                img_fj  = _render_tile(hdata, fj, theta, phi, n_bins)
                alpha_s = smoothstep(xfade_alpha)
                arr     = (np.array(img_fi, np.float32) * (1 - alpha_s) +
                           np.array(img_fj, np.float32) * alpha_s).clip(0, 255).astype(np.uint8)
                tile_img = Image.fromarray(arr)
            else:
                tile_img = img_fi
            canvas.paste(tile_img, (tx, ty))

        # Center profile panel (animated)
        if has_profiles and a_prof > 0:
            if a_unrelax > 0:
                a_s = smoothstep(a_unrelax)
                prof_display = blend(img_prof_relax, img_prof_both, a_s)
            elif a_relax > 0:
                a_s = smoothstep(a_relax)
                prof_display = blend(img_prof_dark, img_prof_relax, a_s)
            else:
                prof_display = img_prof_dark

            if a_prof < 1.0:
                arr_p = (np.array(prof_display, np.float32) * a_prof).clip(0, 255).astype(np.uint8)
                prof_display = Image.fromarray(arr_p)

            canvas.paste(prof_display, (PROF_X, PROF_Y))

        # ── Separators ────────────────────────────────────────────────────────
        draw = ImageDraw.Draw(canvas)
        r, g, b = SEP_COL
        # Left separator (between left halos and center)
        draw.rectangle([SIDE_W, 0, SIDE_W + SEP - 1, H], fill=(r, g, b))
        # Right separator (between center and right halos)
        x2 = RIGHT_X - SEP
        draw.rectangle([x2, 0, x2 + SEP - 1, H], fill=(r, g, b))

        # Faint inner grid lines within each halo panel
        for side_x in (0, RIGHT_X):
            mid_x = side_x + TILE_W
            draw.rectangle([mid_x - 1, HEADER_H, mid_x + 1, H - FOOTER_H], fill=(30, 32, 38))
            mid_y = HEADER_H + TILE_H
            draw.rectangle([side_x, mid_y - 1, side_x + SIDE_W - 1, mid_y + 1], fill=(30, 32, 38))

        # ── Vignette + overlays ───────────────────────────────────────────────
        canvas = add_vignette(canvas, strength=0.20)

        if fade < 1.0:
            canvas = Image.fromarray(
                (np.array(canvas, np.float32) * fade).clip(0, 255).astype(np.uint8))

        canvas = composite_rgba(canvas, label_ov,  alpha_mult=min(fade, 0.95))
        canvas = composite_rgba(canvas, title_ov,  alpha_mult=min(fade, 0.85))

        # Field name overlays on left and right panels (not center)
        ov_L_fi = field_name_ovs_L[fi]
        ov_R_fi = field_name_ovs_R[fi]
        ov_L_fj = field_name_ovs_L[fj]
        ov_R_fj = field_name_ovs_R[fj]

        alpha_fi = min(fade, 0.88) * (1 - smoothstep(xfade_alpha))
        alpha_fj = min(fade, 0.88) * smoothstep(xfade_alpha)

        canvas = composite_rgba(canvas, ov_L_fi, alpha_mult=alpha_fi)
        canvas = composite_rgba(canvas, ov_R_fi, alpha_mult=alpha_fi)
        if xfade_alpha > 0.0:
            canvas = composite_rgba(canvas, ov_L_fj, alpha_mult=alpha_fj)
            canvas = composite_rgba(canvas, ov_R_fj, alpha_mult=alpha_fj)

        yield canvas
