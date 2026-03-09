#!/usr/bin/env python3
"""
make_cluster_zoo_video.py  —  Cinematic HACC Cluster Morphology Showcase
========================================================================

Video structure (≈87 seconds @ 24 fps):

  Scene 1  Title card                            5 s
  Scene 2  Gas-mass collage (R1, all 30 halos)  8 s
  Scene 3  Selection tour (7 groups)            30 s
  Scene 4  Field crossfade  DM→Stars→Gas→Temp  30 s
  Scene 5  4-field finale (most massive)        10 s
  Scene 6  Credits                               4 s

Color palette matches multifield_4field_random6_massive.png:
  DM       "pink"
  Stars    "gist_yarg_r"
  Gas      "plasma_r"
  Gas Temp "rainbow_r"

Usage:
  /home/nramachandra/anaconda3/envs/cosmodev/bin/python3 make_cluster_zoo_video.py
"""

import os, shutil, subprocess, time
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from PIL import Image, ImageDraw, ImageFilter
import opencosmo as oc  # type: ignore
from opencosmo.analysis import halo_projection_array  # type: ignore

# ── Paths ──────────────────────────────────────────────────────────────────────
EXPERIMENT_DIR = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/runs/research_20260218_105441"
PARTICLE_DIR   = "/data/a/cpac/nramachandra/Projects/AmSC/particle_data"
HALO_VIZ_DIR   = os.path.join(EXPERIMENT_DIR, "halo_viz")
VIDEO_DIR      = os.path.join(EXPERIMENT_DIR, "video_assets")
RENDERS_DIR    = os.path.join(VIDEO_DIR, "renders")
FRAMES_DIR     = os.path.join(VIDEO_DIR, "frames")
OUTPUT_VIDEO   = os.path.join(EXPERIMENT_DIR, "cluster_zoo.mp4")

os.makedirs(RENDERS_DIR, exist_ok=True)
os.makedirs(FRAMES_DIR,  exist_ok=True)

# ── Video parameters ───────────────────────────────────────────────────────────
FPS = 24
W, H = 1920, 1080

# ── Color palette (CANONICAL — matches multifield_4field images) ───────────────
CMAP_DM    = "pink"
CMAP_STARS = "gist_yarg_r"
CMAP_GAS   = "plasma_r"
CMAP_TEMP  = "rainbow_r"

FIELD_CMAPS  = [CMAP_DM, CMAP_STARS, CMAP_GAS, CMAP_TEMP]
FIELD_LABELS = ["Dark Matter", "Stars", "Gas", "Gas Temperature"]
FIELD_TYPES  = [("dm",  "particle_mass"),
                ("star","particle_mass"),
                ("gas", "particle_mass"),
                ("gas", "temperature")]

# Peak color of each colormap (for text accent colours)
FIELD_ACCENT_RGB = {
    CMAP_DM:    (255, 180, 200),   # pink highlight
    CMAP_STARS: (230, 230, 230),   # near-white
    CMAP_GAS:   (255, 200,  60),   # plasma gold
    CMAP_TEMP:  ( 60, 210, 255),   # rainbow cyan
}

# ── Group definitions ─────────────────────────────────────────────────────────
FILE_MAP = {
    "R1":       "R1.hdf5",
    "R1_andR2": "R1andR2.hdf5",
    "R1_andR3": "R1andR3.hdf5",
    "R1_andR4": "R1andR4.hdf5",
    "R1_notR2": "R1notR2.hdf5",
    "R1_notR3": "R1notR3.hdf5",
    "R1_notR4": "R1notR4.hdf5",
}
GROUP_ORDER = ["R1", "R1_andR2", "R1_andR3", "R1_andR4",
               "R1_notR2", "R1_notR3", "R1_notR4"]

GROUP_COLORS_RGB = {
    "R1":       (210, 210, 210),
    "R1_andR2": ( 80, 160, 255),
    "R1_andR3": ( 80, 255, 140),
    "R1_andR4": (200,  80, 255),
    "R1_notR2": (255, 140,  40),
    "R1_notR3": (255,  60,  60),
    "R1_notR4": (255, 230,  40),
}

