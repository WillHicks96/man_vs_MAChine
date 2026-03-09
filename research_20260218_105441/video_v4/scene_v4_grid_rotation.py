"""
scene_v4_grid_rotation.py — Synced 2-column 2×2 grid rotation (video v4).

Differences from v3:
  - 3 fields only: Dark Matter, Stars, Gas Temperature  (Gas mass dropped)
  - Profile centre panel: both relaxed + unrelaxed lines shown from the start
    (no staged 2-phase reveal)
  - Tile renders are 2× super-sampled (680×680 histogram → 340×340 output)
    for sharper pixel quality
  - Profile panel rendered at DPI=120 (sharper text/lines vs v3's DPI=100)

Layout is identical to v3:
  LEFT 720px | 8px sep | CENTER 464px profiles | 8px sep | RIGHT 720px
"""

import sys
import os

_V2_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "video_v2")
_V3_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "video_v3")
sys.path.insert(0, _V2_DIR)
sys.path.insert(0, _V3_DIR)

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
from scene_v3_grid_rotation import (
    # Layout constants (same as v3)
    SIDE_W, SEP, SEP_COL, CENTER_W,
    HEADER_H, FOOTER_H, GRID_H,
    TILE_W, TILE_H, PROJ, pad_x, pad_y,
    RIGHT_X, TILE_XY,
    PROF_X, PROF_Y, PROF_W, PROF_H,
    # Style constants
    PROFILE_ROW_TITLES, COL_RELAX_RGB, COL_UNRELAX_RGB,
    # Shared helpers (unchanged)
    compute_profiles_for_scene,
    load_group_particles,
    make_proj,
)
from PIL import Image, ImageDraw


# ── 3-field definition ────────────────────────────────────────────────────────
#   Gas mass (index 2 in v3) is intentionally omitted here.

FIELDS_V4 = [
    ("dm",   "mass",        CMAP_DM,    False, "Dark Matter"),
    ("star", "mass",        CMAP_STARS, False, "Stars"),
    ("gas",  "temperature", CMAP_TEMP,  True,  "Gas Temperature"),
]
N_FIELDS_V4 = len(FIELDS_V4)


# ── Profile panel (v4): both lines visible immediately, DPI=120 ───────────────

def render_profile_panel_v4(profile_data, relax_label, unrelax_label,
                              panel_w=PROF_W, panel_h=PROF_H):
    """
    Pre-render 2 PIL RGB images:
      img_dark : dark background + axis scaffolding (no data lines)
      img_both : same + relaxed (cyan) and unrelaxed (orange) lines together

    Uses DPI=120 for sharper text/lines compared to v3's DPI=100.
    """
    DARK_BG = '#06090f'
    C_AX    = '#8090a8'
    C_GRID  = '#141824'
    C_R     = tuple(c / 255 for c in COL_RELAX_RGB)
    C_U     = tuple(c / 255 for c in COL_UNRELAX_RGB)

    DPI  = 120
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
                sp.set_color('#5a6a80')
                sp.set_linewidth(1.2)
            ax.set_xscale('log')
            ax.set_yscale('log' if log_scales[i] else 'linear')
            ax.grid(True, color=C_GRID, lw=0.35, which='both')
            ax.set_xlim(0.02, 2.0)
            ax.set_ylim(*ylimits[i])
            ax.set_ylabel(ylabels[i], fontsize=8.5, color=C_AX)
            for rv in (0.15, 0.5, 1.0):
                ax.axvline(rv, color='#2a3040', lw=0.5, ls='-', zorder=0)
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

    # Image 1: dark bg + axes only
    fig, _ = _make_fig_and_axes()
    img_dark = _to_pil(fig, panel_w, panel_h)

    # Image 2: both relaxed and unrelaxed lines together
    fig, axes = _make_fig_and_axes()
    for i, ax in enumerate(axes):
        med_r = profs_r[i]
        med_u = profs_u[i]
        vm_r  = np.isfinite(med_r) & (med_r > 0)
        vm_u  = np.isfinite(med_u) & (med_u > 0)
        if vm_r.sum() > 3:
            ax.plot(r_grid[vm_r], med_r[vm_r],
                    color=C_R, lw=1.8, ls='-',
                    solid_capstyle='round', label=relax_label)
        if vm_u.sum() > 3:
            ax.plot(r_grid[vm_u], med_u[vm_u],
                    color=C_U, lw=1.8, ls='-',
                    solid_capstyle='round', label=unrelax_label)
        if i == 0:
            ax.legend(fontsize=8.0, loc='upper left',
                      facecolor='#0e1320', edgecolor='#2a3040',
                      labelcolor=C_AX, framealpha=0.9, handlelength=1.2)
    img_both = _to_pil(fig, panel_w, panel_h)

    return img_dark, img_both


