"""
video_utils.py — Shared utilities for HACC cluster visualization videos.

Canonical color palette (matches multifield_4field_random6_massive.png):
  Dark Matter   "pink"
  Stars         "gist_yarg_r"
  Gas           "plasma_r"
  Gas Temp      "rainbow_r"

Usage:
    from video_utils import (
        W, H, FPS, CMAP_GAS, FIELD_CMAPS, FILE_MAP, GROUP_ORDER,
        smoothstep, blend, fit_to_frame, composite_rgba,
        make_text_overlay, render_field_image, encode_video, ...
    )
"""

import os
import subprocess
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from PIL import Image, ImageDraw, ImageFilter

import opencosmo as oc                             # type: ignore
from opencosmo.analysis import halo_projection_array  # type: ignore

# ── Absolute paths ─────────────────────────────────────────────────────────────
EXPERIMENT_DIR = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/runs/research_20260218_105441"
PARTICLE_DIR   = "/data/a/cpac/nramachandra/Projects/AmSC/particle_data"
HALO_VIZ_DIR   = os.path.join(EXPERIMENT_DIR, "halo_viz")
VIDEO_V2_DIR   = os.path.join(EXPERIMENT_DIR, "video_v2")
RENDERS_DIR    = os.path.join(VIDEO_V2_DIR, "renders")

os.makedirs(RENDERS_DIR, exist_ok=True)

# ── Video parameters ───────────────────────────────────────────────────────────
FPS    = 24
W, H   = 1920, 1080

# ── Canonical color palette ────────────────────────────────────────────────────
CMAP_DM    = "pink"
CMAP_STARS = "gist_yarg_r"
CMAP_GAS   = "plasma_r"
CMAP_TEMP  = "rainbow_r"


FIELD_CMAPS  = [CMAP_DM,               CMAP_STARS,          CMAP_GAS,            CMAP_TEMP]
FIELD_LABELS = ["Dark Matter",         "Stars",             "Gas",               "Gas Temperature"]
FIELD_TYPES  = [("dm",  "particle_mass"), ("star","particle_mass"),
                ("gas", "particle_mass"), ("gas",  "temperature")]

# Accent colour for each field (used in text overlays, separators, …)
FIELD_ACCENT_RGB = {
    CMAP_DM:    (255, 180, 200),    # warm pink
    CMAP_STARS: (230, 230, 230),    # near-white
    CMAP_GAS:   (255, 200,  60),    # plasma gold
    CMAP_TEMP:  ( 60, 210, 255),    # rainbow cyan
}

# ── Group definitions ──────────────────────────────────────────────────────────
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

GROUP_SHORT_LABELS = {
    "R1":       "R₁",
    "R1_andR2": "R₁∩R₂",
    "R1_andR3": "R₁∩R₃",
    "R1_andR4": "R₁∩R₄",
    "R1_notR2": "R₁\\R₂",
    "R1_notR3": "R₁\\R₃",
    "R1_notR4": "R₁\\R₄",
}

# ── Image processing utilities ─────────────────────────────────────────────────

def smoothstep(t, power=2):
    """Smooth easing: maps [0, 1] → [0, 1] with zero derivative at ends."""
    t = float(np.clip(t, 0, 1))
    if power == 2:
        return t * t * (3 - 2 * t)
    return t**power / (t**power + (1 - t)**power)