GROUP_TITLES = {
    "R1":       "R₁  —  CoM offset  δ₁ < 0.07",
    "R1_andR2": "R₁ ∩ R₂  —  + DM/gas centroid offset  δ₂ < 0.07",
    "R1_andR3": "R₁ ∩ R₃  —  + Core entropy  K_core < 150 keV·cm²",
    "R1_andR4": "R₁ ∩ R₄  —  + TPI < 0  (cool-core clusters)",
    "R1 \\ R₂": "R₁ \\ R₂  —  δ₁ relaxed, disturbed DM/gas centroid",
    "R1_notR3": "R₁ \\ R₃  —  δ₁ relaxed, elevated core entropy",
    "R1_notR4": "R₁ \\ R₄  —  δ₁ relaxed, warm core / active AGN",
}
GROUP_TITLES = {
    "R1":       "R₁  —  CoM offset  δ₁ < 0.07",
    "R1_andR2": "R₁ ∩ R₂  —  δ₁ & δ₂ relaxed",
    "R1_andR3": "R₁ ∩ R₃  —  δ₁ relaxed + cool core",
    "R1_andR4": "R₁ ∩ R₄  —  δ₁ relaxed + strong cool core (TPI)",
    "R1_notR2": "R₁ \\ R₂  —  δ₁ relaxed, disturbed DM/gas centroid",
    "R1_notR3": "R₁ \\ R₃  —  δ₁ relaxed, high core entropy",
    "R1_notR4": "R₁ \\ R₄  —  δ₁ relaxed, warm core / active AGN",
}

# ─────────────────────────────────────────────────────────────────────────────
# ── UTILITIES ─────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def smoothstep(t, power=2):
    """Smooth easing in [0, 1]."""
    t = float(np.clip(t, 0, 1))
    if power == 2:
        return t * t * (3 - 2 * t)
    return t ** power / (t ** power + (1 - t) ** power)


def recolor_image(pil_img, cmap_name, p_lo=2, p_hi=90, invert=False, bg_thresh=None):
    """
    Convert PIL Image to grayscale and apply a matplotlib colormap.

    For overview/collage images where bright=dense gas and background=black:
      - Set invert=True with plasma_r to match opencosmo rendering convention
        (bright → low norm → yellow in plasma_r; background forced to black).
      - With invert=False and a forward colormap like 'hot', bright → yellow directly.
      - bg_thresh: pixels at or below this gray value are forced to pure black.
        Default (None) auto-estimates from the image.  Set to ~20 when the source
        image has faint matplotlib figure borders that should be hidden.
    """
    gray = np.array(pil_img.convert("L"), dtype=np.float32)
    # Background: pixels that are nearly black in the original image
    if bg_thresh is None:
        bg_thresh = max(3.0, float(np.percentile(gray, 3)) + 1.0)
    bg_mask = gray <= bg_thresh
    nonzero = gray[~bg_mask]
    if len(nonzero) == 0:
        return Image.fromarray(np.zeros((gray.shape[0], gray.shape[1], 3), np.uint8))
    lo = np.percentile(nonzero, p_lo)
    hi = np.percentile(nonzero, p_hi)
    if hi <= lo:
        hi = lo + 1.0
    norm = np.clip((gray - lo) / (hi - lo), 0, 1)
    if invert:
        norm = 1.0 - norm
    cmap = plt.get_cmap(cmap_name)
    rgb = (cmap(norm)[:, :, :3] * 255).astype(np.uint8)
    rgb[bg_mask] = 0          # Force background pixels to pure black
    return Image.fromarray(rgb)


