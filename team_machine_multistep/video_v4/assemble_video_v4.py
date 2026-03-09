"""
assemble_video_v4.py — Master assembler for HACC Cluster Zoo video v4.

Video structure
---------------
  Scene 1   Intro title card (5 s animated build + 3 s hold with
            glowing boxes around δ₁ and TPI criteria)              ~8 s
  Scene 2   Baseline criterion: Dark Matter offset  (δ₁)
            R₁ vs ¬R₁  —  synced 2×2 grid rotation                16 s
  Scene 3   Agent-generated criterion: Temperature-Density  (TPI)
            R₁∩R₄ vs R₁∖R₄  —  synced 2×2 grid rotation          16 s
  Total ≈ 40 s  ·  1920×1080  ·  24 fps  ·  CRF 12 (high quality)

Key differences from v3
-----------------------
  - Intro: 5 s animated build (no fade-out) + 3 s hold with glowing
    highlight boxes on δ₁ and TPI/δ₄ rows
  - Only 2 rotation scenes (instead of 4) — δ₁ and TPI
  - 3 fields per scene: Dark Matter, Stars, Gas Temperature  (Gas mass removed)
  - Profile centre panel shows both lines (relaxed + unrelaxed) at once —
    no staged 2-phase reveal
  - 16 s per rotation scene (vs 7 s in v3)
  - phi_max = π/2  (full ±90° elevation; wider sweep thanks to extra time)
  - 2 full azimuthal rotations per scene (same angular speed as v3)
  - Tile renders 2× super-sampled for sharper pixel quality
  - Encoded at CRF=12 for high-quality output

Usage
-----
    /home/nramachandra/anaconda3/envs/cosmodev/bin/python3 \\
        /data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/\\
        runs/research_20260218_105441/video_v4/assemble_video_v4.py
"""

import os
import sys
import shutil
import h5py
import numpy as np

# ── Paths ────────────────────────────────────────────────────────────────────

VIDEO_V4_DIR   = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT_DIR = os.path.join(VIDEO_V4_DIR, "..")
PARTICLE_DIR   = "/data/a/cpac/nramachandra/Projects/AmSC/particle_data"

FRAMES_DIR   = os.path.join(VIDEO_V4_DIR, "frames_v4")
OUTPUT_VIDEO = os.path.join(VIDEO_V4_DIR, "cluster_zoo_v4.mp4")

CATALOG_PATH = ("/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/"
                "5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5")

# Make video_v2 and video_v4 importable
sys.path.insert(0, os.path.join(EXPERIMENT_DIR, "video_v2"))
sys.path.insert(0, VIDEO_V4_DIR)

from video_utils import FPS, W, H, encode_video, save_frames
from scene_v4_intro         import scene_v4_intro
from scene_v4_grid_rotation import scene_synced_grid_rotation_v4

os.makedirs(FRAMES_DIR, exist_ok=True)

# ── Particle files ───────────────────────────────────────────────────────────

FILE_MAP = {
    "R1":    os.path.join(PARTICLE_DIR, "R1.hdf5"),
    "notR1": os.path.join(PARTICLE_DIR, "notR1.hdf5"),
    "R4":    os.path.join(PARTICLE_DIR, "R4.hdf5"),
    "notR4": os.path.join(PARTICLE_DIR, "notR4.hdf5"),
}


# ── Random halo selection ────────────────────────────────────────────────────

def get_random_halo_tags(hdf5_path, n=4, seed=1234, n_massive_sample=10):
    """Randomly sample n tags from the n_massive_sample most massive halos."""
    with h5py.File(hdf5_path, "r") as f:
        tags   = np.array(f["halo_properties/data/unique_tag"])
        masses = np.array(f["halo_properties/data/fof_halo_mass"])
    # Restrict pool to the top n_massive_sample most massive halos
    pool_size = min(n_massive_sample, len(tags))
    top_idx   = np.argsort(masses)[::-1][:pool_size]
    pool_tags = tags[top_idx]
    if len(pool_tags) <= n:
        return [int(t) for t in pool_tags]
    rng = np.random.default_rng(seed)
    return [int(t) for t in rng.choice(pool_tags, size=n, replace=False)]


# ── Rotation parameters (shared for scenes 2 & 3) ───────────────────────────
#
#   Angular speed target (matching v3): ~45–51°/s azimuthal
#     v3 had n_azimuthal=1, duration=7s  → 360/7 ≈ 51°/s
#     v4 uses n_azimuthal=2, duration=16s → 2×360/16 = 45°/s  ✓ same speed
#
#   phi_max = π/2 (±90° elevation) — wider sweep enabled by the longer duration.
#   Edit phi_max freely to taste (e.g. np.pi/3 for ±60°, np.pi/4 for ±45°).

