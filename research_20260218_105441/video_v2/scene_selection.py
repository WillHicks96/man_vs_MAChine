"""
scene_selection.py — Animated selection criteria reveal.

Shows a 4-column × 3-row grid of 12 halos (3 from each of four groups)
arranged in a Latin-square shuffle so no group clusters by column.

All halos belong to R₁ (passed the δ₁ centre-of-mass offset criterion).
The animation progressively reveals which additional criteria each halo fails:

  Phase 1  (0 – 1.5 s)   Fade in: all 12 halos shown with Dark Matter field
  Phase 2  (1.5 – 4.0 s) Red outer boxes appear around every halo  +  R₁ legend
  Phase 3  (4.0 – 6.5 s) R₁∖R₂ halos: DM → Gas crossfade + pink inner box
  Phase 4  (6.5 – 9.0 s) R₁∖R₃ halos: DM → Gas crossfade + blue inner box
  Phase 5  (9.0 – 11.5 s)R₁∖R₄ halos: DM → Gas Temperature crossfade + yellow box
  Phase 6  (11.5 – 12.5 s) Hold → fade out

Total ≈ 12.5 s

Group → box colour mapping
--------------------------
  R₁        all halos get Red outer border   (220,  60,  60)
  R₁∖R₂    Pink  inner border  (255, 150, 200)  Gas field
  R₁∖R₃    Blue  inner border  ( 80, 140, 255)  Gas field
  R₁∖R₄    Yellow inner border (255, 220,  50)  Gas Temperature field

Functions
---------
prepare_selection_renders(renders_dir)
    Pre-render all 21 tiles (cached).

scene_selection_reveal(renders_dir, total_sec, ...)
    Generator yielding animated frames.

Usage
-----
    from scene_selection import prepare_selection_renders, scene_selection_reveal

    prepare_selection_renders(RENDERS_DIR)
    for frame in scene_selection_reveal(RENDERS_DIR):
        ...
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from video_utils import (
    W, H, FPS,
    PARTICLE_DIR, RENDERS_DIR,
    FILE_MAP, GROUP_SHORT_LABELS,
    smoothstep, blend, composite_rgba,
    make_text_overlay, render_field_image, get_top_halos,
)
from PIL import Image, ImageDraw
import numpy as np


# ── Grid geometry ───────────────────────────────────────────────────────────────

N_COLS      = 5
N_ROWS      = 3
MARGIN      = 15    # left/right margin (px)
GAP         = 6     # gap between cells (px)
HEADER_H    = 45    # top header area (title)
FOOTER_H    = 100   # bottom footer area (legend)

CELL_W = (W  - 2 * MARGIN  - (N_COLS - 1) * GAP) // N_COLS   # ≈ 373
CELL_H = (H  - HEADER_H - FOOTER_H - (N_ROWS - 1) * GAP) // N_ROWS  # ≈ 307

# Groups shown in the grid and how many halos to pull from each.
# 15 cells total: 3 (R1) + 4 + 4 + 4 = 15.
GROUPS_IN_GRID   = ["R1", "R1_notR2", "R1_notR3", "R1_notR4"]
N_PER_GROUP_MAP  = {"R1": 3, "R1_notR2": 4, "R1_notR3": 4, "R1_notR4": 4}

# 5×3 layout — shuffled so no group clusters by column.
# Each row contains one R1 halo and at least one from each "notR" group.
# (group, local_halo_idx_within_group)
GRID_LAYOUT = [
    # Row 0
    ("R1",       0), ("R1_notR2", 0), ("R1_notR3", 0), ("R1_notR4", 0), ("R1_notR2", 1),
    # Row 1
    ("R1_notR4", 1), ("R1",       1), ("R1_notR2", 2), ("R1_notR3", 1), ("R1_notR4", 2),
    # Row 2
    ("R1_notR3", 2), ("R1_notR4", 3), ("R1",       2), ("R1_notR2", 3), ("R1_notR3", 3),
]

# Alternate field index for the crossfade (None = no crossfade, stay DM)
ALT_FIELD = {
    "R1":       None,   # purely relaxed — no crossfade
    "R1_notR2": 2,      # Gas (δ₂ offset visible in gas distribution)
    "R1_notR3": 2,      # Gas (core entropy visible in gas)
    "R1_notR4": 3,      # Gas Temperature (TPI visible in temperature map)
}

# Box colours
BOX_OUTER_COLOR  = (220,  60,  60)   # red — all R₁ halos
BOX_INNER_COLORS = {
    "R1_notR2": (255, 150, 200),   # pink
    "R1_notR3": ( 80, 140, 255),   # blue
    "R1_notR4": (255, 220,  50),   # yellow
}


# ── Tile path helpers ───────────────────────────────────────────────────────────

def _tile_path(renders_dir, group, halo_idx, suffix="dm"):
    return os.path.join(renders_dir, f"sel_{group}_h{halo_idx}_{suffix}.png")


# ── Pre-render ──────────────────────────────────────────────────────────────────

def prepare_selection_renders(renders_dir=RENDERS_DIR):
    """
    Pre-render DM and alternate-field tiles for all 12 grid cells.
    Files are cached by name; only missing tiles are rendered.

    Returns
    -------
    dict  group → [(mass, tag), …]   (top halos by FoF mass)
    """
    os.makedirs(renders_dir, exist_ok=True)
    halos_by_group = {}

    for group in GROUPS_IN_GRID:
        hdf5 = os.path.join(PARTICLE_DIR, FILE_MAP[group])
        if not os.path.exists(hdf5):
            print(f"  WARNING: {hdf5} not found — skipping {group}")
            continue

        top = get_top_halos(hdf5, n=N_PER_GROUP_MAP[group])
        halos_by_group[group] = top

        for h_idx, (mass, tag) in enumerate(top):
            # DM tile (field 0) — always needed
            dm_path = _tile_path(renders_dir, group, h_idx, "dm")
            render_field_image(hdf5, tag, 0, dm_path, cache=True)

            # Alternate field tile — only for notR2/R3/R4
            af = ALT_FIELD[group]
            if af is not None:
                alt_path = _tile_path(renders_dir, group, h_idx, "alt")
                render_field_image(hdf5, tag, af, alt_path, cache=True)

    return halos_by_group


# ── Geometry helpers ────────────────────────────────────────────────────────────

def _cell_xy(cell_idx):
    """Return (x_off, y_off) top-left corner of cell *cell_idx* (row-major)."""
    row = cell_idx // N_COLS
    col = cell_idx % N_COLS
    x = MARGIN + col * (CELL_W + GAP)
    y = HEADER_H + row * (CELL_H + GAP)
    return x, y


def _make_box_overlay(positions, color_rgb, inset=0, border_w=4):
    """
    Draw colored rectangle outlines at the given cell positions.

    Parameters
    ----------
    positions  : List of (x_off, y_off) top-left corners
    color_rgb  : (r, g, b) border colour
    inset      : Pixels to inset the box from the cell edge (0 = outer border)
    border_w   : Border line width in pixels

    Returns
    -------
    PIL RGBA overlay image  (W × H, transparent background)
    """
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    r, g, b = color_rgb
    for (x0, y0) in positions:
        draw.rectangle(
            [x0 + inset, y0 + inset,
             x0 + CELL_W - 1 - inset, y0 + CELL_H - 1 - inset],
            outline=(r, g, b, 255),
            width=border_w,
        )
    return overlay


# ── Scene generator ─────────────────────────────────────────────────────────────

def scene_selection_reveal(renders_dir=RENDERS_DIR,
                            total_sec=12.5,
                            fade_in_sec=1.5,
                            fade_out_sec=1.0):
    """
    Yield 1920 × 1080 PIL RGB frames for the selection criteria reveal.

    All 12 grid halos initially appear as DM projections.  Colored boxes
    and field crossfades are progressively overlaid to expose which
    relaxation criteria each halo fails.

    Parameters
    ----------
    renders_dir  : Directory containing pre-rendered tile PNGs
    total_sec    : Total scene duration in seconds
    fade_in_sec  : Fade from black at the start
    fade_out_sec : Fade to black at the end
    """
    # ── Load all tiles ──────────────────────────────────────────────────────────
    dm_tiles  = {}   # (group, h_idx) → resized PIL RGB
    alt_tiles = {}   # (group, h_idx) → resized PIL RGB

    for group in GROUPS_IN_GRID:
        for h_idx in range(N_PER_GROUP_MAP[group]):
            dm_p = _tile_path(renders_dir, group, h_idx, "dm")
            if os.path.exists(dm_p):
                img = Image.open(dm_p).convert("RGB").resize(
                    (CELL_W, CELL_H), Image.LANCZOS)
            else:
                img = Image.new("RGB", (CELL_W, CELL_H), (8, 10, 18))
            dm_tiles[(group, h_idx)] = img

            if ALT_FIELD[group] is not None:
                alt_p = _tile_path(renders_dir, group, h_idx, "alt")
                if os.path.exists(alt_p):
                    aimg = Image.open(alt_p).convert("RGB").resize(
                        (CELL_W, CELL_H), Image.LANCZOS)
                else:
                    aimg = Image.new("RGB", (CELL_W, CELL_H), (8, 10, 18))
                alt_tiles[(group, h_idx)] = aimg

    # ── Pre-build box overlays (fixed; alpha is varied at composite time) ──────
    all_pos    = [_cell_xy(ci) for ci in range(len(GRID_LAYOUT))]
    notR2_pos  = [_cell_xy(ci) for ci, (g, _) in enumerate(GRID_LAYOUT)
                  if g == "R1_notR2"]
    notR3_pos  = [_cell_xy(ci) for ci, (g, _) in enumerate(GRID_LAYOUT)
                  if g == "R1_notR3"]
    notR4_pos  = [_cell_xy(ci) for ci, (g, _) in enumerate(GRID_LAYOUT)
                  if g == "R1_notR4"]

    ov_red    = _make_box_overlay(all_pos,   BOX_OUTER_COLOR,              inset=0,  border_w=5)
    ov_pink   = _make_box_overlay(notR2_pos, BOX_INNER_COLORS["R1_notR2"], inset=10, border_w=3)
    ov_blue   = _make_box_overlay(notR3_pos, BOX_INNER_COLORS["R1_notR3"], inset=10, border_w=3)
    ov_yellow = _make_box_overlay(notR4_pos, BOX_INNER_COLORS["R1_notR4"], inset=10, border_w=3)

    # ── Pre-build text overlays ────────────────────────────────────────────────
    # Two title overlays: baseline (phases 1–2) crossfades into exceptions (phase 3+)
    ov_title_baseline = make_text_overlay([
        {"text":      "Relaxed Cluster Criteria  —  Baseline",
         "x": W // 2, "y": HEADER_H // 2 + 4, "size": 18,
         "color_rgb": (190, 210, 240), "bold": True, "stroke_w": 1},
    ])
    ov_title_exceptions = make_text_overlay([
        {"text":      "Relaxed Cluster Criteria  —  exceptions revealed by MACosmo",
         "x": W // 2, "y": HEADER_H // 2 + 4, "size": 18,
         "color_rgb": (160, 210, 255), "bold": True, "stroke_w": 1},
    ])

    # Legend lines appear in the footer area, stacking as phases progress
    leg_ys = [H - 82, H - 60, H - 38, H - 16]   # image-coords from top
    ov_leg_r1 = make_text_overlay([
        {"text":      "■  R₁  —  δ₁ relaxed : Center-of-Mass Offset below threshold",
         "x": W // 2, "y": leg_ys[0], "size": 13,
         "color_rgb": BOX_OUTER_COLOR, "bold": False, "stroke_w": 1},
    ])
    ov_leg_notR2 = make_text_overlay([
        {"text":      "■  R₁∖R₂  —  Gas centroid offset (δ₂) too large  →  unrelaxed by gas criterion",
         "x": W // 2, "y": leg_ys[1], "size": 13,
         "color_rgb": BOX_INNER_COLORS["R1_notR2"], "bold": False, "stroke_w": 1},
    ])
    ov_leg_notR3 = make_text_overlay([
        {"text":      "■  R₁∖R₃  —  Core entropy (K_core) too high  →  lacks a cool core",
         "x": W // 2, "y": leg_ys[2], "size": 13,
         "color_rgb": BOX_INNER_COLORS["R1_notR3"], "bold": False, "stroke_w": 1},
    ])
    ov_leg_notR4 = make_text_overlay([
        {"text":      "■  R₁∖R₄  —  TPI below cool-core threshold  →  no thermodynamic peak",
         "x": W // 2, "y": leg_ys[3], "size": 13,
         "color_rgb": BOX_INNER_COLORS["R1_notR4"], "bold": False, "stroke_w": 1},
    ])

    # ── Phase timing (seconds) ────────────────────────────────────────────────
    # Each phase_t[k] is when phase k+1 begins.
    phase_t = [
        0.0,    # Phase 1: DM tiles fade in
        1.5,    # Phase 2: red boxes
        4.0,    # Phase 3: pink boxes + R1_notR2 crossfade
        6.5,    # Phase 4: blue boxes + R1_notR3 crossfade
        9.0,    # Phase 5: yellow boxes + R1_notR4 crossfade
        11.5,   # Phase 6: hold
    ]
    t_fade_out = total_sec - fade_out_sec
    xfade_dur  = 1.5   # field crossfade duration within each active phase

    n_frames = int(total_sec * FPS)

    def _phase_alpha(t, phase_idx, rise_dur=0.8):
        """Smooth rise for the phase that starts at phase_t[phase_idx]."""
        return smoothstep(min(max(t - phase_t[phase_idx], 0) / rise_dur, 1))

    def _xfade_alpha(t, phase_idx):
        """Field crossfade alpha — starts when the phase starts, lasts xfade_dur."""
        return smoothstep(min(max(t - phase_t[phase_idx], 0) / xfade_dur, 1))

    for i in range(n_frames):
        t = i / FPS

        # Global fade envelope (in at start, out at end)
        g_alpha = smoothstep(min(t / max(fade_in_sec, 0.001), 1))
        if t >= t_fade_out:
            g_alpha *= smoothstep(1 - (t - t_fade_out) / max(fade_out_sec, 0.001))

        # Per-phase box alphas (accumulate: each stays visible once it appears)
        a_red    = _phase_alpha(t, 1)
        a_pink   = _phase_alpha(t, 2)
        a_blue   = _phase_alpha(t, 3)
        a_yellow = _phase_alpha(t, 4)

        # Field crossfade fractions for each notR group
        xf_notR2 = _xfade_alpha(t, 2) if t >= phase_t[2] else 0.0
        xf_notR3 = _xfade_alpha(t, 3) if t >= phase_t[3] else 0.0
        xf_notR4 = _xfade_alpha(t, 4) if t >= phase_t[4] else 0.0
        xf_map   = {
            "R1_notR2": xf_notR2,
            "R1_notR3": xf_notR3,
            "R1_notR4": xf_notR4,
        }

        # ── Build base canvas with cell tiles ──────────────────────────────────
        canvas = Image.new("RGB", (W, H), (0, 0, 0))

        for ci, (group, h_idx) in enumerate(GRID_LAYOUT):
            x_off, y_off = _cell_xy(ci)
            dm_tile = dm_tiles.get((group, h_idx),
                                    Image.new("RGB", (CELL_W, CELL_H), (8, 10, 18)))

            xf = xf_map.get(group, 0.0)
            if xf > 0 and (group, h_idx) in alt_tiles:
                tile = blend(dm_tile, alt_tiles[(group, h_idx)], xf)
            else:
                tile = dm_tile

            if g_alpha < 1.0:
                tile = Image.fromarray(
                    (np.array(tile, dtype=np.float32) * g_alpha
                     ).clip(0, 255).astype(np.uint8))

            canvas.paste(tile, (x_off, y_off))

        # Draw gap separators between cells (thin dark lines)
        draw = ImageDraw.Draw(canvas)
        for col in range(1, N_COLS):
            sx = MARGIN + col * (CELL_W + GAP) - GAP
            draw.rectangle([sx, HEADER_H, sx + GAP - 1, H - FOOTER_H],
                            fill=(20, 20, 20))
        for row in range(1, N_ROWS):
            sy = HEADER_H + row * (CELL_H + GAP) - GAP
            draw.rectangle([MARGIN, sy, W - MARGIN, sy + GAP - 1],
                            fill=(20, 20, 20))

        # ── Composite box overlays ─────────────────────────────────────────────
        canvas = composite_rgba(canvas, ov_red,    alpha_mult=a_red    * g_alpha)
        canvas = composite_rgba(canvas, ov_pink,   alpha_mult=a_pink   * g_alpha)
        canvas = composite_rgba(canvas, ov_blue,   alpha_mult=a_blue   * g_alpha)
        canvas = composite_rgba(canvas, ov_yellow, alpha_mult=a_yellow * g_alpha)

        # ── Composite text overlays ────────────────────────────────────────────
        # Title crossfades from "Baseline" → "exceptions revealed by MACosmo"
        # when the first agent criterion (pink/R1_notR2) appears at phase 3.
        canvas = composite_rgba(canvas, ov_title_baseline,
                                alpha_mult=(1.0 - a_pink) * g_alpha * 0.90)
        canvas = composite_rgba(canvas, ov_title_exceptions,
                                alpha_mult=a_pink * g_alpha * 0.90)
        canvas = composite_rgba(canvas, ov_leg_r1,    alpha_mult=a_red    * g_alpha * 0.95)
        canvas = composite_rgba(canvas, ov_leg_notR2, alpha_mult=a_pink   * g_alpha * 0.95)
        canvas = composite_rgba(canvas, ov_leg_notR3, alpha_mult=a_blue   * g_alpha * 0.95)
        canvas = composite_rgba(canvas, ov_leg_notR4, alpha_mult=a_yellow * g_alpha * 0.95)

        yield canvas


# ── Standalone preview ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    out_dir  = os.path.dirname(os.path.abspath(__file__))
    renders  = os.path.join(out_dir, "renders")

    print("Pre-rendering selection tiles …")
    prepare_selection_renders(renders_dir=renders)

    # Save a single preview frame at t=10 s (all boxes visible)
    target_sec = 10.0
    preview    = None
    for idx, frame in enumerate(scene_selection_reveal(renders_dir=renders)):
        if idx / FPS >= target_sec:
            preview = frame
            break

    if preview:
        out_path = os.path.join(out_dir, "preview_selection.png")
        preview.save(out_path)
        print(f"Preview saved → {out_path}")
    else:
        print("No frame generated.")
