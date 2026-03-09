"""
scene_intro.py — Animated intro/title card for the cluster morphology video.

Explains the four relaxation criteria with full descriptive text.
Designed to be imported into an assembler script, or run standalone
to preview a single frame (saved to video_v2/preview_intro.png).

Scene structure (~15 seconds):
  0.0 – 1.2 s   Title  "HACC Simulation" + subtitle
  1.2 – 2.4 s   Simulation info line
  2.4 – 3.6 s   "Relaxation Criteria" header
  3.6 – 5.6 s   δ₁  criterion
  5.6 – 7.6 s   δ₂  criterion
  7.6 – 9.6 s   K_core criterion
  9.6 – 11.6 s  TPI  criterion
 11.6 – 14.0 s  Hold
 14.0 – 15.0 s  Fade to black (optional)

Usage:
    from scene_intro import scene_intro
    for frame in scene_intro(duration=15, fade_out=True):
        # frame is a 1920×1080 PIL RGB Image
        ...
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from video_utils import (
    W, H, FPS,
    GROUP_COLORS_RGB,
    smoothstep, composite_rgba,
    make_text_overlay, make_separator_bar,
)
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.path as mpath
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe


# ── Text content ───────────────────────────────────────────────────────────────

_CRITERIA_TEXT = [
    {
        "symbol":  "δ₁  —  Center of Mass Offset",
        "line1":   "Distance between the overall center of mass and the density peak of the dark matter halo,",
        "line2":   "normalized by the virial radius R₂₀₀ₘ.  Small δ₁ → dynamically relaxed, symmetric cluster.",
        "color":   GROUP_COLORS_RGB["R1"],        # gray-white
    },
    {
        "symbol":  "δ₂  —  Dark Matter–Gas Centroid Separation",
        "line1":   "Offset between the dark matter and hot gas centers of mass, normalized by R₅₀₀c.",
        "line2":   "Elevated δ₂ signals gas sloshing or centroid displacement caused by a recent merger.",
        "color":   GROUP_COLORS_RGB["R1_andR2"],  # blue
    },
    {
        "symbol":  "K_core  —  Core Entropy  [keV·cm²]",
        "line1":   "Thermal entropy of the hot gas in the innermost region of the cluster.",
        "line2":   "Low K_core identifies dense cool-core clusters where the gas is radiatively cooling.",
        "color":   GROUP_COLORS_RGB["R1_andR3"],  # green
    },
    {
        "symbol":  "TPI  —  Thermodynamic Peakiness Index",
        "line1":   "Combined z-score of the core electron density and the excised-to-global temperature ratio.",
        "line2":   "Negative TPI marks clusters with a pronounced thermodynamic cool-core peak.",
        "color":   GROUP_COLORS_RGB["R1_andR4"],  # purple
    },
]


def _make_square_bracket(x_left, y_top_img, y_bot_img, label,
                          color_rgb=(200, 210, 240),
                          bracket_w=48, lw=2.5, label_size=17,
                          fw=W, fh=H):
    """
    Render a right-facing square bracket  ]  as a PIL RGBA Image (fw × fh).

    Three straight lines (top cap, vertical bar, bottom cap) with a label
    placed just to the right of the bar.

    Parameters
    ----------
    x_left      : x position of the open (left) edge of the caps in pixels
    y_top_img   : y of the top anchor in image coordinates (y=0 at top)
    y_bot_img   : y of the bottom anchor in image coordinates
    label       : Text string placed beside the bar
    color_rgb   : (r, g, b) colour of bracket + label
    bracket_w   : Width of the bracket (caps extend bracket_w px to the right)
    lw          : Line width
    label_size  : Font size of the label
    fw, fh      : Frame width/height (matches the overall video canvas)
    """
    fig, ax = plt.subplots(figsize=(fw / 100, fh / 100))
    fig.patch.set_facecolor((0, 0, 0, 0))
    fig.patch.set_alpha(0.0)
    ax.set_position([0, 0, 1, 1])
    ax.set_xlim(0, fw)
    ax.set_ylim(0, fh)
    ax.axis("off")
    ax.set_facecolor((0, 0, 0, 0))

    # Convert image coords (y=0 top) → matplotlib coords (y=0 bottom)
    my_top = fh - y_top_img
    my_bot = fh - y_bot_img   # my_bot < my_top (image y is inverted)
    my_mid = (my_top + my_bot) / 2
    x_bar  = x_left + bracket_w   # x position of the vertical bar
    r, g, b = color_rgb
    col = (r / 255, g / 255, b / 255, 1.0)

    kw = dict(color=col, linewidth=lw, solid_capstyle="butt",
              solid_joinstyle="miter")
    ax.plot([x_left, x_bar], [my_top, my_top], **kw)   # top cap
    ax.plot([x_bar,  x_bar], [my_top, my_bot], **kw)   # vertical bar
    ax.plot([x_left, x_bar], [my_bot, my_bot], **kw)   # bottom cap

    # Label centred vertically at the bar
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
    """
    Pre-render all text layers as RGBA images.
    Returns a dict mapping layer name → PIL RGBA Image.
    """
    overlays = {}

    # ── Title + subtitle ──────────────────────────────────────────────────────
    overlays["title"] = make_text_overlay([
        {"text":  "MACosmo with HACC",
         "x": W // 2, "y": 105, "size": 70,
         "color_rgb": (255, 255, 255), "bold": True,  "stroke_w": 3},
        {"text":  "Relaxation in Massive Clusters",
         "x": W // 2, "y": 172, "size": 44,
         "color_rgb": (170, 205, 255), "bold": True,  "stroke_w": 2},
    ])

    # ── Simulation info ───────────────────────────────────────────────────────
    overlays["info"] = make_text_overlay([
        {"text":  "Frontier-E Hydrodynamical Simulation  ·  OpenCosmo-MCP on ALCF  ·  MACosmo ",
         "x": W // 2, "y": 228, "size": 18,
         "color_rgb": (120, 160, 210), "bold": False, "stroke_w": 1},
    ])

    # ── "Relaxation Criteria" section header + separator bars ─────────────────
    overlays["header"] = make_text_overlay([
        {"text":  "Relaxation Criteria",
         "x": W // 2, "y": 295, "size": 22,
         "color_rgb": (190, 210, 240), "bold": False, "stroke_w": 1},
    ])
    overlays["header_bar_l"] = make_separator_bar(
        (140, 170, 210), 0.10, 0.38, 295 / H, thickness=2)
    overlays["header_bar_r"] = make_separator_bar(
        (140, 170, 210), 0.62, 0.90, 295 / H, thickness=2)

    # ── Individual criterion overlays ─────────────────────────────────────────
    # y positions for 4 criteria, evenly spaced in the lower ~60% of the screen
    y_positions = [375, 505, 635, 765]

    for i, crit in enumerate(_CRITERIA_TEXT):
        y0 = y_positions[i]
        r, g, b = crit["color"]
        overlays[f"crit_{i}"] = make_text_overlay([
            # Criterion label (symbol + full name)
            {"text":  crit["symbol"],
             "x": 190, "y": y0, "size": 26,
             "color_rgb": (r, g, b),
             "bold": True, "stroke_w": 2,
             "ha": "left", "va": "center"},
            # First description line
            {"text":  crit["line1"],
             "x": 200, "y": y0 + 42, "size": 15,
             "color_rgb": (200, 205, 215),
             "bold": False, "stroke_w": 1,
             "ha": "left", "va": "center"},
            # Second description line
            {"text":  crit["line2"],
             "x": 200, "y": y0 + 68, "size": 15,
             "color_rgb": (170, 175, 190),
             "bold": False, "stroke_w": 1,
             "ha": "left", "va": "center"},
        ])
        # Tiny colour accent bar to the left of the criterion label
        overlays[f"crit_bar_{i}"] = make_separator_bar(
            (r, g, b), 0.08, 0.09, y0 / H, thickness=18)

    # ── Square brackets on the right side ─────────────────────────────────────
    # y_positions = [375, 505, 635, 765]; each block ends at y0 + 68.
    # Bracket 1 spans only δ₁ (y 358–465).
    # Bracket 2 spans δ₂ + K_core + TPI (y 488–853).
    BX = 1450   # x of the bracket's left (open) edge
    BW = 48     # bracket width; bar sits at BX + BW = 1498

    overlays["brace_baseline"] = _make_square_bracket(
        x_left=BX, y_top_img=358, y_bot_img=465,
        label="Baseline\ncriteria",
        color_rgb=(215, 215, 235),
        bracket_w=BW, lw=2.5, label_size=17,
    )
    overlays["brace_agent"] = _make_square_bracket(
        x_left=BX, y_top_img=488, y_bot_img=853,
        label="Agent generated\ncriteria",
        color_rgb=(160, 210, 255),
        bracket_w=BW, lw=2.5, label_size=17,
    )

    return overlays


def scene_intro(duration=8.0, fade_out=True):
    """
    Yield 1920×1080 PIL RGB frames for the animated intro card.

    The four relaxation criteria (δ₁, δ₂, K_core, TPI) fade in
    sequentially with explanatory text in plain language.

    Parameters
    ----------
    duration   : Total scene length in seconds (default 8)
    fade_out   : If True, fade to black in the last ~0.5 s
    """
    n_frames   = int(duration * FPS)
    overlays   = _build_overlays()
    black      = Image.new("RGB", (W, H), (0, 0, 0))

    # Timing breakpoints (in seconds) — compressed to fit 8 s
    t_title    = 0.0   # title starts
    t_info     = 0.5   # info line starts
    t_header   = 1.0   # criteria header
    t_crit     = [1.5, 2.5, 3.5, 4.5]   # each criterion starts
    t_hold_end = duration - (0.5 if fade_out else 0.0)
    fade_dur   = 0.7   # each element takes this long to fully appear

    for i in range(n_frames):
        t = i / FPS   # current time in seconds

        # Fade to black at end
        if fade_out and t >= t_hold_end:
            fade_global = smoothstep(1 - (t - t_hold_end) / 0.8)
        else:
            fade_global = 1.0

        canvas = Image.new("RGB", (W, H), (0, 0, 0))

        def _alpha(start_t):
            """Smoothstep alpha for an element that begins fading in at start_t."""
            return smoothstep(min(max(t - start_t, 0) / fade_dur, 1)) * fade_global

        # Composite all layers
        canvas = composite_rgba(canvas, overlays["title"],      _alpha(t_title))
        canvas = composite_rgba(canvas, overlays["info"],       _alpha(t_info))
        canvas = composite_rgba(canvas, overlays["header"],     _alpha(t_header))
        canvas = composite_rgba(canvas, overlays["header_bar_l"], _alpha(t_header) * 0.7)
        canvas = composite_rgba(canvas, overlays["header_bar_r"], _alpha(t_header) * 0.7)

        for ci, tc in enumerate(t_crit):
            a = _alpha(tc)
            canvas = composite_rgba(canvas, overlays[f"crit_{ci}"],     a)
            canvas = composite_rgba(canvas, overlays[f"crit_bar_{ci}"], a * 0.85)

        # Curly brackets fade in with their respective criterion groups:
        #   Baseline bracket  — appears with δ₁  (t_crit[0])
        #   Agent bracket     — appears with TPI  (t_crit[3], when all 3 are visible)
        canvas = composite_rgba(canvas, overlays["brace_baseline"],
                                _alpha(t_crit[0]) * 0.92)
        canvas = composite_rgba(canvas, overlays["brace_agent"],
                                _alpha(t_crit[3]) * 0.92)

        yield canvas


# ── Standalone preview ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))

    # Save frame at t=12 s (all text visible, before fade-out)
    preview_frame = None
    target_sec    = 12.0
    for idx, frame in enumerate(scene_intro(duration=15, fade_out=True)):
        if idx / FPS >= target_sec:
            preview_frame = frame
            break

    if preview_frame:
        out_path = os.path.join(out_dir, "preview_intro.png")
        preview_frame.save(out_path)
        print(f"Preview saved → {out_path}")
    else:
        print("No frame generated.")
