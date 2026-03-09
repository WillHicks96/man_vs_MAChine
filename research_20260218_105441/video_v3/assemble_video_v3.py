"""
assemble_video_v3.py — Master assembler for HACC Cluster Zoo video v3.

Video structure
---------------
  Scene 1   Intro title card (criteria explanations)            ~5 s
  Scene 2   DM Offset  (R1 vs ¬R1*)  synced 2×2 grid rotation  ~7 s
  Scene 3   DM–Gas Offset  (R1∩R2 vs R1∖R2)                    ~7 s
  Scene 4   Entropy  (R1∩R3 vs R1∖R3)                           ~7 s
  Scene 5   Temp–Density  (R1∩R4 vs R1∖R4)                      ~7 s
  Total ≈ 33 s  ·  1920×1080  ·  24 fps

*  notR1 particle file does not yet exist.  As a placeholder, the
   4 random halos from R1∖R2 are shown in the right panel of
   Scene 2.  These will be replaced with actual notR1 halos later.

Each of Scenes 2–5 uses a SYNCED 2-column 2×2 grid:
  LEFT  column  →  2×2 grid of RELAXED halos
  RIGHT column  →  2×2 grid of UNRELAXED halos
Both columns share the same theta/phi trajectory and cycle through
4 fields:  Dark Matter → Stars → Gas → Gas Temperature.

Halo selection: random sample of 4 from each group (not just most
massive) to avoid the circular boundary artifact from large halos.
Seed is fixed for reproducibility.

Usage
-----
    /home/nramachandra/anaconda3/envs/cosmodev/bin/python3 \\
        /data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/\\
        runs/research_20260218_105441/video_v3/assemble_video_v3.py
"""

import os
import sys
import shutil
import h5py
import numpy as np

# ── Paths ───────────────────────────────────────────────────────────────────────

VIDEO_V3_DIR   = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT_DIR = os.path.join(VIDEO_V3_DIR, "..")
PARTICLE_DIR   = "/data/a/cpac/nramachandra/Projects/AmSC/particle_data"

FRAMES_DIR   = os.path.join(VIDEO_V3_DIR, "frames_v3")
OUTPUT_VIDEO = os.path.join(VIDEO_V3_DIR, "cluster_zoo_v3.mp4")

CATALOG_PATH = ("/data/a/cpac/nramachandra/Projects/AmSC/tmp/OpenCosmo/"
                "5ee0c456-c6a5-4265-97e1-1f66f69e20d4/filtered_haloproperties.hdf5")

# Make video_v2 importable (shares video_utils, scene_rotation helpers)
sys.path.insert(0, os.path.join(EXPERIMENT_DIR, "video_v2"))
sys.path.insert(0, VIDEO_V3_DIR)

from video_utils import FPS, W, H, encode_video, save_frames
from scene_v3_intro        import scene_v3_intro
from scene_v3_grid_rotation import scene_synced_grid_rotation

os.makedirs(FRAMES_DIR, exist_ok=True)

# ── Particle files ──────────────────────────────────────────────────────────────

FILE_MAP = {
    "R1":       os.path.join(PARTICLE_DIR, "R1.hdf5"),
    "R1andR2":  os.path.join(PARTICLE_DIR, "R1andR2.hdf5"),
    "R1andR3":  os.path.join(PARTICLE_DIR, "R1andR3.hdf5"),
    "R1andR4":  os.path.join(PARTICLE_DIR, "R1andR4.hdf5"),
    "R1notR2":  os.path.join(PARTICLE_DIR, "R1notR2.hdf5"),
    "R1notR3":  os.path.join(PARTICLE_DIR, "R1notR3.hdf5"),
    "R1notR4":  os.path.join(PARTICLE_DIR, "R1notR4.hdf5"),
}


# ── Random halo selection ───────────────────────────────────────────────────────

def get_random_halo_tags(hdf5_path, n=4, seed=42):
    """
    Randomly sample n halo unique_tags from a particle HDF5 file.

    Uses a fixed seed for reproducibility.  This avoids selecting only
    the most massive halos, which tend to have a circular boundary artifact.
    """
    with h5py.File(hdf5_path, "r") as f:
        tags = np.array(f["halo_properties/data/unique_tag"])
    if len(tags) <= n:
        return list(tags)
    rng = np.random.default_rng(seed)
    chosen = rng.choice(tags, size=n, replace=False)
    return [int(t) for t in chosen]


# ── Rotation parameters (shared across all grid scenes) ─────────────────────────

ROT_PARAMS = dict(
    duration        = 7.0,
    n_azimuthal     = 1,             # 1 full azimuthal rotation per scene (was 2)
    phi_max         = 3.14159 / 4,   # ±45° elevation range — edit freely (was π/2)
    n_bins          = 340,           # tile pixel size (matches PROJ=340, fills TILE_W=360)
    field_cycle_sec = 1.75,           # 4 fields × 1.75 s = 7 s
    xfade_sec       = 0.28,           # short crossfade
    fade_in_sec     = 0.45,
    fade_out_sec    = 0.45,
    catalog_path    = CATALOG_PATH,
)