# ── Tile renderer (2× super-sampled) ─────────────────────────────────────────

def _render_tile_v4(halo_data, field_idx, theta, phi, n_bins):
    """
    Render a single halo tile.  Histogram is computed at 2×n_bins resolution
    then downsampled to n_bins for crisp, alias-free output.
    """
    pt, wf, cmap, inv, _ = FIELDS_V4[field_idx]
    p = halo_data.get(pt)
    if p is None:
        return Image.fromarray(np.zeros((n_bins, n_bins, 3), np.uint8))
    x = p["x"]
    y = p["y"]
    z = p["z"]
    if wf == "temperature" and "temperature" in p:
        weights = p["mass"] * p["temperature"]
    else:
        weights = p["mass"]
    # 2× super-sample: histogram at 2·n_bins → LANCZOS resize to n_bins
    img = make_proj(x, y, z, weights, theta, phi,
                    n_bins=n_bins * 2, cmap_name=cmap, invert_cmap=inv,
                    size_px=n_bins)
    return add_glow(img, radius=5, intensity=0.22)


# ── Scene generator ───────────────────────────────────────────────────────────

def scene_synced_grid_rotation_v4(
        left_tags, left_hdf5,
        right_tags, right_hdf5,
        scene_title,
        left_label, right_label,
        left_note="", right_note="",
        catalog_path=None,
        col_idx=0,
        duration=16.0,
        n_azimuthal=2,
        phi_max=np.pi / 2,
        n_bins=PROJ,
        field_cycle_sec=None,     # default: 3 fields fill exactly one cycle
        xfade_sec=0.5,
        fade_in_sec=0.6,
        fade_out_sec=0.6):
    """
    Yield 1920×1080 RGB frames.

    Left 2×2 panel  : relaxed halos (left_tags / left_hdf5)
    Centre panel     : radial profile comparison — both lines shown at once
    Right 2×2 panel  : unrelaxed halos (right_tags / right_hdf5)

    3 fields cycle: Dark Matter → Stars → Gas Temperature
    """
    if field_cycle_sec is None:
        field_cycle_sec = duration / N_FIELDS_V4   # one clean pass

    n_frames    = int(duration * FPS)
    frames_fin  = int(fade_in_sec  * FPS)
    frames_fout = int(fade_out_sec * FPS)

    # ── Pre-compute profile panel (2 images: dark, both) ──────────────────────
    if catalog_path is not None and os.path.exists(catalog_path):
        print("  Pre-computing radial profiles …")
        prof_data = compute_profiles_for_scene(catalog_path, col_idx)
        _rl = left_label.split("·")[-1].strip()  if "·" in left_label  else left_label
        _ul = right_label.split("·")[-1].strip() if "·" in right_label else right_label
        img_prof_dark, img_prof_both = render_profile_panel_v4(prof_data, _rl, _ul)
        has_profiles = True
    else:
        print("  WARNING: catalog not found — skipping profile panel")
        img_prof_dark = Image.new("RGB", (PROF_W, PROF_H), (6, 9, 15))
        img_prof_both = img_prof_dark
        has_profiles  = False

    # ── Pre-load particles ────────────────────────────────────────────────────
    print(f"  Loading LEFT  ({left_label}) …")
    left_data  = load_group_particles(left_hdf5,  list(left_tags),  ("dm", "star", "gas"))
    print(f"  Loading RIGHT ({right_label}) …")
    right_data = load_group_particles(right_hdf5, list(right_tags), ("dm", "star", "gas"))

    ordered_data = ([left_data.get(int(t))  for t in left_tags] +
                    [right_data.get(int(t)) for t in right_tags])

    # ── Pre-build text overlays ───────────────────────────────────────────────
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

    _parts     = scene_title.split(": ", 1)
    title_ov   = make_text_overlay([
        {"text": _parts[0],
         "x": W // 2, "y": 16,
         "size": 19, "color_rgb": (240, 246, 255), "bold": True, "stroke_w": 2},
        {"text": _parts[1] if len(_parts) > 1 else "",
         "x": W // 2, "y": 44,
         "size": 17, "color_rgb": (195, 215, 245), "bold": True, "stroke_w": 2},
    ])

    field_name_ovs_L = []
    field_name_ovs_R = []
    for _, _, cmap, _, lbl in FIELDS_V4:
        accent = FIELD_ACCENT_RGB.get(cmap, (200, 200, 200))
        field_name_ovs_L.append(make_text_overlay([
            {"text": lbl, "x": SIDE_W // 2, "y": 60,
             "size": 13, "color_rgb": accent, "bold": False, "stroke_w": 1},
        ]))
        field_name_ovs_R.append(make_text_overlay([
            {"text": lbl, "x": RIGHT_X + SIDE_W // 2, "y": 60,
             "size": 13, "color_rgb": accent, "bold": False, "stroke_w": 1},
        ]))

    xfade_frac   = xfade_sec / field_cycle_sec
    t_prof_start = 0.5    # profile panel fades in at 0.5 s

    # ── Frame loop ────────────────────────────────────────────────────────────
    print(f"  Generating {n_frames} frames …")

    for i in range(n_frames):
        t = i / FPS

        # Global fade-in / fade-out
        if i < frames_fin:
            fade = smoothstep(i / max(frames_fin, 1))
        elif i >= n_frames - frames_fout and frames_fout > 0:
            fade = smoothstep(1 - (i - (n_frames - frames_fout)) / max(frames_fout, 1))
        else:
            fade = 1.0

        # Rotation angles
        t_norm = t / duration
        theta  = 2 * np.pi * n_azimuthal * t_norm
        phi    = phi_max * np.sin(2 * np.pi * t_norm)

        # Field cycling (3 fields)
        cycle_pos   = (t / field_cycle_sec) % N_FIELDS_V4
        fi          = int(cycle_pos) % N_FIELDS_V4
        fj          = (fi + 1) % N_FIELDS_V4
        within_slot = cycle_pos - int(cycle_pos)
        xfade_alpha = max(0.0, (within_slot - (1.0 - xfade_frac)) / xfade_frac)

        # Profile fade-in (both lines together)
        a_prof = smoothstep(min(max(t - t_prof_start, 0) / 0.55, 1)) * fade

        # ── Canvas ────────────────────────────────────────────────────────────
        canvas = Image.new("RGB", (W, H), (0, 0, 0))

        # Halo tiles
        for tile_idx, (tx, ty) in enumerate(TILE_XY):
            hdata = ordered_data[tile_idx]
            if hdata is None:
                continue
            img_fi = _render_tile_v4(hdata, fi, theta, phi, n_bins)
            if xfade_alpha > 0.0:
                img_fj  = _render_tile_v4(hdata, fj, theta, phi, n_bins)
                alpha_s = smoothstep(xfade_alpha)
                arr = (np.array(img_fi, np.float32) * (1 - alpha_s) +
                       np.array(img_fj, np.float32) * alpha_s).clip(0, 255).astype(np.uint8)
                tile_img = Image.fromarray(arr)
            else:
                tile_img = img_fi
            canvas.paste(tile_img, (tx, ty))

        # Centre profile panel — show both lines immediately
        if has_profiles and a_prof > 0:
            if a_prof < 1.0:
                prof_display = blend(img_prof_dark, img_prof_both, smoothstep(a_prof))
            else:
                prof_display = img_prof_both
            canvas.paste(prof_display, (PROF_X, PROF_Y))

        # Separators
        draw = ImageDraw.Draw(canvas)
        r, g, b = SEP_COL
        draw.rectangle([SIDE_W, 0, SIDE_W + SEP - 1, H], fill=(r, g, b))
        x2 = RIGHT_X - SEP
        draw.rectangle([x2, 0, x2 + SEP - 1, H], fill=(r, g, b))

        for side_x in (0, RIGHT_X):
            mid_x = side_x + TILE_W
            draw.rectangle([mid_x - 1, HEADER_H, mid_x + 1, H - FOOTER_H],
                           fill=(30, 32, 38))
            mid_y = HEADER_H + TILE_H
            draw.rectangle([side_x, mid_y - 1, side_x + SIDE_W - 1, mid_y + 1],
                           fill=(30, 32, 38))

        # Vignette + global fade
        canvas = add_vignette(canvas, strength=0.20)

        if fade < 1.0:
            canvas = Image.fromarray(
                (np.array(canvas, np.float32) * fade).clip(0, 255).astype(np.uint8))

        # Text overlays
        canvas = composite_rgba(canvas, label_ov, alpha_mult=min(fade, 0.95))
        canvas = composite_rgba(canvas, title_ov, alpha_mult=min(fade, 0.85))

        alpha_fi = min(fade, 0.88) * (1 - smoothstep(xfade_alpha))
        alpha_fj = min(fade, 0.88) * smoothstep(xfade_alpha)

        canvas = composite_rgba(canvas, field_name_ovs_L[fi], alpha_mult=alpha_fi)
        canvas = composite_rgba(canvas, field_name_ovs_R[fi], alpha_mult=alpha_fi)
        if xfade_alpha > 0.0:
            canvas = composite_rgba(canvas, field_name_ovs_L[fj], alpha_mult=alpha_fj)
            canvas = composite_rgba(canvas, field_name_ovs_R[fj], alpha_mult=alpha_fj)

        yield canvas