def recolor_image(pil_img, cmap_name, p_lo=2, p_hi=90,
                  invert=False, bg_thresh=None):
    """
    Convert an image to grayscale and apply a matplotlib colormap.

    Parameters
    ----------
    pil_img   : PIL Image (any mode)
    cmap_name : matplotlib colormap name
    p_lo/p_hi : Percentile clip range for normalization (on non-background pixels)
    invert    : If True, invert the normalized value before applying the colormap.
                Use invert=True with plasma_r to match opencosmo's rendering
                convention (dense = yellow).
    bg_thresh : Pixels at or below this gray value are forced to pure black.
                Auto-estimated from the image if None.  Set to ~20 to mask
                faint matplotlib figure borders.
    """
    gray = np.array(pil_img.convert("L"), dtype=np.float32)
    if bg_thresh is None:
        bg_thresh = max(3.0, float(np.percentile(gray, 3)) + 1.0)
    bg_mask = gray <= bg_thresh
    nonzero = gray[~bg_mask]
    if len(nonzero) == 0:
        return Image.fromarray(np.zeros((*gray.shape[:2], 3), np.uint8))
    lo = np.percentile(nonzero, p_lo)
    hi = np.percentile(nonzero, p_hi)
    if hi <= lo:
        hi = lo + 1.0
    norm = np.clip((gray - lo) / (hi - lo), 0, 1)
    if invert:
        norm = 1.0 - norm
    cmap = plt.get_cmap(cmap_name)
    rgb  = (cmap(norm)[:, :, :3] * 255).astype(np.uint8)
    rgb[bg_mask] = 0
    return Image.fromarray(rgb)