def main():
    print("=" * 65)
    print("  HACC Cluster Zoo  —  Video v3")
    print("=" * 65)

    # ── Select random halo tags ────────────────────────────────────────────────
    print("\n── Selecting random halo tags ──")
    TAGS = {}
    for key, path in FILE_MAP.items():
        if os.path.exists(path):
            TAGS[key] = get_random_halo_tags(path, n=4, seed=42)
            print(f"  {key}: {TAGS[key]}")
        else:
            print(f"  WARNING: {path} not found — skipping {key}")
    # Placeholder for notR1: random selection from R1notR2
    TAGS["notR1_placeholder"] = get_random_halo_tags(FILE_MAP["R1notR2"], n=4, seed=99)
    print(f"  notR1_placeholder: {TAGS['notR1_placeholder']}")

    # ── Clear frames directory ─────────────────────────────────────────────────
    if os.path.exists(FRAMES_DIR):
        shutil.rmtree(FRAMES_DIR)
    os.makedirs(FRAMES_DIR)
    frame_idx = 0

    # ── Scene 1: Intro (~5 s) ─────────────────────────────────────────────────
    print("\n── Scene 1: Intro ──")
    frame_idx, _ = save_frames(
        scene_v3_intro(duration=5.0, fade_out=True),
        FRAMES_DIR, start_idx=frame_idx, label="s1_intro")

    # ── Scene 2: Baseline — DM offset (R1 vs ¬R1) ────────────────────────────
    # notR1 particle file not yet available → use R1notR2 as placeholder
    print("\n── Scene 2: DM Offset  (R₁  vs  ¬R₁  [placeholder: R₁∖R₂]) ──")
    frame_idx, _ = save_frames(
        scene_synced_grid_rotation(
            left_tags   = TAGS["R1"],
            left_hdf5   = FILE_MAP["R1"],
            right_tags  = TAGS["notR1_placeholder"],
            right_hdf5  = FILE_MAP["R1notR2"],
            scene_title = "Baseline criterion: Dark Matter offset  (δ₁)",
            left_label  = "Relaxed  ·  R₁",
            right_label = "Unrelaxed  ·  ¬R₁",
            left_note   = "satisfy δ₁  ·  DM relaxed",
            right_note  = "Placeholder: R₁∖R₂  (notR₁ pending)",
            col_idx     = 0,
            **ROT_PARAMS,
        ),
        FRAMES_DIR, start_idx=frame_idx, label="s2_dm_offset")

    # ── Scene 3: Agent — DM–Gas offset (R1∩R2 vs R1∖R2) ─────────────────────
    print("\n── Scene 3: DM–Gas Offset  (R₁∩R₂  vs  R₁∖R₂) ──")
    frame_idx, _ = save_frames(
        scene_synced_grid_rotation(
            left_tags   = TAGS["R1andR2"],
            left_hdf5   = FILE_MAP["R1andR2"],
            right_tags  = TAGS["R1notR2"],
            right_hdf5  = FILE_MAP["R1notR2"],
            scene_title = "Agent-generated criterion: Dark Matter–Gas offset  (δ₂)",
            left_label  = "Relaxed  ·  R₁∩R₂",
            right_label = "Unrelaxed  ·  R₁∖R₂",
            left_note   = "satisfy δ₁ & δ₂",
            right_note  = "satisfy δ₁ but not δ₂",
            col_idx     = 1,
            **ROT_PARAMS,
        ),
        FRAMES_DIR, start_idx=frame_idx, label="s3_dm_gas_offset")

    # ── Scene 4: Agent — Entropy (R1∩R3 vs R1∖R3) ────────────────────────────
    print("\n── Scene 4: Entropy  (R₁∩R₃  vs  R₁∖R₃) ──")
    frame_idx, _ = save_frames(
        scene_synced_grid_rotation(
            left_tags   = TAGS["R1andR3"],
            left_hdf5   = FILE_MAP["R1andR3"],
            right_tags  = TAGS["R1notR3"],
            right_hdf5  = FILE_MAP["R1notR3"],
            scene_title = "Agent-generated criterion: Core Entropy  (K_core)",
            left_label  = "Relaxed  ·  R₁∩R₃",
            right_label = "Unrelaxed  ·  R₁∖R₃",
            left_note   = "satisfy δ₁ & K_core",
            right_note  = "satisfy δ₁ but not K_core",
            col_idx     = 2,
            **ROT_PARAMS,
        ),
        FRAMES_DIR, start_idx=frame_idx, label="s4_entropy")

    # ── Scene 5: Agent — Temp–Density (R1∩R4 vs R1∖R4) ──────────────────────
    print("\n── Scene 5: Temp–Density  (R₁∩R₄  vs  R₁∖R₄) ──")
    frame_idx, _ = save_frames(
        scene_synced_grid_rotation(
            left_tags   = TAGS["R1andR4"],
            left_hdf5   = FILE_MAP["R1andR4"],
            right_tags  = TAGS["R1notR4"],
            right_hdf5  = FILE_MAP["R1notR4"],
            scene_title = "Agent-generated criterion: Thermodynamic Peakiness Index  (TPI)",
            left_label  = "Relaxed  ·  R₁∩R₄",
            right_label = "Unrelaxed  ·  R₁∖R₄",
            left_note   = "satisfy δ₁ & TPI",
            right_note  = "satisfy δ₁ but not TPI",
            col_idx     = 3,
            **ROT_PARAMS,
        ),
        FRAMES_DIR, start_idx=frame_idx, label="s5_tpi")

    total_secs = frame_idx / FPS
    print(f"\n  Total frames: {frame_idx}  (~{total_secs:.0f} s)")

    # ── Encode ─────────────────────────────────────────────────────────────────
    print("\n── Encoding ──")
    encode_video(FRAMES_DIR, OUTPUT_VIDEO, fps=FPS, w=W, h=H, crf=16)

    print(f"\n  Output: {OUTPUT_VIDEO}")
    print("=" * 65)


if __name__ == "__main__":
    main()
