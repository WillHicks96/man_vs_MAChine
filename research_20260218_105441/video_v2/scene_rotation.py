"""
scene_rotation.py — Custom particle-projection rotation animation.

Renders a halo rotating around the line of sight by directly computing
2D weighted histograms of the rotated particle positions — no call to
halo_projection_array is needed.  This gives full control over the
projection axis.

Functions
---------
load_halo_particles(hdf5_path, tag)
    Extract DM, gas, and star particle positions/masses from opencosmo.

make_projection_frame(x, y, z, weights, theta, phi, ...)
    Rotate and project particles into a 2D histogram image.

scene_halo_rotation(hdf5_path, tag, duration, ...)
    Generator: yield frames of a single field rotating ~360°.

scene_halo_rotation_multifield(hdf5_path, tag, ...)
    Generator: cycle through DM → Gas → Gas Temperature, each rotating.

Usage example
-------------
    from scene_rotation import scene_halo_rotation

    for frame in scene_halo_rotation("R1.hdf5", tag=12345, duration=12,
                                      particle_type="gas"):
        ...

Standalone:
    python scene_rotation.py
    → saves preview_rotation.png (single frame, gas projection)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from video_utils import (
    W, H, FPS,
    CMAP_GAS, CMAP_DM, CMAP_TEMP, CMAP_STARS,
    FIELD_ACCENT_RGB,
    PARTICLE_DIR, RENDERS_DIR, FILE_MAP,
    smoothstep, fit_to_frame, add_glow, add_vignette, composite_rgba,
    make_text_overlay, get_top_halos,
)
from PIL import Image, ImageDraw
import numpy as np

import opencosmo as oc   # type: ignore


# ── Particle extraction ────────────────────────────────────────────────────────

def _get_col(dataset, col):
    """
    Retrieve a column from an opencosmo Dataset (particle type).
    Tries dataset.data[col] first; falls back to dataset[col].
    """
    try:
        return np.array(dataset.data[col])
    except (AttributeError, KeyError, Exception):
        return np.array(dataset[col])


def load_halo_particles(hdf5_path, tag,
                         particle_types=("dm", "gas", "star")):
    """
    Load particle positions and masses for a specific halo.

    Iterates the opencosmo StructureCollection, finds the halo with
    unique_tag == tag, and extracts particle arrays.

    Parameters
    ----------
    hdf5_path      : Path to opencosmo particle HDF5 file (e.g. R1.hdf5)
    tag            : Halo unique_tag (int)
    particle_types : Which particle types to load

    Returns
    -------
    dict keyed by particle type ("dm", "gas", "star").
    Each value is a dict:
        "x", "y", "z"   — positions relative to halo FoF centre
        "mass"           — particle masses
        "temperature"    — (gas only, if available)

    Notes
    -----
    Positions are returned in the native units of the file (comoving Mpc/h).
    For projection purposes only the relative positions matter.
    """
    data       = oc.open(hdf5_path)
    pt_keys    = [f"{pt}_particles" for pt in particle_types]
    result     = {}
    tag_int    = int(tag)
    found      = False

    # Try to pre-filter for efficiency; fall back to iterating all halos
    try:
        filtered = data.filter(oc.col("unique_tag") == tag_int)
    except Exception:
        filtered = data

    for halo in filtered.halos(pt_keys):
        props = halo["halo_properties"]
        htag  = int(props["unique_tag"])
        if htag != tag_int:
            continue
        found = True

        # Halo centre: try catalog first, then compute from particles.
        # The particle HDF5 files often omit fof_halo_center_x/y/z, so we
        # cannot rely on the catalog value being present.
        catalog_cx = catalog_cy = catalog_cz = None
        try:
            catalog_cx = float(props["fof_halo_center_x"])
            catalog_cy = float(props["fof_halo_center_y"])
            catalog_cz = float(props["fof_halo_center_z"])
            print(f"    Centre from catalog: ({catalog_cx:.4f}, {catalog_cy:.4f}, {catalog_cz:.4f})")
        except (KeyError, Exception):
            print("    fof_halo_center_x/y/z not in halo_properties — will compute from particles")

        # Track the centre used so all particle types share the same origin
        shared_cx = shared_cy = shared_cz = None

        for pt, pt_key in zip(particle_types, pt_keys):
            try:
                particles = halo[pt_key]
                x_raw = _get_col(particles, "x")
                y_raw = _get_col(particles, "y")
                z_raw = _get_col(particles, "z")
                m = _get_col(particles, "mass")

                # Determine centre on the first particle type loaded
                if shared_cx is None:
                    if catalog_cx is not None:
                        shared_cx, shared_cy, shared_cz = catalog_cx, catalog_cy, catalog_cz
                    else:
                        # Mass-weighted centre of mass from particles
                        total_m = float(m.sum())
                        if total_m > 0:
                            shared_cx = float((x_raw * m).sum() / total_m)
                            shared_cy = float((y_raw * m).sum() / total_m)
                            shared_cz = float((z_raw * m).sum() / total_m)
                        else:
                            shared_cx = float(np.median(x_raw))
                            shared_cy = float(np.median(y_raw))
                            shared_cz = float(np.median(z_raw))
                        print(f"    Centre from particle CoM: ({shared_cx:.4f}, {shared_cy:.4f}, {shared_cz:.4f})")

                cx, cy, cz = shared_cx, shared_cy, shared_cz
                x = x_raw - cx
                y = y_raw - cy
                z = z_raw - cz

                entry = {"x": x, "y": y, "z": z, "mass": m}

                if pt == "gas":
                    try:
                        entry["temperature"] = _get_col(particles, "temperature")
                    except Exception:
                        pass   # temperature not available

                result[pt] = entry
                print(f"    {pt}: {len(x):,} particles loaded")
            except (KeyError, Exception) as exc:
                print(f"    WARNING: {pt_key} unavailable: {exc}")

        break   # only the first match

    if not found:
        print(f"  WARNING: tag {tag} not found in {hdf5_path}")

    return result


# ── Projection ────────────────────────────────────────────────────────────────

def make_projection_frame(x, y, z, weights,
                           theta, phi=0.0,
                           n_bins=1024,
                           cmap_name="plasma_r",
                           invert_cmap=True,
                           p_lo=3, p_hi=99.2,
                           extent_percentile=99.5,
                           size_px=None):
    """
    Rotate particles and build a 2D weighted histogram projection.

    Rotation
    --------
    theta : azimuthal angle around the z-axis (radians)
    phi   : elevation tilt around the (rotated) x-axis (radians)
            phi=0  → face-on (xy-projection)
            phi=π/2 → edge-on (xz-projection)

    Parameters
    ----------
    x, y, z    : Particle position arrays (centred on halo)
    weights    : Particle weight array (mass or mass-weighted temperature)
    n_bins     : 2D histogram resolution
    cmap_name  : Matplotlib colormap name
    invert_cmap: Invert the colormap normalisation (set True for plasma_r
                 to make dense regions appear yellow, matching opencosmo)
    p_lo/p_hi  : Percentile range for contrast normalisation
    size_px    : Output image size in pixels (square). Defaults to n_bins.

    Returns
    -------
    PIL RGB Image (size_px × size_px)
    """
    if size_px is None:
        size_px = n_bins

    # ── Rotation: azimuthal (around z) ────────────────────────────────────────
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    x1 = cos_t * x - sin_t * y
    y1 = sin_t * x + cos_t * y
    # z1 = z  (unchanged for pure azimuthal rotation)

    # ── Rotation: elevation (around rotated x-axis) ────────────────────────────
    if phi != 0.0:
        cos_p, sin_p = np.cos(phi), np.sin(phi)
        y2 = cos_p * y1 - sin_p * z
        # project onto (x1, y2)
        px_arr, py_arr = x1, y2
    else:
        px_arr, py_arr = x1, y1

    # ── Determine square spatial extent ───────────────────────────────────────
    r3d   = np.sqrt(x**2 + y**2 + z**2)
    r_max = float(np.percentile(r3d, extent_percentile))
    if r_max <= 0:
        r_max = 1.0

    # ── 2D weighted histogram ─────────────────────────────────────────────────
    H, _, _ = np.histogram2d(
        px_arr, py_arr, bins=n_bins,
        range=[[-r_max, r_max], [-r_max, r_max]],
        weights=weights,
    )
    H = H.T   # convention: rows = y, columns = x

    # ── Log stretch ───────────────────────────────────────────────────────────
    H = np.log1p(H)

    # ── Contrast normalisation ────────────────────────────────────────────────
    nonzero = H[H > 0]
    if len(nonzero) == 0:
        return Image.fromarray(np.zeros((size_px, size_px, 3), np.uint8))

    vmin = np.percentile(nonzero, p_lo)
    vmax = np.percentile(nonzero, p_hi)
    if vmax <= vmin:
        vmax = vmin + 1e-10

    norm = np.clip((H - vmin) / (vmax - vmin), 0, 1)
    if invert_cmap:
        norm = 1.0 - norm

    # ── Apply colormap ────────────────────────────────────────────────────────
    cmap = plt.get_cmap(cmap_name) if isinstance(cmap_name, str) else cmap_name
    rgb  = (cmap(norm)[:, :, :3] * 255).astype(np.uint8)
    rgb[H <= 0] = 0   # true black background

    img = Image.fromarray(rgb)
    if img.size[0] != size_px:
        img = img.resize((size_px, size_px), Image.LANCZOS)
    return img


import matplotlib.pyplot as plt   # needed inside make_projection_frame


# ── Scene generators ───────────────────────────────────────────────────────────

def scene_halo_rotation(hdf5_path, tag,
                         duration=12,
                         n_rotations=1,
                         particle_type="gas",
                         weight_field="mass",
                         phi_wobble=0.18,
                         cmap_name="plasma_r",
                         invert_cmap=True,
                         n_bins=1024,
                         fade_in_sec=0.7,
                         fade_out_sec=0.7,
                         label=None):
    """
    Yield frames of one halo rotating around its z-axis.

    A small elevation wobble (phi_wobble) gives a subtle 3-D feel.

    Parameters
    ----------
    hdf5_path      : Path to opencosmo particle HDF5 file
    tag            : Halo unique_tag
    duration       : Scene duration in seconds
    n_rotations    : Number of full 360° rotations
    particle_type  : "gas", "dm", or "star"
    weight_field   : "mass" (default) or "temperature" (for gas temp map)
    phi_wobble     : Amplitude of elevation wobble in radians (0 = flat rotation)
    cmap_name      : Matplotlib colormap
    invert_cmap    : Invert colormap normalization (True for plasma_r / rainbow_r)
    n_bins         : 2D histogram resolution (higher = sharper, slower)
    fade_in_sec    : Fade in from black
    fade_out_sec   : Fade to black at end (0 = no fade)
    label          : Optional text label shown at top-left

    Yields
    ------
    1920 × 1080 PIL RGB frames
    """
    from PIL import Image as _Image

    n_frames     = int(duration * FPS)
    frames_fin   = int(fade_in_sec  * FPS)
    frames_fout  = int(fade_out_sec * FPS)

    print(f"Loading particles for halo tag={tag}, type={particle_type} …")
    particles = load_halo_particles(hdf5_path, tag, particle_types=(particle_type,))

    if particle_type not in particles:
        print(f"  ERROR: {particle_type} particles not found — yielding black frames")
        black = _Image.new("RGB", (W, H), (0, 0, 0))
        for _ in range(n_frames):
            yield black
        return

    p  = particles[particle_type]
    x  = p["x"].astype(np.float32)
    y  = p["y"].astype(np.float32)
    z  = p["z"].astype(np.float32)

    if weight_field == "temperature" and "temperature" in p:
        weights = (p["mass"] * p["temperature"]).astype(np.float32)
    else:
        weights = p["mass"].astype(np.float32)

    print(f"  {len(x):,} particles.  Generating {n_frames} frames …")

    # Text overlay
    label_str = label or f"Halo rotation  ·  {particle_type.capitalize()}"
    label_ov  = make_text_overlay([
        {"text":  label_str,
         "x": int(W * 0.05), "y": int(H * 0.050), "size": 26,
         "color_rgb": FIELD_ACCENT_RGB.get(cmap_name, (230, 230, 230)),
         "bold": False, "stroke_w": 1, "ha": "left"},
    ])

    black = _Image.new("RGB", (W, H), (0, 0, 0))

    for i in range(n_frames):
        t     = i / n_frames
        theta = 2 * np.pi * n_rotations * t
        phi   = phi_wobble * np.sin(2 * np.pi * t)   # one full wobble per rotation

        # Fade envelope
        if i < frames_fin:
            fade = smoothstep(i / max(frames_fin, 1))
        elif i >= n_frames - frames_fout and frames_fout > 0:
            fade = smoothstep(1 - (i - (n_frames - frames_fout)) / max(frames_fout, 1))
        else:
            fade = 1.0

        proj  = make_projection_frame(x, y, z, weights, theta, phi,
                                       n_bins=n_bins, cmap_name=cmap_name,
                                       invert_cmap=invert_cmap)
        proj  = add_glow(proj, radius=9, intensity=0.28)
        frame = fit_to_frame(proj)
        frame = add_vignette(frame, strength=0.38)

        if fade < 1.0:
            frame = Image.fromarray(
                (np.array(frame, dtype=np.float32) * fade).clip(0, 255).astype(np.uint8)
            )
        frame = composite_rgba(frame, label_ov, alpha_mult=min(fade, 0.9))

        yield frame


def scene_halo_rotation_multifield(hdf5_path, tag,
                                    secs_per_field=10,
                                    n_rotations=1,
                                    phi_wobble=0.18,
                                    n_bins=1024):
    """
    Cycle through three field views (DM → Gas Mass → Gas Temperature),
    each doing a full rotation.

    Parameters
    ----------
    hdf5_path    : Path to opencosmo particle HDF5 file
    tag          : Halo unique_tag
    secs_per_field : Duration per field (seconds)
    n_rotations  : Full rotations per field
    phi_wobble   : Elevation wobble amplitude (radians)
    n_bins       : 2D histogram resolution

    Yields
    ------
    1920 × 1080 PIL RGB frames
    """
    fields_config = [
        # (particle_type, weight_field, cmap_name, invert_cmap, label)
        ("dm",  "mass",        "pink",      False, "Dark Matter  ·  Rotating"),
        ("gas", "mass",        "plasma_r",  True,  "Gas Mass  ·  Rotating"),
        ("gas", "temperature", "rainbow_r", True,  "Gas Temperature  ·  Rotating"),
    ]

    # Load all particle types once
    print(f"Loading all particle types for tag={tag} …")
    particles = load_halo_particles(hdf5_path, tag,
                                     particle_types=("dm", "gas", "star"))

    from PIL import Image as _Image

    for pt, wf, cmap, inv, lbl in fields_config:
        if pt not in particles:
            print(f"  Skipping {pt} (not available)")
            continue

        p = particles[pt]
        x = p["x"].astype(np.float32)
        y = p["y"].astype(np.float32)
        z = p["z"].astype(np.float32)

        if wf == "temperature" and "temperature" in p:
            weights = (p["mass"] * p["temperature"]).astype(np.float32)
        else:
            weights = p["mass"].astype(np.float32)

        n_frames   = int(secs_per_field * FPS)
        frames_fin = int(0.5 * FPS)
        frames_fout = int(0.5 * FPS)

        label_ov = make_text_overlay([
            {"text":  lbl,
             "x": int(W * 0.05), "y": int(H * 0.050), "size": 28,
             "color_rgb": FIELD_ACCENT_RGB.get(cmap, (230, 230, 230)),
             "bold": False, "stroke_w": 1, "ha": "left"},
        ])

        black = _Image.new("RGB", (W, H), (0, 0, 0))

        for i in range(n_frames):
            t     = i / n_frames
            theta = 2 * np.pi * n_rotations * t
            phi   = phi_wobble * np.sin(2 * np.pi * t)

            fade = 1.0
            if i < frames_fin:
                fade = smoothstep(i / max(frames_fin, 1))
            elif i >= n_frames - frames_fout:
                fade = smoothstep(1 - (i - (n_frames - frames_fout)) / max(frames_fout, 1))

            proj  = make_projection_frame(x, y, z, weights, theta, phi,
                                           n_bins=n_bins, cmap_name=cmap,
                                           invert_cmap=inv)
            proj  = add_glow(proj, 9, 0.28)
            frame = fit_to_frame(proj)
            frame = add_vignette(frame, 0.38)

            if fade < 1.0:
                frame = _Image.fromarray(
                    (np.array(frame, dtype=np.float32) * fade).clip(0, 255).astype(np.uint8)
                )
            frame = composite_rgba(frame, label_ov, alpha_mult=min(fade, 0.9))
            yield frame


def scene_halo_rotation_3d(hdf5_path, tag,
                            duration=15,
                            particle_type="gas",
                            weight_field="mass",
                            n_azimuthal=2,
                            phi_max=np.pi / 2,
                            cmap_name="plasma_r",
                            invert_cmap=True,
                            n_bins=1024,
                            fade_in_sec=0.8,
                            fade_out_sec=0.8,
                            label=None):
    """
    True 3D rotation: the viewing direction traces a sinusoidal path on a
    sphere so the viewer sees the halo from ALL angles — equatorial, polar,
    and every inclination in between.

    Trajectory
    ----------
    The line-of-sight direction is parametrised by:
        theta(t) = 2π × n_azimuthal × t        (azimuthal sweeps around z)
        phi(t)   = phi_max × sin(2π × t)       (elevation oscillates ±phi_max)

    With phi_max = π/2 (default):
        t = 0.00  → equatorial face-on view  (phi = 0)
        t = 0.25  → looking straight down at the top  (phi = +π/2)
        t = 0.50  → equatorial again, from opposite side
        t = 0.75  → looking straight up at the bottom (phi = -π/2)
        t = 1.00  → back to start

    This creates a "figure-8 on a sphere" path that truly shows every side.

    Parameters
    ----------
    hdf5_path    : Path to opencosmo particle HDF5 file
    tag          : Halo unique_tag
    duration     : Total duration in seconds
    particle_type: "gas", "dm", or "star"
    weight_field : "mass" or "temperature" (gas only)
    n_azimuthal  : Number of complete azimuthal sweeps (default 2)
    phi_max      : Maximum elevation angle (radians). π/2 = full polar view.
    cmap_name    : Matplotlib colormap
    invert_cmap  : Invert colormap normalisation (True for plasma_r)
    n_bins       : 2D histogram resolution
    fade_in_sec  : Fade in from black
    fade_out_sec : Fade to black at end
    label        : Optional text label in top-left

    Yields
    ------
    1920 × 1080 PIL RGB frames
    """
    from PIL import Image as _Image

    n_frames    = int(duration * FPS)
    frames_fin  = int(fade_in_sec  * FPS)
    frames_fout = int(fade_out_sec * FPS)

    print(f"Loading particles for 3D rotation  tag={tag}  type={particle_type} …")
    particles = load_halo_particles(hdf5_path, tag, particle_types=(particle_type,))

    if particle_type not in particles:
        print(f"  ERROR: {particle_type} not found — black frames")
        black = _Image.new("RGB", (W, H), (0, 0, 0))
        for _ in range(n_frames):
            yield black
        return

    p = particles[particle_type]
    x = p["x"].astype(np.float32)
    y = p["y"].astype(np.float32)
    z = p["z"].astype(np.float32)

    if weight_field == "temperature" and "temperature" in p:
        weights = (p["mass"] * p["temperature"]).astype(np.float32)
    else:
        weights = p["mass"].astype(np.float32)

    print(f"  {len(x):,} particles.  3D rotation: {n_azimuthal} sweeps, phi_max={np.degrees(phi_max):.0f}°")

    label_str = label or f"3D rotation  ·  {particle_type.capitalize()}"
    label_ov  = make_text_overlay([
        {"text":  label_str,
         "x": int(W * 0.05), "y": int(H * 0.050), "size": 26,
         "color_rgb": FIELD_ACCENT_RGB.get(cmap_name, (230, 230, 230)),
         "bold": False, "stroke_w": 1, "ha": "left"},
    ])

    black = _Image.new("RGB", (W, H), (0, 0, 0))

    for i in range(n_frames):
        t = i / n_frames

        # Sinusoidal path on the sphere:
        # - theta sweeps azimuthally (n_azimuthal full rounds)
        # - phi oscillates from 0 → +phi_max → 0 → -phi_max → 0
        theta = 2 * np.pi * n_azimuthal * t
        phi   = phi_max * np.sin(2 * np.pi * t)

        # Fade envelope
        if i < frames_fin:
            fade = smoothstep(i / max(frames_fin, 1))
        elif i >= n_frames - frames_fout and frames_fout > 0:
            fade = smoothstep(1 - (i - (n_frames - frames_fout)) / max(frames_fout, 1))
        else:
            fade = 1.0

        proj  = make_projection_frame(x, y, z, weights, theta, phi,
                                       n_bins=n_bins, cmap_name=cmap_name,
                                       invert_cmap=invert_cmap)
        proj  = add_glow(proj, radius=9, intensity=0.28)
        frame = fit_to_frame(proj)
        frame = add_vignette(frame, strength=0.38)

        if fade < 1.0:
            frame = _Image.fromarray(
                (np.array(frame, dtype=np.float32) * fade).clip(0, 255).astype(np.uint8)
            )
        frame = composite_rgba(frame, label_ov, alpha_mult=min(fade, 0.9))
        yield frame


def scene_dual_rotation_3d_synced(
        hdf5_path_1, tag_1,
        hdf5_path_2, tag_2,
        duration_1=10.0,
        duration_2=10.0,
        n_azimuthal=2,
        phi_max=np.pi / 2,
        n_bins=900,
        fade_in_sec=0.7,
        fade_mid_sec=0.7,
        fade_out_sec=0.7):
    """
    Two-pair synchronized 1×2 dual-panel 3D rotation.

    Pair 1  (duration_1 s):  Gas Mass   (left) | Dark Matter     (right)  —  halo_1
    Pair 2  (duration_2 s):  Stars      (left) | Gas Temperature  (right)  —  halo_2

    Both panels in each pair share the same theta/phi trajectory so the
    viewer can compare two fields from exactly the same viewing angle.

    Layout
    ------
    1920 × 1080 frame split vertically:
      Left panel:  x  0 – 957   (958 px wide)
      Separator:   x  958 – 961  (4 px, near-black)
      Right panel: x  962 – 1919 (958 px wide)

    The square particle projection (n_bins × n_bins) is centred in each
    panel both horizontally and vertically.

    Parameters
    ----------
    hdf5_path_1/2 : OpenCosmo HDF5 particle files for the two halos
    tag_1/2       : Halo unique_tags
    duration_1/2  : Duration of each pair (seconds)
    n_azimuthal   : Full azimuthal rotations during the pair
    phi_max       : Max elevation angle (π/2 = full polar view)
    n_bins        : Projection histogram resolution (≈ output pixels per side)
    fade_in_sec   : Fade-in at the very start (Pair 1 opening)
    fade_mid_sec  : Fade at the Pair 1 → Pair 2 boundary (out then in)
    fade_out_sec  : Fade-out at the very end (Pair 2 closing)

    Yields
    ------
    1920 × 1080 PIL RGB frames
    """
    SEP  = 4
    PW   = (W - SEP) // 2    # 958
    PROJ = n_bins             # square, fills most of the panel height

    # Absolute x-offsets for pasting the projection onto the canvas
    proj_x = [(PW - PROJ) // 2,               # left panel
               PW + SEP + (PW - PROJ) // 2]   # right panel
    proj_y = (H - PROJ) // 2                   # vertical centre

    # Per-pair configs:  (particle_type, weight_field, cmap, invert, label)
    PAIR_CONFIGS = [
        [  # Pair 1: Gas + DM
            ("gas",  "mass",        CMAP_GAS,   True,  "Gas Mass"),
            ("dm",   "mass",        CMAP_DM,    False, "Dark Matter"),
        ],
        [  # Pair 2: Stars + Gas Temperature
            ("star", "mass",        CMAP_STARS, False, "Stars"),
            ("gas",  "temperature", CMAP_TEMP,  True,  "Gas Temperature"),
        ],
    ]

    # Load particles once per halo (only what each pair needs)
    print("Loading pair-1 particles (gas + dm) …")
    particles_1 = load_halo_particles(hdf5_path_1, tag_1,
                                       particle_types=("gas", "dm"))
    print("Loading pair-2 particles (star + gas) …")
    particles_2 = load_halo_particles(hdf5_path_2, tag_2,
                                       particle_types=("star", "gas"))

    particle_sets = [particles_1, particles_2]
    durations     = [duration_1, duration_2]

    for pair_idx, (config, pset, dur) in enumerate(
            zip(PAIR_CONFIGS, particle_sets, durations)):

        n_frames    = int(dur * FPS)
        frames_fin  = int((fade_in_sec  if pair_idx == 0 else fade_mid_sec) * FPS)
        frames_fout = int((fade_mid_sec if pair_idx == 0 else fade_out_sec) * FPS)

        # Pre-fetch numpy arrays for each panel
        panel_data = []
        for pt, wf, cmap, inv, lbl in config:
            p = pset.get(pt)
            if p is None:
                print(f"  WARNING: {pt} particles missing — blank panel")
                panel_data.append(None)
                continue
            x = p["x"].astype(np.float32)
            y = p["y"].astype(np.float32)
            z = p["z"].astype(np.float32)
            if wf == "temperature" and "temperature" in p:
                weights = (p["mass"] * p["temperature"]).astype(np.float32)
            else:
                weights = p["mass"].astype(np.float32)
            panel_data.append((x, y, z, weights))
            print(f"  Pair {pair_idx+1} panel '{lbl}': {len(x):,} particles")

        # Build label overlay for this pair
        label_items = []
        for pi, (pt, wf, cmap, inv, lbl) in enumerate(config):
            label_items.append({
                "text":      lbl,
                "x":         proj_x[pi] + PROJ // 2,
                "y":         32,
                "size":      26,
                "color_rgb": FIELD_ACCENT_RGB.get(cmap, (230, 230, 230)),
                "bold":      False,
                "stroke_w":  1,
            })
        label_ov = make_text_overlay(label_items)

        black = Image.new("RGB", (W, H), (0, 0, 0))

        for i in range(n_frames):
            t     = i / n_frames
            theta = 2 * np.pi * n_azimuthal * t
            phi   = phi_max * np.sin(2 * np.pi * t)

            # Fade envelope
            if i < frames_fin:
                fade = smoothstep(i / max(frames_fin, 1))
            elif i >= n_frames - frames_fout and frames_fout > 0:
                fade = smoothstep(
                    1 - (i - (n_frames - frames_fout)) / max(frames_fout, 1))
            else:
                fade = 1.0

            # Render canvas
            canvas = Image.new("RGB", (W, H), (0, 0, 0))

            for pi, ((pt, wf, cmap, inv, lbl), arr) in enumerate(
                    zip(config, panel_data)):
                if arr is None:
                    continue
                x, y, z, weights = arr
                proj = make_projection_frame(
                    x, y, z, weights, theta, phi,
                    n_bins=PROJ, cmap_name=cmap,
                    invert_cmap=inv, size_px=PROJ)
                proj = add_glow(proj, radius=9, intensity=0.28)
                canvas.paste(proj, (proj_x[pi], proj_y))

            # Separator line
            sep_draw = ImageDraw.Draw(canvas)
            sep_draw.rectangle([PW, 0, PW + SEP - 1, H], fill=(18, 18, 18))

            canvas = add_vignette(canvas, strength=0.25)

            if fade < 1.0:
                canvas = Image.fromarray(
                    (np.array(canvas, dtype=np.float32) * fade
                     ).clip(0, 255).astype(np.uint8))

            canvas = composite_rgba(canvas, label_ov, alpha_mult=min(fade, 0.9))
            yield canvas


# ── Standalone preview ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    hdf5    = os.path.join(PARTICLE_DIR, FILE_MAP["R1"])

    if not os.path.exists(hdf5):
        print(f"ERROR: {hdf5} not found")
        raise SystemExit(1)

    tag = get_top_halos(hdf5, n=1)[0][1]
    print(f"Using most massive R1 halo: tag={tag}")

    particles = load_halo_particles(hdf5, tag, particle_types=("gas",))
    if "gas" not in particles:
        print("No gas particles found"); raise SystemExit(1)

    p = particles["gas"]
    x, y, z = p["x"], p["y"], p["z"]
    weights  = p["mass"]

    # Preview: face-on (theta=0, phi=0) and rotated 45° (theta=π/4)
    for angle_name, theta, phi in [
        ("faceon",   0.0,         0.0),
        ("rotated",  np.pi / 4,  0.15),
    ]:
        img = make_projection_frame(x, y, z, weights, theta, phi,
                                     n_bins=1024, cmap_name="plasma_r",
                                     invert_cmap=True)
        img = add_glow(img, 9, 0.3)
        img = fit_to_frame(img)
        img = add_vignette(img, 0.38)
        out_path = os.path.join(out_dir, f"preview_rotation_{angle_name}.png")
        img.save(out_path)
        print(f"Saved → {out_path}")