ROT_PARAMS = dict(
    duration        = 16.0,
    n_azimuthal     = 2,              # 2 full azimuthal rotations over 16 s
    phi_max         = np.pi / 2,      # ±90° elevation range — edit freely
    n_bins          = 340,            # final tile px; histogram at 2× = 680 px
    field_cycle_sec = None,           # None → duration / 3 = 5.33 s per field
    xfade_sec       = 0.5,            # crossfade between fields
    fade_in_sec     = 0.6,
    fade_out_sec    = 0.6,
    catalog_path    = CATALOG_PATH,
)


def main():
    print("=" * 65)
    print("  HACC Cluster Zoo  —  Video v4")
    print("=" * 65)

    # ── Select random halo tags ──────────────────────────────────────────────
    print("\n── Selecting random halo tags ──")
    TAGS = {}
    for key, path in FILE_MAP.items():
        if os.path.exists(path):
            TAGS[key] = get_random_halo_tags(path, n=4, seed=1234)
            print(f"  {key}: {TAGS[key]}")
        else:
            print(f"  WARNING: {path} not found — skipping {key}")

    # ── Clear frames directory ───────────────────────────────────────────────
    if os.path.exists(FRAMES_DIR):
        shutil.rmtree(FRAMES_DIR)
    os.makedirs(FRAMES_DIR)
    frame_idx = 0

    # ── Scene 1: Intro (5 s anim + 3 s hold with highlight boxes) ───────────
    print("\n── Scene 1: Intro ──")
    frame_idx, _ = save_frames(
        scene_v4_intro(anim_duration=5.0, hold_duration=3.0),
        FRAMES_DIR, start_idx=frame_idx, label="s1_intro")

    # ── Scene 2: Baseline — DM offset (R₁ vs ¬R₁) ──────────────────────────
    print("\n── Scene 2: Baseline — Dark Matter offset  (δ₁) ──")
    frame_idx, _ = save_frames(
        scene_synced_grid_rotation_v4(
            left_tags   = TAGS["R1"],
            left_hdf5   = FILE_MAP["R1"],
            right_tags  = TAGS["notR1"],
            right_hdf5  = FILE_MAP["notR1"],
            scene_title = ("Baseline criterion: Dark Matter offset  (δ₁): "
                           "R₁ vs ¬R₁"),
            left_label  = "Relaxed  ·  R₁",
            right_label = "Unrelaxed  ·  ¬R₁",
            left_note   = "δ₁ < 0.07  ·  DM relaxed",
            right_note  = "δ₁ ≥ 0.07  ·  DM disturbed",
            col_idx     = 0,
            **ROT_PARAMS,
        ),
        FRAMES_DIR, start_idx=frame_idx, label="s2_dm_offset")

    # ── Scene 3: Agent — Temperature-Density / TPI (R₄ vs ¬R₄) ─────────────
    print("\n── Scene 3: Agent — TPI  (R₄  vs  ¬R₄) ──")
    frame_idx, _ = save_frames(
        scene_synced_grid_rotation_v4(
            left_tags   = TAGS["R4"],
            left_hdf5   = FILE_MAP["R4"],
            right_tags  = TAGS["notR4"],
            right_hdf5  = FILE_MAP["notR4"],
            scene_title = ("Agent-generated criterion: Temperature-Density  (TPI): "
                           "R₄ vs ¬R₄"),
            left_label  = "Cool-core  ·  R₄",
            right_label = "Non-cool-core  ·  ¬R₄",
            left_note   = "TPI > 0  ·  high density + T-drop",
            right_note  = "TPI ≤ 0  ·  disrupted/AGN-heated core",
            col_idx     = 3,
            **ROT_PARAMS,
        ),
        FRAMES_DIR, start_idx=frame_idx, label="s3_tpi")

    total_secs = frame_idx / FPS
    print(f"\n  Total frames: {frame_idx}  (~{total_secs:.1f} s)")

    # ── Encode — CRF=12 for high quality ────────────────────────────────────
    print("\n── Encoding (CRF=12) ──")
    encode_video(FRAMES_DIR, OUTPUT_VIDEO, fps=FPS, w=W, h=H, crf=12)

    print(f"\n  Output: {OUTPUT_VIDEO}")
    print("=" * 65)


if __name__ == "__main__":
    main()