def fit_to_frame(pil_img, fw=W, fh=H):
    """Scale image to fit (fw, fh) preserving aspect ratio; black bars fill rest."""
    aspect = pil_img.width / pil_img.height
    target = fw / fh
    if aspect > target:
        nw, nh = fw, int(fw / aspect)
    else:
        nw, nh = int(fh * aspect), fh
    resized = pil_img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (fw, fh), (0, 0, 0))
    canvas.paste(resized, ((fw - nw) // 2, (fh - nh) // 2))
    return canvas


def zoom_image(pil_img, zoom=1.0, cx_frac=0.5, cy_frac=0.5):
    """Zoom into image (zoom > 1 enlarges). cx_frac/cy_frac = centre [0-1]."""
    if zoom <= 1.001:
        return pil_img
    iw, ih = pil_img.size
    nw, nh = int(iw / zoom), int(ih / zoom)
    cx = int(iw * cx_frac)
    cy = int(ih * cy_frac)
    x0 = max(0, min(cx - nw // 2, iw - nw))
    y0 = max(0, min(cy - nh // 2, ih - nh))
    return pil_img.crop((x0, y0, x0 + nw, y0 + nh)).resize((iw, ih), Image.LANCZOS)


def blend(img1, img2, alpha):
    """Linear blend. alpha=0 → img1, alpha=1 → img2."""
    alpha = float(np.clip(alpha, 0, 1))
    a1 = np.array(img1.convert("RGB"), dtype=np.float32)
    a2 = np.array(img2.convert("RGB"), dtype=np.float32)
    return Image.fromarray((a1 * (1 - alpha) + a2 * alpha).clip(0, 255).astype(np.uint8))


def add_glow(pil_img, radius=15, intensity=0.4):
    """Additive glow: blend original with blurred version."""
    blurred = pil_img.filter(ImageFilter.GaussianBlur(radius))
    a = np.array(pil_img, dtype=np.float32)
    b = np.array(blurred, dtype=np.float32)
    return Image.fromarray(np.clip(a + b * intensity, 0, 255).astype(np.uint8))


def crop_margins(pil_img, margin_frac=0.025):
    """Remove a fractional margin from all sides (removes matplotlib axis borders)."""
    w, h = pil_img.size
    mx, my = int(w * margin_frac), int(h * margin_frac)
    return pil_img.crop((mx, my, w - mx, h - my))


def add_vignette(pil_img, strength=0.55):
    """Darken edges radially."""
    arr = np.array(pil_img, dtype=np.float32)
    h, w = arr.shape[:2]
    y, x = np.ogrid[:h, :w]
    r = np.sqrt(((x - w/2) / (w/2))**2 + ((y - h/2) / (h/2))**2)
    mask = 1 - np.clip(r * strength, 0, 1)
    return Image.fromarray((arr * mask[:, :, None]).clip(0, 255).astype(np.uint8))


def composite_rgba(base_rgb, overlay_rgba, alpha_mult=1.0):
    """Composite an RGBA PIL overlay onto an RGB base image."""
    base = np.array(base_rgb.convert("RGB"), dtype=np.float32)
    ov   = np.array(overlay_rgba.convert("RGBA"), dtype=np.float32)
    mask = ov[:, :, 3:4] / 255.0 * alpha_mult
    rgb  = ov[:, :, :3]
    return Image.fromarray((base * (1 - mask) + rgb * mask).clip(0, 255).astype(np.uint8))


# ─────────────────────────────────────────────────────────────────────────────
# ── PRE-RENDER TEXT / DECORATION OVERLAYS ─────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def make_text_overlay(lines, fw=W, fh=H):
    """
    Render text lines as an RGBA PIL Image (transparent background).
    lines: list of dicts with keys: text, x, y, size, color_rgb, bold, alpha
    x, y are in pixel coordinates (int).
    Returns PIL RGBA image.
    """
    fig, ax = plt.subplots(figsize=(fw/100, fh/100))
    fig.patch.set_facecolor((0, 0, 0, 0))
    fig.patch.set_alpha(0.0)
    ax.set_position([0, 0, 1, 1])
    ax.set_xlim(0, fw); ax.set_ylim(0, fh)
    ax.axis("off")
    ax.set_facecolor((0, 0, 0, 0))

    for L in lines:
        r, g, b = L.get("color_rgb", (255, 255, 255))
        a = L.get("alpha", 1.0)
        fw_text = "bold" if L.get("bold", True) else "normal"
        stroke_w = L.get("stroke_w", 2)
        effects = [pe.withStroke(linewidth=stroke_w, foreground="black")]
        ax.text(L["x"], fh - L["y"], L["text"],
                ha=L.get("ha", "center"), va=L.get("va", "center"),
                fontsize=L["size"], fontweight=fw_text,
                color=(r/255, g/255, b/255, a),
                path_effects=effects)

    fig.canvas.draw()
    buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
    rw, rh = fig.canvas.get_width_height()
    arr = buf.reshape(rh, rw, 4).copy()
    plt.close(fig)
    return Image.fromarray(arr, "RGBA")


def make_separator_bar(color_rgb, x0_frac, x1_frac, y_frac, fw=W, fh=H, thickness=4):
    """Thin horizontal colour bar overlay (RGBA)."""
    overlay = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    y = int(fh * y_frac)
    x0 = int(fw * x0_frac)
    x1 = int(fw * x1_frac)
    r, g, b = color_rgb
    draw.rectangle([x0, y - thickness//2, x1, y + thickness//2], fill=(r, g, b, 230))
    return overlay


# ─────────────────────────────────────────────────────────────────────────────
# ── OPENCOSMO RENDER HELPERS ──────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def get_top_halos(hdf5_path, n=3):
    """Return [(mass, tag), …] for top-n halos by FoF mass."""
    data = oc.open(hdf5_path)
    info = []
    for halo in data.halos():
        props = halo["halo_properties"]
        tag  = int(props["unique_tag"])
        m    = props["fof_halo_mass"]
        mass = float(m.value) if hasattr(m, "value") else float(m)
        info.append((mass, tag))
    info.sort(reverse=True)
    return info[:n]


def render_field_image(hdf5_path, tag, field_idx, out_path, width=4.5):
    """
    Render a single field for a single halo.  Extracts just the projection
    axes (no colorbar / margins) and saves to out_path.
    Returns PIL RGB Image.
    """
    if os.path.exists(out_path):
        print(f"    [cache] {os.path.basename(out_path)}")
        return Image.open(out_path).convert("RGB")

    print(f"    Rendering field {FIELD_LABELS[field_idx]} for tag {tag} …")
    t0 = time.time()
    data = oc.open(hdf5_path)
    halo_ids = np.array([[tag]])
    params = {
        "fields": ([FIELD_TYPES[field_idx]],),
        "labels": ([FIELD_LABELS[field_idx]],),
        "cmaps":  ([FIELD_CMAPS[field_idx]],),
    }
    fig = halo_projection_array(halo_ids, data, params=params, width=width)
    fig.patch.set_facecolor("black")
    fig.set_size_inches(12, 12)
    fig.canvas.draw()

    # Find main projection axes (largest area)
    cands = [ax for ax in fig.axes if ax.get_position().width > 0.08]
    main_ax = max(cands, key=lambda ax: ax.get_position().width * ax.get_position().height)
    pos = main_ax.get_position()

    buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
    rw, rh = fig.canvas.get_width_height()
    arr = buf.reshape(rh, rw, 4)[:, :, :3].copy()

    x0, x1 = int(pos.x0 * rw), int(pos.x1 * rw)
    y0, y1 = int((1 - pos.y1) * rh), int((1 - pos.y0) * rh)
    y0, y1 = max(0, y0), min(rh, y1)
    x0, x1 = max(0, x0), min(rw, x1)
    cropped = arr[y0:y1, x0:x1]
    plt.close(fig)

    img = Image.fromarray(cropped)
    img.save(out_path)
    print(f"      saved {cropped.shape[1]}×{cropped.shape[0]}  ({time.time()-t0:.1f}s)")
    return img


def render_multifield_row(hdf5_path, tag, out_path):
    """
    Render a 1×4 multifield row (DM | Stars | Gas | Gas Temp) for one halo.
    Returns PIL RGB Image.
    """
    if os.path.exists(out_path):
        print(f"    [cache] {os.path.basename(out_path)}")
        return Image.open(out_path).convert("RGB")

    print(f"    Rendering 4-field row for tag {tag} …")
    t0 = time.time()
    data = oc.open(hdf5_path)
    halo_ids = np.array([[tag, tag, tag, tag]])
    params = {
        "fields": (FIELD_TYPES,),
        "labels": (FIELD_LABELS,),
        "cmaps":  (FIELD_CMAPS,),
    }
    fig = halo_projection_array(halo_ids, data, params=params, length_scale="all left")
    fig.patch.set_facecolor("black")
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    print(f"      saved  ({time.time()-t0:.1f}s)")
    return Image.open(out_path).convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# ── SCENE GENERATORS ──────────────────────────────────────────────────────────
# Each generator yields PIL RGB Images (one per frame, 1920×1080).
# ─────────────────────────────────────────────────────────────────────────────

def scene_title(duration=5):
    """Title card with gradient text fade-in."""
    n = int(duration * FPS)
    # Pre-render three text overlays at full opacity
    lines_main = [
        {"text": "HACC Simulation", "x": W//2, "y": int(H*0.43),
         "size": 74, "color_rgb": (255,255,255), "bold": True, "stroke_w": 3},
        {"text": "Cluster Morphology Zoo", "x": W//2, "y": int(H*0.53),
         "size": 48, "color_rgb": (170, 205, 255), "bold": True, "stroke_w": 2},
    ]
    lines_sub = [
        {"text": "Relaxation Criteria:  δ₁  ·  δ₂  ·  K_core  ·  TPI",
         "x": W//2, "y": int(H*0.62), "size": 26,
         "color_rgb": (160, 200, 255), "bold": False, "stroke_w": 1},
        {"text": "Frontier-E  ·  HACC Hydrodynamical Simulation",
         "x": W//2, "y": int(H*0.70), "size": 20,
         "color_rgb": (120, 160, 200), "bold": False, "stroke_w": 1},
    ]
    ov_main = make_text_overlay(lines_main)
    ov_sub  = make_text_overlay(lines_sub)

    for i in range(n):
        t = i / n
        a_main = smoothstep(min(t * 3.5, 1))
        a_sub  = smoothstep(max(0, min((t - 0.28) * 3.5, 1)))

        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        canvas = composite_rgba(canvas, ov_main, alpha_mult=a_main)
        canvas = composite_rgba(canvas, ov_sub,  alpha_mult=a_sub)
        yield canvas


def scene_gas_collage(r1_gas_img, duration=8):
    """
    Scene 2: R1 gas collage slowly brightens with a subtitle.
    r1_gas_img: overview_gas.png from R1, already PIL RGB.
    """
    n = int(duration * FPS)
    # Recolour with plasma_r, fit to frame, add glow + vignette
    recolored = recolor_image(crop_margins(r1_gas_img), CMAP_GAS, p_lo=2, p_hi=90, invert=True, bg_thresh=20)
    base = fit_to_frame(recolored)
    base = add_glow(base, radius=12, intensity=0.35)
    base = add_vignette(base, strength=0.5)
    base_arr = np.array(base, dtype=np.float32)

    sub_ov = make_text_overlay([
        {"text": "R₁  —  30 galaxy clusters  ·  gas mass projection",
         "x": W//2, "y": int(H*0.055), "size": 26,
         "color_rgb": (255, 200, 80), "bold": False, "stroke_w": 1},
    ])

    for i in range(n):
        t = i / n
        bright = smoothstep(min(t * 2.5, 1))
        frame_arr = (base_arr * bright).clip(0, 255).astype(np.uint8)
        frame = Image.fromarray(frame_arr)
        alpha_sub = smoothstep(max(0, min((t - 0.5) * 4, 1)))
        frame = composite_rgba(frame, sub_ov, alpha_mult=alpha_sub)
        yield frame


def scene_selection_tour(overview_imgs, duration=30):
    """
    Scene 3: Cycle through all 7 groups, each shown as plasma_r gas collage
    with coloured group label.  4s hold + 0.3s crossfade per group.
    """
    ng = len(GROUP_ORDER)
    secs_per_group = duration / ng
    frames_hold  = int(secs_per_group * 0.75 * FPS)
    frames_xfade = int(secs_per_group * 0.25 * FPS)

    # Pre-process all group gas images
    group_base = {}
    group_ov   = {}
    for g in GROUP_ORDER:
        img = overview_imgs.get(g)
        if img is None:
            img = Image.new("RGB", (W, H), (0, 0, 0))
        # crop_margins removes matplotlib axis box spines; bg_thresh=20 catches residuals
        reco = recolor_image(crop_margins(img), CMAP_GAS, p_lo=2, p_hi=90, invert=True, bg_thresh=20)
        base = fit_to_frame(reco)
        base = add_glow(base, radius=10, intensity=0.3)
        base = add_vignette(base, strength=0.45)
        group_base[g] = base

        gc = GROUP_COLORS_RGB[g]
        bar_ov = make_separator_bar(gc, 0.30, 0.70, 0.125, thickness=3)
        lines = [
            {"text": GROUP_TITLES[g], "x": W//2, "y": int(H*0.07),
             "size": 30, "color_rgb": gc, "bold": True, "stroke_w": 2},
            {"text": "Gas Mass Projection  ·  30 halos",
             "x": W//2, "y": int(H*0.93), "size": 18,
             "color_rgb": (160,160,160), "bold": False, "stroke_w": 1},
        ]
        txt_ov = make_text_overlay(lines)
        group_ov[g] = (txt_ov, bar_ov)

    for gi, g in enumerate(GROUP_ORDER):
        ng_next = GROUP_ORDER[(gi+1) % len(GROUP_ORDER)]
        base_cur  = group_base[g]
        base_next = group_base[ng_next]
        txt_ov, bar_ov = group_ov[g]

        # Hold frames
        for j in range(frames_hold):
            a_label = smoothstep(min(j / max(frames_hold * 0.35, 1), 1))
            frame = composite_rgba(base_cur, txt_ov, alpha_mult=a_label)
            frame = composite_rgba(frame, bar_ov, alpha_mult=a_label * 0.9)
            yield frame

        # Crossfade to next
        for j in range(frames_xfade):
            t_x = smoothstep(j / max(frames_xfade, 1))
            frame = blend(base_cur, base_next, t_x)
            a_label = 1 - smoothstep(t_x * 2)
            frame = composite_rgba(frame, txt_ov, alpha_mult=max(0, a_label))
            frame = composite_rgba(frame, bar_ov,  alpha_mult=max(0, a_label * 0.9))
            yield frame


def scene_field_crossfade(render_sets):
    """
    Scene 4: For each halo in render_sets (list of {0:PIL,1:PIL,2:PIL,3:PIL}),
    cycle DM→Stars→Gas→GasTemp with smooth crossfades.
    Per halo: 1.8s hold × 4 fields + 0.8s crossfade × 4 = ~10s each.
    """
    n_halos = len(render_sets)
    hold_sec  = 1.8
    xfade_sec = 0.8
    halo_fade_sec = 0.9

    frames_hold  = int(hold_sec  * FPS)
    frames_xfade = int(xfade_sec * FPS)
    frames_hfade = int(halo_fade_sec * FPS)

    for hi, rset in enumerate(render_sets):
        # Prepare fitted field images
        field_imgs = [fit_to_frame(rset[fi]) for fi in range(4)]
        field_imgs = [add_glow(img, 12, 0.3) for img in field_imgs]
        field_imgs = [add_vignette(img, 0.4) for img in field_imgs]

        # Pre-render label overlays for each field
        label_ovs = []
        for fi in range(4):
            ac = FIELD_ACCENT_RGB[FIELD_CMAPS[fi]]
            ov = make_text_overlay([
                {"text": FIELD_LABELS[fi],
                 "x": int(W*0.07), "y": int(H*0.065), "size": 40,
                 "color_rgb": ac, "bold": True, "stroke_w": 3,
                 "ha": "left", "va": "center"},
                {"text": f"Halo {hi+1} of {n_halos}",
                 "x": int(W*0.07), "y": int(H*0.92), "size": 18,
                 "color_rgb": (160,160,160), "bold": False, "stroke_w": 1,
                 "ha": "left"},
            ])
            label_ovs.append(ov)

        for fi in range(4):
            cur_img  = field_imgs[fi]
            next_img = field_imgs[(fi + 1) % 4]
            cur_ov   = label_ovs[fi]

            # Hold frames with slow zoom
            for j in range(frames_hold):
                t  = j / max(frames_hold, 1)
                zm = 1.0 + 0.04 * smoothstep(t)
                img = zoom_image(cur_img, zm)
                a_lbl = smoothstep(min(j / max(frames_hold * 0.4, 1), 1))
                frame = composite_rgba(img, cur_ov, alpha_mult=a_lbl)
                yield frame

            # Crossfade to next field
            for j in range(frames_xfade):
                t = smoothstep(j / max(frames_xfade, 1))
                frame = blend(cur_img, next_img, t)
                a_lbl = 1 - smoothstep(t * 1.5)
                frame = composite_rgba(frame, cur_ov, alpha_mult=max(0, a_lbl))
                yield frame

        # Fade to black, then fade in next halo's DM (if not last)
        if hi < n_halos - 1:
            next_dm = fit_to_frame(render_sets[hi+1][0])
            next_dm = add_glow(next_dm, 12, 0.3)
            next_dm = add_vignette(next_dm, 0.4)
            black = Image.new("RGB", (W, H), (0,0,0))
            for j in range(frames_hfade):
                t = j / max(frames_hfade, 1)
                if t < 0.5:
                    frame = blend(field_imgs[3], black, smoothstep(t * 2))
                else:
                    frame = blend(black, next_dm, smoothstep((t - 0.5) * 2))
                yield frame


def scene_finale(finale_img, duration=10):
    """
    Scene 5: 4-field multifield row of most massive cluster with slow zoom.
    finale_img: 1×4 row PIL Image (DM|Stars|Gas|GasTemp).
    """
    n = int(duration * FPS)
    base = fit_to_frame(finale_img)
    base = add_glow(base, 14, 0.35)
    base = add_vignette(base, 0.4)
    base_arr = np.array(base, dtype=np.float32)

    title_ov = make_text_overlay([
        {"text": "Most Massive Cluster  ·  Dark Matter  |  Stars  |  Gas  |  Gas Temperature",
         "x": W//2, "y": int(H*0.04), "size": 22,
         "color_rgb": (200, 215, 255), "bold": False, "stroke_w": 1},
    ])

    for i in range(n):
        t = i / n
        # Fade in [0-0.25], hold, fade out [0.85-1.0]
        if t < 0.2:
            fade = smoothstep(t / 0.2)
        elif t > 0.85:
            fade = smoothstep(1 - (t - 0.85) / 0.15)
        else:
            fade = 1.0

        zm = 1.0 + 0.12 * smoothstep(t)
        img = zoom_image(Image.fromarray(base_arr.clip(0,255).astype(np.uint8)), zm)
        frame_arr = (np.array(img, dtype=np.float32) * fade).clip(0,255).astype(np.uint8)
        frame = Image.fromarray(frame_arr)
        a_txt = fade * smoothstep(max(0, min((t - 0.1) * 5, 1)))
        frame = composite_rgba(frame, title_ov, alpha_mult=a_txt)
        yield frame


def scene_credits(duration=4):
    """Scene 6: Credits fade in and out."""
    n = int(duration * FPS)
    lines = [
        {"text": "HACC Simulation  ·  Frontier-E",
         "x": W//2, "y": int(H*0.46), "size": 32,
         "color_rgb": (255,255,255), "bold": True, "stroke_w": 1},
        {"text": "Cluster Relaxation Criteria Analysis  ·  Phases 1–6",
         "x": W//2, "y": int(H*0.54), "size": 22,
         "color_rgb": (170, 200, 255), "bold": False, "stroke_w": 1},
        {"text": "OpenCosmo  ·  Claude Code  ·  2025",
         "x": W//2, "y": int(H*0.62), "size": 18,
         "color_rgb": (120, 160, 200), "bold": False, "stroke_w": 1},
    ]
    ov = make_text_overlay(lines)

    for i in range(n):
        t = i / n
        if t < 0.3:
            a = smoothstep(t / 0.3)
        elif t > 0.7:
            a = smoothstep(1 - (t - 0.7) / 0.3)
        else:
            a = 1.0
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        frame = composite_rgba(canvas, ov, alpha_mult=a)
        yield frame


# ─────────────────────────────────────────────────────────────────────────────
# ── FRAME I/O & ENCODING ──────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

_frame_counter = [0]


def save_scene(gen, label):
    t0 = time.time()
    count = 0
    for frame in gen:
        path = os.path.join(FRAMES_DIR, f"frame_{_frame_counter[0]:06d}.png")
        frame.save(path, compress_level=1)
        _frame_counter[0] += 1
        count += 1
        if count % 100 == 0:
            print(f"    [{label}] {count} frames  ({time.time()-t0:.1f}s)")
    print(f"  ✓ {label}: {count} frames  ({time.time()-t0:.1f}s total)")


def encode_video(frames_dir, output_path):
    """Encode PNG frame sequence to MP4 with ffmpeg."""
    print(f"\n=== Encoding video → {output_path} ===")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%06d.png"),
        "-c:v", "libx264",
        "-crf", "16",
        "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}",
        output_path,
    ]
    print("  " + " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        mb = os.path.getsize(output_path) / 1e6
        print(f"  ✓ Done: {output_path}  ({mb:.1f} MB)")
    else:
        print(f"  ERROR:\n{result.stderr[-800:]}")


# ─────────────────────────────────────────────────────────────────────────────
# ── MAIN ──────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  HACC Cluster Zoo Video Generator")
    print("=" * 65)

    # ── Phase 1: Render individual field images ────────────────────────────────
    print("\n── Phase 1: Individual field renders (opencosmo) ──")
    # Pick one halo each from 3 contrasting groups
    crossfade_groups = [
        ("R1",       FILE_MAP["R1"]),
        ("R1_notR2", FILE_MAP["R1_notR2"]),
        ("R1_andR2", FILE_MAP["R1_andR2"]),
    ]
    render_sets = []
    for gname, fname in crossfade_groups:
        hdf5 = os.path.join(PARTICLE_DIR, fname)
        top  = get_top_halos(hdf5, n=1)
        if not top:
            continue
        mass, tag = top[0]
        print(f"  {gname}: tag={tag}, M={mass:.3e} Msun/h")
        rset = {}
        for fi in range(4):
            out = os.path.join(RENDERS_DIR, f"{gname}_tag{tag}_f{fi}.png")
            rset[fi] = render_field_image(hdf5, tag, fi, out, width=4.5)
        render_sets.append(rset)

    # Render 4-field row for finale (most massive R1 halo)
    r1_top = get_top_halos(os.path.join(PARTICLE_DIR, FILE_MAP["R1"]), n=1)
    finale_tag = r1_top[0][1]
    finale_path = os.path.join(RENDERS_DIR, f"R1_tag{finale_tag}_4field_row.png")
    finale_img = render_multifield_row(
        os.path.join(PARTICLE_DIR, FILE_MAP["R1"]),
        finale_tag, finale_path
    )

    # ── Phase 2: Load overview images ─────────────────────────────────────────
    print("\n── Phase 2: Loading overview gas images ──")
    overview_imgs = {}
    for g in GROUP_ORDER:
        p = os.path.join(HALO_VIZ_DIR, g, "overview_gas.png")
        if os.path.exists(p):
            overview_imgs[g] = Image.open(p).convert("RGB")
            print(f"  {g}: {overview_imgs[g].size}")
        else:
            print(f"  WARNING: {p} not found — using blank")
            overview_imgs[g] = Image.new("RGB", (3630, 3060), (0,0,0))

    # ── Phase 3: Generate all frames ──────────────────────────────────────────
    print("\n── Phase 3: Frame generation ──")
    if os.path.exists(FRAMES_DIR):
        shutil.rmtree(FRAMES_DIR)
    os.makedirs(FRAMES_DIR)
    _frame_counter[0] = 0

    print("  Scene 1: Title …")
    save_scene(scene_title(duration=5), "title")

    print("  Scene 2: Gas collage …")
    save_scene(scene_gas_collage(overview_imgs["R1"], duration=8), "collage")

    print("  Scene 3: Selection tour …")
    save_scene(scene_selection_tour(overview_imgs, duration=30), "selection")

    print("  Scene 4: Field crossfade …")
    save_scene(scene_field_crossfade(render_sets), "crossfade")

    print("  Scene 5: 4-field finale …")
    save_scene(scene_finale(finale_img, duration=10), "finale")

    print("  Scene 6: Credits …")
    save_scene(scene_credits(duration=4), "credits")

    total = _frame_counter[0]
    print(f"\n  Total frames: {total}  (~{total/FPS:.0f} seconds)")

    # ── Phase 4: Encode ────────────────────────────────────────────────────────
    encode_video(FRAMES_DIR, OUTPUT_VIDEO)
    print(f"\n  Video: {OUTPUT_VIDEO}")
    print("=" * 65)


if __name__ == "__main__":
    main()
