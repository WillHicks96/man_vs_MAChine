"""
scene_v5_grid_rotation.py — Split-rotation synced grid scene (video v5).

New in v5 vs v4:
  - Staged profile reveal (like v3): relaxed line appears first, then
    unrelaxed line fades in.
  - Panel rotation is tied to the profile reveal:
      Phase 1 (before unrelaxed appears):
          LEFT  panel (relaxed halos)   → rotates normally
          RIGHT panel (unrelaxed halos) → holds at face-on (θ=0, φ=0)
      Phase 2 (after unrelaxed appears):
          LEFT  panel → freezes at its angle when the switch occurred
          RIGHT panel → begins rotating at the same angular speed

    The switch is smoothed over ~1.2 s centred on t_unrelax_start to
    avoid a jarring snap.

Everything else is identical to v4:
  - 3 fields: Dark Matter, Stars, Gas Temperature
  - 2× super-sampled tile renders (680×680 histogram → 340×340 output)
  - Profile panel at DPI=120
"""

import sys
import os

_V2_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "video_v2")
_V3_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "video_v3")
_V4_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "video_v4")
sys.path.insert(0, _V2_DIR)
sys.path.insert(0, _V3_DIR)
sys.path.insert(0, _V4_DIR)

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from video_utils import (
    W, H, FPS,
    CMAP_DM, CMAP_STARS, CMAP_TEMP,
    FIELD_ACCENT_RGB,
    smoothstep, blend, add_glow, add_vignette, composite_rgba, make_text_overlay,
)
from scene_v3_grid_rotation import (
    SIDE_W, SEP, SEP_COL, CENTER_W,
    HEADER_H, FOOTER_H, GRID_H,
    TILE_W, TILE_H, PROJ, pad_x, pad_y,
    RIGHT_X, TILE_XY,
    PROF_X, PROF_Y, PROF_W, PROF_H,
    PROFILE_ROW_TITLES, COL_RELAX_RGB, COL_UNRELAX_RGB,
    compute_profiles_for_scene, load_group_particles, make_proj,
)
from scene_v4_grid_rotation import FIELDS_V4, N_FIELDS_V4, _render_tile_v4
from PIL import Image, ImageDraw


# ── Profile panel (v5): 3 images — dark / relax-only / both ──────────────────

