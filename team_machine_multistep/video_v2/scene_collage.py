"""
scene_collage.py — Per-group multifield collage: 7 halos × 4 fields.

For each requested group (R1, R1_notR2, R1_notR3, R1_notR4) renders a
7-column × 4-row grid where:
  Columns  = top 7 most-massive halos in that group
  Rows     = Dark Matter | Stars | Gas | Gas Temperature

Groups are shown in sequence with smooth crossfades so the viewer can
compare morphology across selection criteria.

Functions
---------
prepare_group_multifield_renders(group, renders_dir, n_halos)
    Pre-render all tiles for one group (cached).

build_group_multifield_image(group, renders_dir, n_halos)
    Assemble the 7×4 collage for one group as a PIL RGB Image.

scene_group_multifield_tour(group_names, renders_dir, hold_sec, xfade_sec)
    Generator yielding animated frames that tour through the groups.

Usage:
    from scene_collage import prepare_group_multifield_renders, scene_group_multifield_tour

    GROUPS = ["R1", "R1_notR2", "R1_notR3", "R1_notR4"]
    for g in GROUPS:
        prepare_group_multifield_renders(g, RENDERS_DIR)
    for frame in scene_group_multifield_tour(GROUPS, RENDERS_DIR, hold_sec=4, xfade_sec=1.2):
        ...
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from video_utils import (
    W, H, FPS,
    PARTICLE_DIR, RENDERS_DIR,
    FIELD_CMAPS, FIELD_LABELS, FIELD_ACCENT_RGB,
    FILE_MAP, GROUP_COLORS_RGB, GROUP_SHORT_LABELS,
    smoothstep, blend, composite_rgba, zoom_image,
    make_text_overlay, render_field_image, get_top_halos,
)
from PIL import Image, ImageDraw
import numpy as np


# ── Grid geometry ──────────────────────────────────────────────────────────────
N_HALOS   = 7      # columns
N_FIELDS  = 4      # rows  (DM, Stars, Gas, Gas Temp)
LABEL_W   = 148    # left margin for row (field) labels
HEADER_H  = 46     # top margin for group title

CELL_W = (W - LABEL_W - (N_HALOS - 1)) // N_HALOS          # ≈ 252 px
CELL_H = (H - HEADER_H - (N_FIELDS - 1)) // N_FIELDS        # ≈ 258 px


def _tile_path(renders_dir, group, halo_idx, field_idx):
    return os.path.join(renders_dir, f"mf_{group}_h{halo_idx}_f{field_idx}.png")


# ── Render helpers ─────────────────────────────────────────────────────────────

def prepare_group_multifield_renders(group, renders_dir=RENDERS_DIR,
                                      n_halos=N_HALOS):
    """
    Pre-render n_halos × 4 field images for *group*.
    Tiles are cached by filename; only missing tiles are rendered.
    """
    os.makedirs(renders_dir, exist_ok=True)
    hdf5 = os.path.join(PARTICLE_DIR, FILE_MAP[group])
    if not os.path.exists(hdf5):
        print(f"  WARNING: {hdf5} not found — skipping {group}")
        return

    top_halos = get_top_halos(hdf5, n=n_halos)
    total     = len(top_halos) * N_FIELDS
    done      = 0

    print(f"Preparing {total} tiles for {group} …")
    for h_idx, (mass, tag) in enumerate(top_halos):
        for fi in range(N_FIELDS):
            out = _tile_path(renders_dir, group, h_idx, fi)
            render_field_image(hdf5, tag, fi, out, width=4.5, cache=True)
            done += 1
            print(f"  [{done}/{total}]  {group} halo {h_idx}  field {fi}  tag={tag}  M={mass:.2e}")

    print(f"  ✓ {group} done")


# ── Collage assembly ───────────────────────────────────────────────────────────

def build_group_multifield_image(group, renders_dir=RENDERS_DIR,
                                  n_halos=N_HALOS):
    """
    Assemble a 1920 × 1080 multifield collage for one group.

    Layout:
      Left margin  (148 px)  : field-name labels in canonical colors
      Top margin   ( 46 px)  : group name + selection criterion
      Grid         : n_halos cols × 4 rows, 1-px white separators

    Returns PIL RGB Image.
    """
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    draw   = ImageDraw.Draw(canvas)

    # ── Paste tiles ────────────────────────────────────────────────────────────
    for fi in range(N_FIELDS):
        y_off = HEADER_H + fi * (CELL_H + 1)
        for h_idx in range(n_halos):
            x_off = LABEL_W + h_idx * (CELL_W + 1)
            path  = _tile_path(renders_dir, group, h_idx, fi)
            if os.path.exists(path):
                tile = Image.open(path).convert("RGB")
                tile = tile.resize((CELL_W, CELL_H), Image.LANCZOS)
                canvas.paste(tile, (x_off, y_off))
            else:
                draw.rectangle([x_off, y_off,
                                 x_off + CELL_W - 1, y_off + CELL_H - 1],
                                fill=(12, 12, 18))

    # ── 1-px white separator lines ─────────────────────────────────────────────
    for h_idx in range(1, n_halos):
        sx = LABEL_W + h_idx * (CELL_W + 1) - 1
        draw.line([sx, HEADER_H, sx, H - 1], fill=(255, 255, 255), width=1)
    for fi in range(1, N_FIELDS):
        sy = HEADER_H + fi * (CELL_H + 1) - 1
        draw.line([LABEL_W, sy, W - 1, sy], fill=(255, 255, 255), width=1)
    # Left margin separator
    draw.line([LABEL_W - 1, HEADER_H, LABEL_W - 1, H - 1],
              fill=(120, 120, 120), width=1)

    # ── Field labels (row headers, left margin) ────────────────────────────────
    field_label_lines = []
    for fi, (label, cmap) in enumerate(zip(FIELD_LABELS, FIELD_CMAPS)):
        y_center = HEADER_H + fi * (CELL_H + 1) + CELL_H // 2
        r, g, b  = FIELD_ACCENT_RGB[cmap]
        # Short labels to fit in 148 px
        short = {"Dark Matter": "Dark\nMatter", "Gas Temperature": "Gas\nTemp"}.get(label, label)
        for line_idx, line_text in enumerate(short.split("\n")):
            offset = -10 if "\n" in short else 0
            field_label_lines.append({
                "text":      line_text,
                "x":         LABEL_W // 2,
                "y":         y_center + offset + line_idx * 22,
                "size":      14,
                "color_rgb": (r, g, b),
                "bold":      True,
                "stroke_w":  1,
            })

    label_ov = make_text_overlay(field_label_lines)
    canvas = composite_rgba(canvas, label_ov, alpha_mult=1.0)

    # ── Group title (top header) ───────────────────────────────────────────────
    gc   = GROUP_COLORS_RGB.get(group, (200, 200, 200))
    glbl = GROUP_SHORT_LABELS.get(group, group)
    title_ov = make_text_overlay([
        {"text":  f"{glbl}  —  top {n_halos} halos by mass  ·  Dark Matter | Stars | Gas | Gas Temperature",
         "x": LABEL_W + (W - LABEL_W) // 2, "y": HEADER_H // 2 + 2,
         "size": 15, "color_rgb": gc, "bold": True, "stroke_w": 1},
    ])
    canvas = composite_rgba(canvas, title_ov, alpha_mult=1.0)

    return canvas


# ── Scene generator ────────────────────────────────────────────────────────────

def scene_group_multifield_tour(group_names,
                                 renders_dir=RENDERS_DIR,
                                 n_halos=N_HALOS,
                                 hold_sec=4.0,
                                 xfade_sec=1.2,
                                 fade_in_sec=0.6,
                                 fade_out_sec=0.6):
    """
    Yield 1920 × 1080 frames touring through groups in sequence.

    Each group is shown as a 7×4 multifield collage with slow zoom.
    Groups crossfade into one another.

    Parameters
    ----------
    group_names  : Ordered list of group keys, e.g. ["R1","R1_notR2",...]
    hold_sec     : Seconds to hold each group's collage
    xfade_sec    : Crossfade duration between groups
    fade_in_sec  : Fade in from black at scene start
    fade_out_sec : Fade to black at scene end
    """
    frames_hold  = int(hold_sec  * FPS)
    frames_xfade = int(xfade_sec * FPS)
    frames_fin   = int(fade_in_sec  * FPS)
    frames_fout  = int(fade_out_sec * FPS)

    # Build all collage images up front
    print("Building multifield collage images …")
    collages = {}
    for g in group_names:
        print(f"  {g} …")
        collages[g] = build_group_multifield_image(g, renders_dir, n_halos)

    black = Image.new("RGB", (W, H), (0, 0, 0))

    # Subtitle overlay (field-column labels at bottom)
    sub_ov = make_text_overlay([
        {"text": "Columns: top 7 halos by mass   ·   Rows: Dark Matter | Stars | Gas | Gas Temperature",
         "x": W // 2, "y": int(H * 0.973), "size": 14,
         "color_rgb": (140, 155, 175), "bold": False, "stroke_w": 1},
    ])

    # Fade in from black
    first = collages[group_names[0]]
    for j in range(frames_fin):
        t = smoothstep(j / max(frames_fin, 1))
        frame = blend(black, first, t)
        yield frame

    for gi, g in enumerate(group_names):
        base_img  = collages[g]
        base_arr  = np.array(base_img, dtype=np.float32)

        # Hold with very subtle slow zoom
        for j in range(frames_hold):
            t   = j / max(frames_hold, 1)
            zm  = 1.0 + 0.025 * smoothstep(t)
            a_s = smoothstep(min(t / 0.25, 1))
            frame = zoom_image(base_img, zm) if zm > 1.001 else base_img
            frame = composite_rgba(frame, sub_ov, alpha_mult=a_s * 0.85)
            yield frame

        # Crossfade to next group (or fade to black if last)
        if gi < len(group_names) - 1:
            next_img = collages[group_names[gi + 1]]
            for j in range(frames_xfade):
                t = smoothstep(j / max(frames_xfade, 1))
                frame = blend(base_img, next_img, t)
                yield frame
        else:
            # Last group: fade to black
            for j in range(frames_fout):
                t = smoothstep(j / max(frames_fout, 1))
                yield blend(base_img, black, t)


# ── Standalone preview ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    renders = os.path.join(out_dir, "renders")
    groups  = ["R1", "R1_notR2", "R1_notR3", "R1_notR4"]

    for g in groups:
        prepare_group_multifield_renders(g, renders_dir=renders, n_halos=N_HALOS)

    # Preview first group
    img = build_group_multifield_image(groups[0], renders_dir=renders)
    out = os.path.join(out_dir, f"preview_collage_{groups[0]}.png")
    img.save(out)
    print(f"Preview saved → {out}")
