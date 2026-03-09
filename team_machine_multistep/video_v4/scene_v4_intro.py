"""
scene_v4_intro.py — Intro card for video v4.

Two phases:
  Phase 1 (anim_duration ≈ 5 s)
      Animated build: title → subtitle → criteria, no fade-out.
      Reuses _build_overlays() and _CRITERIA_TEXT from scene_v3_intro.

  Phase 2 (hold_duration ≈ 3 s)
      Static hold at full visibility.  Glowing rectangular highlight boxes
      fade in around δ₁ (criterion 0) and TPI / δ₄ (criterion 3), signalling
      that only these two criteria will be shown in scenes 2 and 3.
"""

import sys
import os

_V2_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "video_v2")
_V3_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "video_v3")
sys.path.insert(0, _V2_DIR)
sys.path.insert(0, _V3_DIR)

import numpy as np
from PIL import Image, ImageDraw

from video_utils import W, H, FPS, smoothstep, composite_rgba
from scene_v3_intro import _CRITERIA_TEXT, _build_overlays


# ── Highlight-box overlay ─────────────────────────────────────────────────────

def _make_highlight_box_overlay(x1, y1, x2, y2, color_rgb, fw=W, fh=H):
    """
    Return a full-frame (fw × fh) RGBA image with a glowing rectangle drawn
    from (x1, y1) to (x2, y2).  Alpha is 0 everywhere except the border.
    """
    r, g, b = color_rgb
    img  = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, mode="RGBA")

    # Outer glow: wide + dim → inner: narrow + bright
    glow_spec = [
        (9, 12, 1),   # (expand_px, alpha, line_width)
        (6, 28, 1),
        (4, 52, 1),
        (2, 85, 2),
        (1, 130, 2),
        (0, 210, 2),  # solid core
    ]
    for offset, alpha, lw in glow_spec:
        draw.rectangle(
            [x1 - offset, y1 - offset, x2 + offset, y2 + offset],
            outline=(r, g, b, alpha),
            width=lw,
        )
    return img


# ── Pre-build highlight boxes ─────────────────────────────────────────────────
#
# Criterion y_positions (from scene_v3_intro): [375, 505, 635, 765]
# Each row: symbol at y0 (va=center, size=26), line1 at y0+42, line2 at y0+68
# Colour bar: x ≈ 154–173 px (0.08–0.09 × W).  Main text from x=190.
# Brackets start at BX=1450.
#
# Box spans slightly past the colour bar on the left and just before brackets.

_BOX_X1 = 132
_BOX_X2 = 1443

def _make_criterion_box(crit_idx):
    y0  = [375, 505, 635, 765][crit_idx]
    col = _CRITERIA_TEXT[crit_idx]["color"]
    return _make_highlight_box_overlay(_BOX_X1, y0 - 30, _BOX_X2, y0 + 82, col)


# ── Main generator ────────────────────────────────────────────────────────────

def scene_v4_intro(anim_duration=5.0, hold_duration=3.0):
    """
    Yield 1920×1080 PIL RGB frames.

    anim_duration : animated build (no fade-out at end)
    hold_duration : static hold with glowing boxes on δ₁ and TPI/δ₄
    """
    overlays   = _build_overlays()
    box_d1     = _make_criterion_box(0)   # δ₁  — criterion 0
    box_tpi    = _make_criterion_box(3)   # TPI — criterion 3

    # ── Phase 1: animated build ───────────────────────────────────────────────
    n_anim   = int(anim_duration * FPS)
    fade_dur = 0.45
    t_title  = 0.0
    t_info   = 0.25
    t_header = 0.55
    t_crit   = [0.9, 1.4, 1.9, 2.4]

    for i in range(n_anim):
        t = i / FPS

        def _alpha(start_t, _t=t):
            return smoothstep(min(max(_t - start_t, 0) / fade_dur, 1))

        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        canvas = composite_rgba(canvas, overlays["title"],        _alpha(t_title))
        canvas = composite_rgba(canvas, overlays["info"],         _alpha(t_info))
        canvas = composite_rgba(canvas, overlays["header"],       _alpha(t_header))
        canvas = composite_rgba(canvas, overlays["header_bar_l"], _alpha(t_header) * 0.7)
        canvas = composite_rgba(canvas, overlays["header_bar_r"], _alpha(t_header) * 0.7)

        for ci, tc in enumerate(t_crit):
            a = _alpha(tc)
            canvas = composite_rgba(canvas, overlays[f"crit_{ci}"],      a)
            canvas = composite_rgba(canvas, overlays[f"crit_bar_{ci}"],  a * 0.85)

        canvas = composite_rgba(canvas, overlays["brace_baseline"], _alpha(t_crit[0]) * 0.92)
        canvas = composite_rgba(canvas, overlays["brace_agent"],    _alpha(t_crit[3]) * 0.92)

        yield canvas

    # ── Phase 2: hold with highlight boxes ────────────────────────────────────
    n_hold      = int(hold_duration * FPS)
    t_box_start = 0.30   # boxes begin to appear 0.3 s into the hold
    t_box_fade  = 0.55   # fade-in duration

    # Build the fully-visible base frame once
    base = Image.new("RGB", (W, H), (0, 0, 0))
    base = composite_rgba(base, overlays["title"],        1.0)
    base = composite_rgba(base, overlays["info"],         1.0)
    base = composite_rgba(base, overlays["header"],       1.0)
    base = composite_rgba(base, overlays["header_bar_l"], 0.7)
    base = composite_rgba(base, overlays["header_bar_r"], 0.7)
    for ci in range(4):
        base = composite_rgba(base, overlays[f"crit_{ci}"],     1.0)
        base = composite_rgba(base, overlays[f"crit_bar_{ci}"], 0.85)
    base = composite_rgba(base, overlays["brace_baseline"], 0.92)
    base = composite_rgba(base, overlays["brace_agent"],    0.92)

    for i in range(n_hold):
        t_hold = i / FPS
        canvas = base.copy()

        a_boxes = smoothstep(min(max(t_hold - t_box_start, 0) / t_box_fade, 1))
        if a_boxes > 0:
            canvas = composite_rgba(canvas, box_d1,  a_boxes)
            canvas = composite_rgba(canvas, box_tpi, a_boxes)

        yield canvas
