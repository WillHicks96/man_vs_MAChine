"""
scene_v3_intro.py — Faster animated intro card (~5 s) for the cluster zoo v3 video.

Identical content to v2's scene_intro but compressed to fit in 5 seconds.

Scene structure:
  0.0 – 0.3 s   Title fades in
  0.3 – 0.6 s   Subtitle + info line appear
  0.6 – 1.0 s   "Relaxation Criteria" header
  1.0 – 2.8 s   4 criteria fade in at 0.45 s intervals
  2.8 – 4.5 s   Hold (all text fully visible)
  4.5 – 5.0 s   Fade to black

Usage:
    from scene_v3_intro import scene_v3_intro
    for frame in scene_v3_intro(duration=5.0, fade_out=True):
        ...
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "video_v2"))

from video_utils import (
    W, H, FPS,
    GROUP_COLORS_RGB,
    smoothstep, composite_rgba,
    make_text_overlay, make_separator_bar,
)
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe


# ── Text content (identical to v2) ─────────────────────────────────────────────

_CRITERIA_TEXT = [
    {
        "symbol":  "δ₁  —  Center of Mass Offset",
        "line1":   "Distance between the overall center of mass and the density peak of the dark matter halo,",
        "line2":   "normalized by the virial radius R₂₀₀ₘ.  Small δ₁ → dynamically relaxed, symmetric cluster.",
        "color":   GROUP_COLORS_RGB["R1"],
    },
    {
        "symbol":  "δ₂  —  Dark Matter–Gas Centroid Separation",
        "line1":   "Offset between the dark matter and hot gas centers of mass, normalized by R₅₀₀c.",
        "line2":   "Elevated δ₂ signals gas sloshing or centroid displacement caused by a recent merger.",
        "color":   GROUP_COLORS_RGB["R1_andR2"],
    },
    {
        "symbol":  "K_core  —  Core Entropy  [keV·cm²]",
        "line1":   "Thermal entropy of the hot gas in the innermost region of the cluster.",
        "line2":   "Low K_core identifies dense cool-core clusters where the gas is radiatively cooling.",
        "color":   GROUP_COLORS_RGB["R1_andR3"],
    },
    {
        "symbol":  "TPI  —  Thermodynamic Peakiness Index",
        "line1":   "Combined z-score of the core electron density and the excised-to-global temperature ratio.",
        "line2":   "Negative TPI marks clusters with a pronounced thermodynamic cool-core peak.",
        "color":   GROUP_COLORS_RGB["R1_andR4"],
    },
]


def _make_square_bracket(x_left, y_top_img, y_bot_img, label,
                          color_rgb=(200, 210, 240),
                          bracket_w=48, lw=2.5, label_size=17,
                          fw=W, fh=H):
    """Right-facing square bracket with label (same as v2)."""
    fig, ax = plt.subplots(figsize=(fw / 100, fh / 100))
    fig.patch.set_facecolor((0, 0, 0, 0))
    fig.patch.set_alpha(0.0)
    ax.set_position([0, 0, 1, 1])
    ax.set_xlim(0, fw)
    ax.set_ylim(0, fh)
    ax.axis("off")
    ax.set_facecolor((0, 0, 0, 0))

    my_top = fh - y_top_img
    my_bot = fh - y_bot_img
    my_mid = (my_top + my_bot) / 2
    x_bar  = x_left + bracket_w
    r, g, b = color_rgb
    col = (r / 255, g / 255, b / 255, 1.0)

    kw = dict(color=col, linewidth=lw, solid_capstyle="butt", solid_joinstyle="miter")
    ax.plot([x_left, x_bar], [my_top, my_top], **kw)
    ax.plot([x_bar,  x_bar], [my_top, my_bot], **kw)
    ax.plot([x_left, x_bar], [my_bot, my_bot], **kw)

    ax.text(x_bar + 18, my_mid, label,
            ha="left", va="center",
            fontsize=label_size, fontweight="bold",
            color=col,
            path_effects=[pe.withStroke(linewidth=1.5, foreground="black")])

    fig.canvas.draw()
    buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
    rw, rh = fig.canvas.get_width_height()
    arr = buf.reshape(rh, rw, 4).copy()
    plt.close(fig)
    return Image.fromarray(arr, "RGBA")


def _build_overlays():
    """Pre-render all RGBA text layers."""
    overlays = {}

    overlays["title"] = make_text_overlay([
        {"text":  "MACosmo with HACC",
         "x": W // 2, "y": 105, "size": 70,
         "color_rgb": (255, 255, 255), "bold": True, "stroke_w": 3},
        {"text":  "Relaxation in Massive Clusters",
         "x": W // 2, "y": 172, "size": 44,
         "color_rgb": (170, 205, 255), "bold": True, "stroke_w": 2},
    ])

    overlays["info"] = make_text_overlay([
        {"text":  "Frontier-E Hydrodynamical Simulation  ·  OpenCosmo-MCP on ALCF  ·  MACosmo",
         "x": W // 2, "y": 228, "size": 18,
         "color_rgb": (120, 160, 210), "bold": False, "stroke_w": 1},
    ])

    overlays["header"] = make_text_overlay([
        {"text":  "Relaxation Criteria",
         "x": W // 2, "y": 295, "size": 22,
         "color_rgb": (190, 210, 240), "bold": False, "stroke_w": 1},
    ])
    overlays["header_bar_l"] = make_separator_bar((140, 170, 210), 0.10, 0.38, 295 / H, thickness=2)
    overlays["header_bar_r"] = make_separator_bar((140, 170, 210), 0.62, 0.90, 295 / H, thickness=2)

    y_positions = [375, 505, 635, 765]
    for i, crit in enumerate(_CRITERIA_TEXT):
        y0 = y_positions[i]
        r, g, b = crit["color"]
        overlays[f"crit_{i}"] = make_text_overlay([
            {"text": crit["symbol"],
             "x": 190, "y": y0, "size": 26,
             "color_rgb": (r, g, b), "bold": True, "stroke_w": 2,
             "ha": "left", "va": "center"},
            {"text": crit["line1"],
             "x": 200, "y": y0 + 42, "size": 15,
             "color_rgb": (200, 205, 215), "bold": False, "stroke_w": 1,
             "ha": "left", "va": "center"},
            {"text": crit["line2"],
             "x": 200, "y": y0 + 68, "size": 15,
             "color_rgb": (170, 175, 190), "bold": False, "stroke_w": 1,
             "ha": "left", "va": "center"},
        ])
        overlays[f"crit_bar_{i}"] = make_separator_bar(
            (r, g, b), 0.08, 0.09, y0 / H, thickness=18)

    BX, BW = 1450, 48
    overlays["brace_baseline"] = _make_square_bracket(
        x_left=BX, y_top_img=358, y_bot_img=465,
        label="Baseline\ncriterion", color_rgb=(215, 215, 235),
        bracket_w=BW, lw=2.5, label_size=17)
    overlays["brace_agent"] = _make_square_bracket(
        x_left=BX, y_top_img=488, y_bot_img=853,
        label="Agent generated\ncriteria", color_rgb=(160, 210, 255),
        bracket_w=BW, lw=2.5, label_size=17)

    return overlays


def scene_v3_intro(duration=5.0, fade_out=True):
    """
    Yield 1920×1080 PIL RGB frames for the faster intro card (~5 s).

    Compressed timing relative to v2's 8 s version.
    """
    n_frames = int(duration * FPS)
    overlays  = _build_overlays()

    # Compressed timing to fit in 5 s
    t_title    = 0.0
    t_info     = 0.25
    t_header   = 0.55
    t_crit     = [0.9, 1.4, 1.9, 2.4]   # 0.5 s apart → all visible by ~2.9 s
    t_hold_end = duration - (0.5 if fade_out else 0.0)  # 4.5 s
    fade_dur   = 0.45   # each element fades in over 0.45 s

    for i in range(n_frames):
        t = i / FPS

        if fade_out and t >= t_hold_end:
            fade_global = smoothstep(1 - (t - t_hold_end) / 0.6)
        else:
            fade_global = 1.0

        canvas = Image.new("RGB", (W, H), (0, 0, 0))

        def _alpha(start_t):
            return smoothstep(min(max(t - start_t, 0) / fade_dur, 1)) * fade_global

        canvas = composite_rgba(canvas, overlays["title"],        _alpha(t_title))
        canvas = composite_rgba(canvas, overlays["info"],         _alpha(t_info))
        canvas = composite_rgba(canvas, overlays["header"],       _alpha(t_header))
        canvas = composite_rgba(canvas, overlays["header_bar_l"], _alpha(t_header) * 0.7)
        canvas = composite_rgba(canvas, overlays["header_bar_r"], _alpha(t_header) * 0.7)

        for ci, tc in enumerate(t_crit):
            a = _alpha(tc)
            canvas = composite_rgba(canvas, overlays[f"crit_{ci}"],     a)
            canvas = composite_rgba(canvas, overlays[f"crit_bar_{ci}"], a * 0.85)

        canvas = composite_rgba(canvas, overlays["brace_baseline"],
                                _alpha(t_crit[0]) * 0.92)
        canvas = composite_rgba(canvas, overlays["brace_agent"],
                                _alpha(t_crit[3]) * 0.92)

        yield canvas