def fit_to_frame(pil_img, fw=W, fh=H):
    """Scale image to fit (fw × fh) preserving aspect ratio; black bars fill rest."""
    aspect = pil_img.width / pil_img.height
    target = fw / fh
    if aspect > target:
        nw, nh = fw, int(fw / aspect)
    else:
        nw, nh = int(fh * aspect), fh
    resized = pil_img.resize((nw, nh), Image.LANCZOS)
    canvas  = Image.new("RGB", (fw, fh), (0, 0, 0))
    canvas.paste(resized, ((fw - nw) // 2, (fh - nh) // 2))
    return canvas


def zoom_image(pil_img, zoom=1.0, cx_frac=0.5, cy_frac=0.5):
    """Zoom into image. zoom > 1 magnifies; cx/cy_frac = center (0–1)."""
    if zoom <= 1.001:
        return pil_img
    iw, ih = pil_img.size
    nw, nh = int(iw / zoom), int(ih / zoom)
    x0 = max(0, min(int(iw * cx_frac) - nw // 2, iw - nw))
    y0 = max(0, min(int(ih * cy_frac) - nh // 2, ih - nh))
    return pil_img.crop((x0, y0, x0 + nw, y0 + nh)).resize((iw, ih), Image.LANCZOS)


def blend(img1, img2, alpha):
    """Linear blend. alpha=0 → img1; alpha=1 → img2."""
    alpha = float(np.clip(alpha, 0, 1))
    a1 = np.array(img1.convert("RGB"), dtype=np.float32)
    a2 = np.array(img2.convert("RGB"), dtype=np.float32)
    return Image.fromarray((a1 * (1 - alpha) + a2 * alpha).clip(0, 255).astype(np.uint8))


def add_glow(pil_img, radius=15, intensity=0.4):
    """Additive glow: blend original with Gaussian-blurred version."""
    blurred = pil_img.filter(ImageFilter.GaussianBlur(radius))
    a = np.array(pil_img, dtype=np.float32)
    b = np.array(blurred, dtype=np.float32)
    return Image.fromarray(np.clip(a + b * intensity, 0, 255).astype(np.uint8))


def crop_margins(pil_img, margin_frac=0.025):
    """Remove a fractional margin on all sides (strips matplotlib axis borders)."""
    w, h = pil_img.size
    mx, my = int(w * margin_frac), int(h * margin_frac)
    return pil_img.crop((mx, my, w - mx, h - my))


def add_vignette(pil_img, strength=0.55):
    """Darken the image edges with a radial gradient."""
    arr  = np.array(pil_img, dtype=np.float32)
    h, w = arr.shape[:2]
    y, x = np.ogrid[:h, :w]
    r    = np.sqrt(((x - w/2) / (w/2))**2 + ((y - h/2) / (h/2))**2)
    mask = 1 - np.clip(r * strength, 0, 1)
    return Image.fromarray((arr * mask[:, :, None]).clip(0, 255).astype(np.uint8))


def composite_rgba(base_rgb, overlay_rgba, alpha_mult=1.0):
    """Alpha-composite an RGBA PIL overlay onto an RGB base image."""
    base = np.array(base_rgb.convert("RGB"),  dtype=np.float32)
    ov   = np.array(overlay_rgba.convert("RGBA"), dtype=np.float32)
    mask = ov[:, :, 3:4] / 255.0 * float(np.clip(alpha_mult, 0, 1))
    return Image.fromarray((base * (1 - mask) + ov[:, :, :3] * mask).clip(0, 255).astype(np.uint8))


# ── Text / overlay utilities ──────────────────────────────────────────────────

def make_text_overlay(lines, fw=W, fh=H):
    """
    Render a list of text items as an RGBA PIL Image (transparent background).

    Each item in *lines* is a dict with keys:
      text       : str
      x, y       : int  pixel position (y measured from top)
      size       : float  font size in points
      color_rgb  : (r, g, b)  0–255 each
      bold       : bool  (default True)
      alpha      : float  0–1  (default 1.0)
      stroke_w   : int  outline width (default 2)
      ha         : 'left' | 'center' | 'right'  (default 'center')
      va         : 'top'  | 'center' | 'bottom' (default 'center')
    """
    fig, ax = plt.subplots(figsize=(fw / 100, fh / 100))
    fig.patch.set_facecolor((0, 0, 0, 0))
    fig.patch.set_alpha(0.0)
    ax.set_position([0, 0, 1, 1])
    ax.set_xlim(0, fw)
    ax.set_ylim(0, fh)
    ax.axis("off")
    ax.set_facecolor((0, 0, 0, 0))

    for L in lines:
        r, g, b = L.get("color_rgb", (255, 255, 255))
        a       = L.get("alpha", 1.0)
        fw_text = "bold" if L.get("bold", True) else "normal"
        sw      = L.get("stroke_w", 2)
        ax.text(
            L["x"], fh - L["y"], L["text"],
            ha=L.get("ha", "center"),
            va=L.get("va", "center"),
            fontsize=L["size"],
            fontweight=fw_text,
            color=(r / 255, g / 255, b / 255, a),
            path_effects=[pe.withStroke(linewidth=sw, foreground="black")],
        )

    fig.canvas.draw()
    buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
    rw, rh = fig.canvas.get_width_height()
    arr = buf.reshape(rh, rw, 4).copy()
    plt.close(fig)
    return Image.fromarray(arr, "RGBA")


def make_separator_bar(color_rgb, x0_frac, x1_frac, y_frac,
                        fw=W, fh=H, thickness=4):
    """Draw a thin horizontal colour bar as an RGBA overlay."""
    overlay = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    y  = int(fh * y_frac)
    x0 = int(fw * x0_frac)
    x1 = int(fw * x1_frac)
    r, g, b = color_rgb
    draw.rectangle([x0, y - thickness // 2, x1, y + thickness // 2],
                   fill=(r, g, b, 220))
    return overlay


# ── OpenCosmo render helpers ──────────────────────────────────────────────────

def get_top_halos(hdf5_path, n=4):
    """
    Return [(mass, unique_tag), …] for the top-n halos by FoF mass
    in an opencosmo particle/properties HDF5 file.
    """
    data = oc.open(hdf5_path)
    info = []
    for halo in data.halos():
        props = halo["halo_properties"]
        tag   = int(props["unique_tag"])
        m     = props["fof_halo_mass"]
        mass  = float(m.value) if hasattr(m, "value") else float(m)
        info.append((mass, tag))
    info.sort(reverse=True)
    return info[:n]


def render_field_image(hdf5_path, tag, field_idx, out_path,
                       width=4.5, cache=True):
    """
    Render one field for one halo using halo_projection_array.
    Extracts the main projection axes (no colorbar / figure margins).

    Parameters
    ----------
    hdf5_path : Path to opencosmo particle HDF5 file
    tag       : Halo unique_tag
    field_idx : 0=DM  1=Stars  2=Gas  3=Gas Temperature
    out_path  : Where to save the PNG
    width     : Projection half-width in units of R_halo
    cache     : If True, skip rendering when out_path already exists

    Returns
    -------
    PIL RGB Image (square, projection axes only)
    """
    if cache and os.path.exists(out_path):
        print(f"    [cache] {os.path.basename(out_path)}")
        return Image.open(out_path).convert("RGB")

    print(f"    Rendering {FIELD_LABELS[field_idx]} for tag {tag} …")
    t0   = time.time()
    data = oc.open(hdf5_path)

    halo_ids = np.array([[tag]])
    params   = {
        "fields": ([FIELD_TYPES[field_idx]],),
        "labels": ([FIELD_LABELS[field_idx]],),
        "cmaps":  ([FIELD_CMAPS[field_idx]],),
    }
    fig = halo_projection_array(halo_ids, data, params=params, width=width)
    fig.patch.set_facecolor("black")
    fig.set_size_inches(12, 12)
    fig.canvas.draw()

    # Locate the main projection axes (largest area, avoids colorbar axes)
    cands   = [ax for ax in fig.axes if ax.get_position().width > 0.08]
    main_ax = max(cands, key=lambda ax: ax.get_position().width * ax.get_position().height)
    pos     = main_ax.get_position()

    buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
    rw, rh = fig.canvas.get_width_height()
    arr     = buf.reshape(rh, rw, 4)[:, :, :3].copy()

    x0, x1 = max(0, int(pos.x0 * rw)), min(rw, int(pos.x1 * rw))
    y0, y1 = max(0, int((1 - pos.y1) * rh)), min(rh, int((1 - pos.y0) * rh))
    cropped = arr[y0:y1, x0:x1]
    plt.close(fig)

    img = Image.fromarray(cropped)
    img.save(out_path)
    print(f"      {cropped.shape[1]}×{cropped.shape[0]} px  ({time.time() - t0:.1f} s)")
    return img


def render_multifield_row(hdf5_path, tag, out_path, cache=True):
    """
    Render a 1×4 multifield row (DM | Stars | Gas | Gas Temperature)
    for one halo.  Returns PIL RGB Image.
    """
    if cache and os.path.exists(out_path):
        print(f"    [cache] {os.path.basename(out_path)}")
        return Image.open(out_path).convert("RGB")

    print(f"    Rendering 4-field row for tag {tag} …")
    t0   = time.time()
    data = oc.open(hdf5_path)

    halo_ids = np.array([[tag, tag, tag, tag]])
    params   = {
        "fields": (FIELD_TYPES,),
        "labels": (FIELD_LABELS,),
        "cmaps":  (FIELD_CMAPS,),
    }
    fig = halo_projection_array(halo_ids, data, params=params, length_scale="all left")
    fig.patch.set_facecolor("black")
    fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    print(f"      saved  ({time.time() - t0:.1f} s)")
    return Image.open(out_path).convert("RGB")


# ── Frame I/O & video encoding ────────────────────────────────────────────────

def save_frames(gen, frames_dir, start_idx=0, label="scene"):
    """
    Write frames from a generator to *frames_dir*.
    Each frame is saved as frame_NNNNNN.png (zero-padded).

    Returns (next_frame_index, total_frames_written).
    """
    t0    = time.time()
    count = 0
    idx   = start_idx
    for frame in gen:
        frame.save(os.path.join(frames_dir, f"frame_{idx:06d}.png"),
                   compress_level=1)
        idx   += 1
        count += 1
        if count % 100 == 0:
            print(f"    [{label}] {count} frames  ({time.time() - t0:.1f} s)")
    print(f"  ✓ {label}: {count} frames  ({time.time() - t0:.1f} s total)")
    return idx, count


def encode_video(frames_dir, output_path, fps=FPS, w=W, h=H, crf=16):
    """Encode a PNG frame sequence to H264 MP4 via ffmpeg."""
    print(f"\n=== Encoding → {output_path} ===")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "frame_%06d.png"),
        "-c:v", "libx264",
        "-crf",    str(crf),
        "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={w}:{h}",
        output_path,
    ]
    print("  " + " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        mb = os.path.getsize(output_path) / 1e6
        print(f"  ✓ {output_path}  ({mb:.1f} MB)")
    else:
        print(f"  ERROR:\n{result.stderr[-800:]}")
