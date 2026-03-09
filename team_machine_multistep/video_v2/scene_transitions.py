"""
scene_transitions.py — Reusable field transition animations.

Provides generators that cycle through all four fields
  Dark Matter → Stars → Gas → Gas Temperature
with smooth crossfades and a gentle slow zoom.

Functions
---------
prepare_transition_renders(hdf5_path, tag, renders_dir, tag_prefix)
    Pre-render the four field images for a single halo (cached).

render_set_from_cache(renders_dir, tag_prefix)
    Load the four pre-rendered images as a dict {field_idx: PIL Image}.

scene_single_halo_transition(render_set, hold_sec=2.5, xfade_sec=1.2,
                              loop=False)
    Full-screen DM → Stars → Gas → Gas Temperature for one halo.

scene_three_halo_transition(render_sets, hold_sec=2.5, xfade_sec=1.2)
    Three halos side-by-side, all cycling simultaneously.

scene_six_halo_grid_transition(render_sets, hold_sec=3.0, xfade_sec=1.5)
    3 × 2 grid of 6 halos, all cycling simultaneously. Slower pace.

Usage example
-------------
    from scene_transitions import (
        prepare_transition_renders, render_set_from_cache,
        scene_single_halo_transition, scene_three_halo_transition,
        scene_six_halo_grid_transition,
    )
    from video_utils import PARTICLE_DIR, FILE_MAP, RENDERS_DIR, get_top_halos

    hdf5   = os.path.join(PARTICLE_DIR, FILE_MAP["R1"])
    tag    = get_top_halos(hdf5, n=1)[0][1]  # most massive
    prefix = f"R1_tag{tag}"

    prepare_transition_renders(hdf5, tag, RENDERS_DIR, prefix)
    rset = render_set_from_cache(RENDERS_DIR, prefix)

    for frame in scene_single_halo_transition(rset):
        ...
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from video_utils import (
    W, H, FPS,
    FIELD_CMAPS, FIELD_LABELS, FIELD_TYPES, FIELD_ACCENT_RGB,
    PARTICLE_DIR, RENDERS_DIR, FILE_MAP,
    smoothstep, blend, fit_to_frame, zoom_image,
    add_glow, add_vignette, composite_rgba,
    make_text_overlay, render_field_image, get_top_halos,
)
from PIL import Image
import numpy as np


# ── Render helpers ─────────────────────────────────────────────────────────────

def prepare_transition_renders(hdf5_path, tag, renders_dir=RENDERS_DIR,
                                tag_prefix=None, width=4.5):
    """
    Pre-render the 4 field images (DM, Stars, Gas, Gas Temperature)
    for *tag* using opencosmo.  Skips any that are already on disk.

    Parameters
    ----------
    hdf5_path   : Path to the opencosmo particle HDF5 file
    tag         : Halo unique_tag
    renders_dir : Directory for cached PNGs
    tag_prefix  : Name prefix used in filenames, e.g. "R1_tag12345".
                  Defaults to "halo_{tag}" if not provided.
    width       : Projection half-width in R_halo units

    Returns
    -------
    tag_prefix (str)
    """
    if tag_prefix is None:
        tag_prefix = f"halo_{tag}"
    os.makedirs(renders_dir, exist_ok=True)

    for fi in range(4):
        out = os.path.join(renders_dir, f"{tag_prefix}_f{fi}.png")
        render_field_image(hdf5_path, tag, fi, out, width=width, cache=True)

    return tag_prefix


def render_set_from_cache(renders_dir, tag_prefix):
    """
    Load 4 pre-rendered field images from disk.

    Returns dict {0: PIL_Image, 1: PIL_Image, 2: PIL_Image, 3: PIL_Image}
    or None for any missing file.
    """
    rset = {}
    for fi in range(4):
        path = os.path.join(renders_dir, f"{tag_prefix}_f{fi}.png")
        if os.path.exists(path):
            rset[fi] = Image.open(path).convert("RGB")
        else:
            rset[fi] = None
    return rset


# ── Scene generators ───────────────────────────────────────────────────────────

def scene_single_halo_transition(render_set,
                                  hold_sec=2.5,
                                  xfade_sec=1.2,
                                  halo_label=None,
                                  loop=False,
                                  fade_in_sec=0.6,
                                  fade_out_sec=0.6):
    """
    Full-screen field transition for a single halo:
      Dark Matter → Stars → Gas → Gas Temperature

    Slower than the original video (hold=2.5 s, crossfade=1.2 s)
    to let viewers appreciate each projection.

    Parameters
    ----------
    render_set    : dict {0: PIL, 1: PIL, 2: PIL, 3: PIL}
                    from render_set_from_cache() or render_field_image().
                    A None entry is skipped gracefully.
    hold_sec      : How long to hold each field (seconds)
    xfade_sec     : Crossfade duration between fields (seconds)
    halo_label    : Optional string shown in lower-left, e.g. "Halo 1 of 3"
    loop          : If True, cycle back to DM after Gas Temperature
    fade_in_sec   : Fade in from black at scene start
    fade_out_sec  : Fade to black at scene end (0 to skip)

    Yields
    ------
    1920 × 1080 PIL RGB frames
    """
    n_fields     = 4
    frames_hold  = int(hold_sec  * FPS)
    frames_xfade = int(xfade_sec * FPS)
    frames_fin   = int(fade_in_sec  * FPS)
    frames_fout  = int(fade_out_sec * FPS)

    # Prepare fitted + post-processed images for each field
    field_imgs = []
    for fi in range(n_fields):
        img = render_set.get(fi)
        if img is None:
            img = Image.new("RGB", (W, H), (0, 0, 0))
        img = fit_to_frame(img)
        img = add_glow(img, 14, 0.32)
        img = add_vignette(img, 0.42)
        field_imgs.append(img)

    # Pre-render label overlays (field name + optional halo label)
    label_ovs = []
    for fi in range(n_fields):
        ac = FIELD_ACCENT_RGB[FIELD_CMAPS[fi]]
        lines = [
            {"text":  FIELD_LABELS[fi],
             "x": int(W * 0.055), "y": int(H * 0.065), "size": 44,
             "color_rgb": ac, "bold": True, "stroke_w": 3,
             "ha": "left", "va": "center"},
        ]
        if halo_label:
            lines.append({
                "text":  halo_label,
                "x": int(W * 0.055), "y": int(H * 0.92), "size": 18,
                "color_rgb": (155, 165, 185), "bold": False, "stroke_w": 1,
                "ha": "left",
            })
        label_ovs.append(make_text_overlay(lines))

    black = Image.new("RGB", (W, H), (0, 0, 0))

    # ── Fade in from black ────────────────────────────────────────────────────
    for j in range(frames_fin):
        t = smoothstep(j / max(frames_fin, 1))
        yield blend(black, field_imgs[0], t)

    # ── Field cycle ───────────────────────────────────────────────────────────
    n_cycles = n_fields if not loop else n_fields
    for fi in range(n_cycles):
        cur_img  = field_imgs[fi]
        next_img = field_imgs[(fi + 1) % n_fields]
        cur_ov   = label_ovs[fi]

        # Hold with very slow zoom-in
        for j in range(frames_hold):
            t   = j / max(frames_hold, 1)
            zm  = 1.0 + 0.045 * smoothstep(t)
            img = zoom_image(cur_img, zm)
            a   = smoothstep(min(j / max(frames_hold * 0.30, 1), 1))
            frame = composite_rgba(img, cur_ov, alpha_mult=a)
            yield frame

        # Crossfade to next field
        is_last = (fi == n_cycles - 1) and not loop
        for j in range(frames_xfade):
            t     = smoothstep(j / max(frames_xfade, 1))
            frame = blend(cur_img, next_img, t)
            a_lbl = max(0.0, 1.0 - smoothstep(t * 1.6))
            frame = composite_rgba(frame, cur_ov, alpha_mult=a_lbl)
            yield frame

    # ── Fade out ──────────────────────────────────────────────────────────────
    last_field = field_imgs[0 if loop else n_fields - 1]
    for j in range(frames_fout):
        t = smoothstep(j / max(frames_fout, 1))
        yield blend(last_field, black, t)


def scene_three_halo_transition(render_sets,
                                 hold_sec=2.5,
                                 xfade_sec=1.2,
                                 group_labels=None,
                                 fade_in_sec=0.6,
                                 fade_out_sec=0.8):
    """
    Three halos displayed side-by-side, all cycling through fields
    simultaneously:  Dark Matter → Stars → Gas → Gas Temperature.

    Parameters
    ----------
    render_sets   : list of 3 render_set dicts (one per halo).
                    Each render_set is {0: PIL, 1: PIL, 2: PIL, 3: PIL}.
    hold_sec      : Hold duration per field (seconds)
    xfade_sec     : Crossfade duration (seconds)
    group_labels  : Optional list of 3 short strings, one per halo,
                    displayed below each panel (e.g. ["R₁", "R₁∩R₂", "R₁\\R₂"])
    fade_in_sec   : Fade in at start
    fade_out_sec  : Fade out at end

    Yields
    ------
    1920 × 1080 PIL RGB frames
    """
    n_halos      = 3
    n_fields     = 4
    frames_hold  = int(hold_sec  * FPS)
    frames_xfade = int(xfade_sec * FPS)
    frames_fin   = int(fade_in_sec  * FPS)
    frames_fout  = int(fade_out_sec * FPS)

    # ── Panel geometry (three landscape strips with thin separators) ───────────
    SEP      = 3
    PW       = (W - (n_halos - 1) * SEP) // n_halos   # panel width  ≈ 638 px
    PH       = H                                        # full height

    def _make_panel_strip(img_rgb, panel_idx):
        """Fit img into a PW × PH strip (square image letterboxed vertically)."""
        fitted  = img_rgb.resize((PW, PW), Image.LANCZOS)  # square
        strip   = Image.new("RGB", (PW, PH), (0, 0, 0))
        y_off   = (PH - PW) // 2
        strip.paste(fitted, (0, y_off))
        return strip

    def _assemble(strips, sep_color=(255, 255, 255)):
        """Concatenate 3 strips horizontally with 1-px separators."""
        from PIL import ImageDraw
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        for idx, strip in enumerate(strips):
            x_off = idx * (PW + SEP)
            canvas.paste(strip, (x_off, 0))
        # Draw vertical separators
        draw = ImageDraw.Draw(canvas)
        for idx in range(1, n_halos):
            sx = idx * (PW + SEP) - SEP
            draw.line([sx, 0, sx, H - 1], fill=(80, 80, 80), width=SEP)
        return canvas

    # Prepare per-halo, per-field fitted images
    panel_imgs = []   # [halo_idx][field_idx] = PIL strip
    for h_idx, rset in enumerate(render_sets[:n_halos]):
        halo_fields = []
        for fi in range(n_fields):
            img = rset.get(fi) if rset else None
            if img is None:
                img = Image.new("RGB", (W, H), (0, 0, 0))
            img = add_glow(img.resize((PW, PW), Image.LANCZOS), 8, 0.25)
            img = add_vignette(img, 0.35)
            halo_fields.append(img)
        panel_imgs.append(halo_fields)

    # Pre-render the shared field-label overlay (centered, shown on the composite)
    label_ovs = []
    for fi in range(n_fields):
        ac = FIELD_ACCENT_RGB[FIELD_CMAPS[fi]]
        lines = [
            {"text":  FIELD_LABELS[fi],
             "x": W // 2, "y": int(H * 0.055), "size": 40,
             "color_rgb": ac, "bold": True, "stroke_w": 3},
        ]
        # Optional per-panel group labels at the bottom
        if group_labels:
            for h_idx, gl in enumerate(group_labels[:n_halos]):
                lx = h_idx * (PW + SEP) + PW // 2
                lines.append({
                    "text":  gl,
                    "x": lx, "y": int(H * 0.940), "size": 16,
                    "color_rgb": (160, 170, 190), "bold": False, "stroke_w": 1,
                })
        label_ovs.append(make_text_overlay(lines))

    black = Image.new("RGB", (W, H), (0, 0, 0))

    def _composite_frame(fi, blend_alpha=None, next_fi=None):
        """Build one composed frame at a given field index."""
        strips = []
        for h_idx in range(n_halos):
            cur_strip = panel_imgs[h_idx][fi]
            if blend_alpha is not None and next_fi is not None:
                nxt_strip = panel_imgs[h_idx][next_fi]
                # Resize both to PW×PW before blending (they already are)
                merged = Image.fromarray(
                    (np.array(cur_strip, dtype=np.float32) * (1 - blend_alpha)
                     + np.array(nxt_strip, dtype=np.float32) * blend_alpha
                    ).clip(0, 255).astype(np.uint8)
                )
                strips.append(merged)
            else:
                strips.append(cur_strip)
        canvas = _assemble(strips)
        # letterbox: add black top/bottom bars for the non-square region
        return canvas

    # ── Fade in ───────────────────────────────────────────────────────────────
    first_frame = _composite_frame(0)
    for j in range(frames_fin):
        t = smoothstep(j / max(frames_fin, 1))
        yield blend(black, first_frame, t)

    # ── Field cycle ───────────────────────────────────────────────────────────
    for fi in range(n_fields):
        cur_ov   = label_ovs[fi]
        next_fi  = (fi + 1) % n_fields

        # Hold frames
        for j in range(frames_hold):
            t   = j / max(frames_hold, 1)
            zm  = 1.0 + 0.03 * smoothstep(t)
            frame = _composite_frame(fi)
            if zm > 1.001:
                frame = frame.resize(
                    (int(W * zm), int(H * zm)), Image.BILINEAR
                ).crop(
                    ((int(W * zm) - W) // 2, (int(H * zm) - H) // 2,
                     (int(W * zm) - W) // 2 + W, (int(H * zm) - H) // 2 + H)
                )
            a_lbl = smoothstep(min(j / max(frames_hold * 0.30, 1), 1))
            frame = composite_rgba(frame, cur_ov, alpha_mult=a_lbl)
            yield frame

        # Crossfade to next field
        for j in range(frames_xfade):
            t  = j / max(frames_xfade, 1)
            ta = smoothstep(t)
            frame = _composite_frame(fi, blend_alpha=ta, next_fi=next_fi)
            a_lbl = max(0.0, 1.0 - smoothstep(ta * 1.6))
            frame = composite_rgba(frame, cur_ov, alpha_mult=a_lbl)
            yield frame

    # ── Fade out ──────────────────────────────────────────────────────────────
    last_frame = _composite_frame(0)
    for j in range(frames_fout):
        t = smoothstep(j / max(frames_fout, 1))
        yield blend(last_frame, black, t)


def scene_six_halo_grid_transition(render_sets,
                                    hold_sec=3.0,
                                    xfade_sec=1.5,
                                    group_labels=None,
                                    fade_in_sec=0.8,
                                    fade_out_sec=0.8):
    """
    3 × 2 grid of 6 halos, all cycling DM → Stars → Gas → Gas Temperature
    simultaneously.  Slower and longer than the 3-halo version for a
    more meditative, gallery-like feel.

    Layout: 3 columns × 2 rows, dark separators between panels.
    Each panel shows one halo; all panels advance fields in sync.

    Parameters
    ----------
    render_sets   : List of at least 6 render_set dicts.
                    Each render_set is {0: PIL, 1: PIL, 2: PIL, 3: PIL}.
    hold_sec      : Hold duration per field (seconds), default 3.0
    xfade_sec     : Crossfade duration (seconds), default 1.5
    group_labels  : Optional list of 6 short strings shown below each panel.
    fade_in_sec   : Fade in at scene start
    fade_out_sec  : Fade to black at scene end

    Yields
    ------
    1920 × 1080 PIL RGB frames
    """
    from PIL import ImageDraw as _IDraw

    N_COLS, N_ROWS = 3, 2
    n_halos  = N_COLS * N_ROWS
    n_fields = 4

    frames_hold  = int(hold_sec  * FPS)
    frames_xfade = int(xfade_sec * FPS)
    frames_fin   = int(fade_in_sec  * FPS)
    frames_fout  = int(fade_out_sec * FPS)

    # ── Panel geometry ─────────────────────────────────────────────────────────
    SEP_H = 4   # column separator pixels
    SEP_V = 4   # row separator pixels
    PW    = (W - (N_COLS - 1) * SEP_H) // N_COLS   # ≈ 637 px
    PH    = (H - (N_ROWS - 1) * SEP_V) // N_ROWS   # ≈ 538 px
    SQ    = min(PW, PH)   # square projection size  ≈ 538 px

    # ── Pre-process all panel images ───────────────────────────────────────────
    panel_imgs = []   # [halo_idx][field_idx] = PIL image SQ × SQ
    for h_idx in range(n_halos):
        rset = render_sets[h_idx] if h_idx < len(render_sets) else None
        halo_fields = []
        for fi in range(n_fields):
            img = rset.get(fi) if rset else None
            if img is None:
                img = Image.new("RGB", (SQ, SQ), (0, 0, 0))
            else:
                img = img.resize((SQ, SQ), Image.LANCZOS)
            img = add_glow(img, 9, 0.27)
            img = add_vignette(img, 0.32)
            halo_fields.append(img)
        panel_imgs.append(halo_fields)

    def _build_grid(fi, blend_alpha=None, next_fi=None):
        """Assemble the 3×2 grid at field index fi."""
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        draw   = _IDraw.Draw(canvas)

        for h_idx in range(n_halos):
            col = h_idx % N_COLS
            row = h_idx // N_COLS
            x_off = col * (PW + SEP_H) + (PW - SQ) // 2
            y_off = row * (PH + SEP_V) + (PH - SQ) // 2

            cur = panel_imgs[h_idx][fi]
            if blend_alpha is not None and next_fi is not None:
                nxt = panel_imgs[h_idx][next_fi]
                cur = Image.fromarray(
                    (np.array(cur, np.float32) * (1 - blend_alpha)
                     + np.array(nxt, np.float32) * blend_alpha
                    ).clip(0, 255).astype(np.uint8))
            canvas.paste(cur, (x_off, y_off))

        # Column separators
        for ci in range(1, N_COLS):
            sx = ci * (PW + SEP_H) - SEP_H
            draw.line([sx, 0, sx, H - 1], fill=(45, 45, 50), width=SEP_H)
        # Row separator
        sy = PH + SEP_V - SEP_V
        draw.line([0, sy, W - 1, sy], fill=(45, 45, 50), width=SEP_V)

        return canvas

    # Shared field-label + optional group-label overlays per field
    label_ovs = []
    for fi in range(n_fields):
        ac    = FIELD_ACCENT_RGB[FIELD_CMAPS[fi]]
        lines = [
            {"text": FIELD_LABELS[fi],
             "x": W // 2, "y": int(H * 0.045), "size": 42,
             "color_rgb": ac, "bold": True, "stroke_w": 3},
        ]
        if group_labels:
            for h_idx, gl in enumerate(group_labels[:n_halos]):
                col = h_idx % N_COLS
                row = h_idx // N_COLS
                lx = col * (PW + SEP_H) + PW // 2
                ly = row * (PH + SEP_V) + PH - 16
                lines.append({
                    "text": gl,
                    "x": lx, "y": ly, "size": 13,
                    "color_rgb": (150, 160, 180), "bold": False, "stroke_w": 1,
                })
        label_ovs.append(make_text_overlay(lines))

    black = Image.new("RGB", (W, H), (0, 0, 0))

    # ── Fade in ────────────────────────────────────────────────────────────────
    first = _build_grid(0)
    for j in range(frames_fin):
        yield blend(black, first, smoothstep(j / max(frames_fin, 1)))

    # ── Field cycle ────────────────────────────────────────────────────────────
    for fi in range(n_fields):
        cur_ov  = label_ovs[fi]
        next_fi = (fi + 1) % n_fields

        for j in range(frames_hold):
            t  = j / max(frames_hold, 1)
            a  = smoothstep(min(j / max(frames_hold * 0.28, 1), 1))
            frame = _build_grid(fi)
            frame = composite_rgba(frame, cur_ov, alpha_mult=a)
            yield frame

        for j in range(frames_xfade):
            t  = smoothstep(j / max(frames_xfade, 1))
            frame = _build_grid(fi, blend_alpha=t, next_fi=next_fi)
            frame = composite_rgba(frame, cur_ov,
                                   alpha_mult=max(0.0, 1 - smoothstep(t * 1.5)))
            yield frame

    # ── Fade out ───────────────────────────────────────────────────────────────
    last = _build_grid(0)
    for j in range(frames_fout):
        yield blend(last, black, smoothstep(j / max(frames_fout, 1)))


# ── Standalone demo ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    out_dir  = os.path.dirname(os.path.abspath(__file__))
    renders  = os.path.join(out_dir, "renders")

    # Pick the most massive halo from each of 3 groups for a demo
    demo_groups = ["R1", "R1_andR2", "R1_notR2"]
    prefixes    = []
    render_sets = []

    for g in demo_groups:
        hdf5 = os.path.join(PARTICLE_DIR, FILE_MAP[g])
        if not os.path.exists(hdf5):
            print(f"  WARNING: {hdf5} not found — skipping"); continue
        tag    = get_top_halos(hdf5, n=1)[0][1]
        prefix = prepare_transition_renders(hdf5, tag, renders, f"{g}_tag{tag}")
        prefixes.append(prefix)
        render_sets.append(render_set_from_cache(renders, prefix))

    if len(render_sets) >= 1:
        # Save one preview frame of the single-halo version
        import shutil, tempfile
        tmpdir = tempfile.mkdtemp()
        idx    = 0
        for frame in scene_single_halo_transition(
                render_sets[0], hold_sec=2.5, xfade_sec=1.2,
                halo_label=f"Demo: {demo_groups[0]}"):
            if idx == int(FPS * 2.8):   # frame during DM hold
                frame.save(os.path.join(out_dir, "preview_transition_single.png"))
                print(f"Preview → preview_transition_single.png")
                break
            idx += 1
        shutil.rmtree(tmpdir)

    if len(render_sets) >= 3:
        idx = 0
        for frame in scene_three_halo_transition(
                render_sets[:3],
                hold_sec=2.5, xfade_sec=1.2,
                group_labels=[demo_groups[i] for i in range(3)]):
            if idx == int(FPS * 2.8):
                frame.save(os.path.join(out_dir, "preview_transition_three.png"))
                print(f"Preview → preview_transition_three.png")
                break
            idx += 1