def render_profile_panel_v5(profile_data, relax_label, unrelax_label,
                              panel_w=PROF_W, panel_h=PROF_H):
    """
    Pre-render 3 PIL RGB images at DPI=120:
      img_dark  : dark background + axis scaffolding (no data lines)
      img_relax : same + relaxed (cyan) line only
      img_both  : same + both relaxed (cyan) and unrelaxed (orange) lines
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

    # ── Image 1: dark bg only ────────────────────────────────────────────────
    fig, _ = _make_fig_and_axes()
    img_dark = _to_pil(fig, panel_w, panel_h)

    # ── Image 2: relaxed line only ───────────────────────────────────────────
    fig, axes = _make_fig_and_axes()
    for i, ax in enumerate(axes):
        med = profs_r[i]
        vm  = np.isfinite(med) & (med > 0)
        if vm.sum() > 3:
            ax.plot(r_grid[vm], med[vm], color=C_R, lw=1.8, ls='-',
                    solid_capstyle='round', label=relax_label)
        if i == 0:
            ax.legend(fontsize=8.0, loc='upper left',
                      facecolor='#0e1320', edgecolor='#2a3040',
                      labelcolor=C_AX, framealpha=0.9, handlelength=1.2)
    img_relax = _to_pil(fig, panel_w, panel_h)

    # ── Image 3: both lines ──────────────────────────────────────────────────
    fig, axes = _make_fig_and_axes()
    for i, ax in enumerate(axes):
        med_r = profs_r[i]
        med_u = profs_u[i]
        vm_r  = np.isfinite(med_r) & (med_r > 0)
        vm_u  = np.isfinite(med_u) & (med_u > 0)
        if vm_r.sum() > 3:
            ax.plot(r_grid[vm_r], med_r[vm_r], color=C_R, lw=1.8, ls='-',
                    solid_capstyle='round', label=relax_label)
        if vm_u.sum() > 3:
            ax.plot(r_grid[vm_u], med_u[vm_u], color=C_U, lw=1.8, ls='-',
                    solid_capstyle='round', label=unrelax_label)
        if i == 0:
            ax.legend(fontsize=8.0, loc='upper left',
                      facecolor='#0e1320', edgecolor='#2a3040',
                      labelcolor=C_AX, framealpha=0.9, handlelength=1.2)
    img_both = _to_pil(fig, panel_w, panel_h)

    return img_dark, img_relax, img_both


# ── Scene generator ───────────────────────────────────────────────────────────

def scene_synced_grid_rotation_v5(
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
        field_cycle_sec=None,
        xfade_sec=0.5,
        fade_in_sec=0.6,
        fade_out_sec=0.6,
        # Profile reveal timing
        t_relax_start=0.9,
        t_unrelax_start=7.0,
        # Rotation-switch crossfade (seconds, centred on t_unrelax_start)
        xover_dur=1.2):
    """
    Yield 1920×1080 RGB frames.

    Phase 1 (0 → t_unrelax_start):
        Profile centre panel fades in with relaxed line only.
        LEFT  2×2 panel (relaxed halos)   → rotating
        RIGHT 2×2 panel (unrelaxed halos) → stationary at face-on (θ=0, φ=0)

    Phase 2 (t_unrelax_start → end):
        Unrelaxed line fades into the profile panel.
        LEFT  panel → freezes at its angle at the switch point
        RIGHT panel → begins rotating at the same angular speed as left did

    The panel switch is smoothed over xover_dur seconds centred on
    t_unrelax_start to avoid a jarring snap.
    """
    if field_cycle_sec is None:
        field_cycle_sec = duration / N_FIELDS_V4

    n_frames    = int(duration * FPS)
    frames_fin  = int(fade_in_sec  * FPS)
    frames_fout = int(fade_out_sec * FPS)

    # Angular rate (same for left before switch and right after switch)
    omega     = 2 * np.pi * n_azimuthal / duration
    phi_omega = 2 * np.pi / duration

    # The angle at which the LEFT panel will freeze
    theta_L_frozen = omega * t_unrelax_start
    phi_L_frozen   = phi_max * np.sin(phi_omega * t_unrelax_start)

    # Crossover window
    t_xover_lo = t_unrelax_start - xover_dur / 2
    t_xover_hi = t_unrelax_start + xover_dur / 2

    # ── Pre-compute profile panel (3 images) ──────────────────────────────────
    if catalog_path is not None and os.path.exists(catalog_path):
        print("  Pre-computing radial profiles …")
        prof_data = compute_profiles_for_scene(catalog_path, col_idx)
        _rl = left_label.split("·")[-1].strip()  if "·" in left_label  else left_label
        _ul = right_label.split("·")[-1].strip() if "·" in right_label else right_label
        img_prof_dark, img_prof_relax, img_prof_both = render_profile_panel_v5(
            prof_data, _rl, _ul)
        has_profiles = True
    else:
        print("  WARNING: catalog not found — skipping profile panel")
        _blank = Image.new("RGB", (PROF_W, PROF_H), (6, 9, 15))
        img_prof_dark = img_prof_relax = img_prof_both = _blank
        has_profiles = False

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

    _parts   = scene_title.split(": ", 1)
    title_ov = make_text_overlay([
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
    t_prof_start = 0.5   # profile panel fade-in start

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

        # ── Per-panel rotation angles ──────────────────────────────────────
        #
        # Phase 1 (t <= t_xover_lo):  left rotates, right is face-on (0,0)
        # Phase 2 (t >= t_xover_hi):  left frozen, right rotates from t_switch
        # Crossover: smoothly blend between the two states

        if t <= t_xover_lo:
            # Phase 1: left rotating, right face-on
            theta_L = omega * t
            phi_L   = phi_max * np.sin(phi_omega * t)
            theta_R = 0.0
            phi_R   = 0.0

        elif t >= t_xover_hi:
            # Phase 2: left frozen, right rotating
            theta_L = theta_L_frozen
            phi_L   = phi_L_frozen
            dt      = t - t_unrelax_start
            theta_R = omega * dt
            phi_R   = phi_max * np.sin(phi_omega * dt)

        else:
            # Crossover blend (smooth transition)
            alpha   = smoothstep((t - t_xover_lo) / xover_dur)
            # Phase-1 values at this t
            tL_1    = omega * t
            phL_1   = phi_max * np.sin(phi_omega * t)
            # Phase-2 values at this t
            dt      = max(t - t_unrelax_start, 0.0)
            tR_2    = omega * dt
            phR_2   = phi_max * np.sin(phi_omega * dt)
            # Blend
            theta_L = (1 - alpha) * tL_1  + alpha * theta_L_frozen
            phi_L   = (1 - alpha) * phL_1 + alpha * phi_L_frozen
            theta_R = (1 - alpha) * 0.0   + alpha * tR_2
            phi_R   = (1 - alpha) * 0.0   + alpha * phR_2

        # ── Field cycling ──────────────────────────────────────────────────
        cycle_pos   = (t / field_cycle_sec) % N_FIELDS_V4
        fi          = int(cycle_pos) % N_FIELDS_V4
        fj          = (fi + 1) % N_FIELDS_V4
        within_slot = cycle_pos - int(cycle_pos)
        xfade_alpha = max(0.0, (within_slot - (1.0 - xfade_frac)) / xfade_frac)

        # ── Profile panel alphas (staged reveal) ───────────────────────────
        a_prof    = smoothstep(min(max(t - t_prof_start,    0) / 0.5, 1)) * fade
        a_relax   = smoothstep(min(max(t - t_relax_start,   0) / 0.6, 1)) * fade
        a_unrelax = smoothstep(min(max(t - t_unrelax_start, 0) / 0.8, 1)) * fade

        # ── Canvas ────────────────────────────────────────────────────────
        canvas = Image.new("RGB", (W, H), (0, 0, 0))

        # Halo tiles — LEFT (indices 0-3) and RIGHT (indices 4-7) use
        # their respective rotation angles
        for tile_idx, (tx, ty) in enumerate(TILE_XY):
            hdata = ordered_data[tile_idx]
            if hdata is None:
                continue
            t_theta, t_phi = (theta_L, phi_L) if tile_idx < 4 else (theta_R, phi_R)

            img_fi = _render_tile_v4(hdata, fi, t_theta, t_phi, n_bins)
            if xfade_alpha > 0.0:
                img_fj  = _render_tile_v4(hdata, fj, t_theta, t_phi, n_bins)
                alpha_s = smoothstep(xfade_alpha)
                arr = (np.array(img_fi, np.float32) * (1 - alpha_s) +
                       np.array(img_fj, np.float32) * alpha_s).clip(0, 255).astype(np.uint8)
                tile_img = Image.fromarray(arr)
            else:
                tile_img = img_fi
            canvas.paste(tile_img, (tx, ty))

        # Centre profile panel (staged reveal)
        if has_profiles and a_prof > 0:
            if a_unrelax > 0:
                prof_display = blend(img_prof_relax, img_prof_both,
                                     smoothstep(a_unrelax))
            elif a_relax > 0:
                prof_display = blend(img_prof_dark, img_prof_relax,
                                     smoothstep(a_relax))
            else:
                prof_display = img_prof_dark

            if a_prof < 1.0:
                arr_p = (np.array(prof_display, np.float32) * a_prof
                         ).clip(0, 255).astype(np.uint8)
                prof_display = Image.fromarray(arr_p)

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
