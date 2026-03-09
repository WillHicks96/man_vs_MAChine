"""
assemble_video_v2.py — Master assembler for the improved cluster zoo video.

Video structure
---------------
  Scene 1  Intro title card with criteria explanations         ~8 s
  Scene 2  3×2 grid: 6 halos cycling all 4 fields            ~22 s
  Scene 3  Selection reveal: 4×3 grid, boxes + crossfades     ~12 s
  Scene 4  Multifield collage tour (R1, R1∖R2, R1∖R3, R1∖R4) ~21 s
  Scene 5  1×2 synced 3D rotation
             Pair 1  Gas | DM          (10 s)
             Pair 2  Stars | Gas Temp  (10 s)               ~20 s
  Total ≈ 83 s  ·  1920×1080  ·  24 fps

All OpenCosmo tile renders are cached; re-running skips rendering and only
regenerates frames + encodes the video.




Usage
-----
    /home/nramachandra/anaconda3/envs/cosmodev/bin/python3 \\
        /data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/runs/research_20260218_105441/video_v2/assemble_video_v2.py
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from video_utils import (
    FPS, W, H,
    PARTICLE_DIR, VIDEO_V2_DIR, RENDERS_DIR, FILE_MAP,
    get_top_halos, save_frames, encode_video,
)
from scene_intro       import scene_intro
from scene_collage     import prepare_group_multifield_renders, scene_group_multifield_tour
from scene_transitions import (
    prepare_transition_renders, render_set_from_cache,
    scene_six_halo_grid_transition,
)
from scene_selection   import prepare_selection_renders, scene_selection_reveal
from scene_rotation    import scene_halo_rotation_3d, scene_dual_rotation_3d_synced

import numpy as np

FRAMES_DIR   = os.path.join(VIDEO_V2_DIR, "frames_v2")
OUTPUT_VIDEO = os.path.join(VIDEO_V2_DIR, "cluster_zoo_v2.mp4")

os.makedirs(FRAMES_DIR, exist_ok=True)

# Groups for Scene 2 (6-halo grid): one halo from each group
GRID_GROUPS  = ["R1", "R1_andR2", "R1_notR2",
                "R1_andR3", "R1_notR3", "R1_notR4"]

# Groups for Scene 4 (multifield collage tour)
TOUR_GROUPS  = ["R1", "R1_notR2", "R1_notR3", "R1_notR4"]


def main():
    print("=" * 65)
    print("  HACC Cluster Zoo  —  Video v2")
    print("=" * 65)

    # ── Phase 1: Pre-render all OpenCosmo tiles ────────────────────────────────
    print("\n── Phase 1: Pre-render OpenCosmo tiles ──")

    # Scene 2: one halo from each of the 6 grid groups
    grid_render_sets = []
    grid_labels      = []
    for g in GRID_GROUPS:
        hdf5 = os.path.join(PARTICLE_DIR, FILE_MAP[g])
        if not os.path.exists(hdf5):
            print(f"  WARNING: {hdf5} not found — skipping {g}"); continue
        top = get_top_halos(hdf5, n=3)
        _, tag = top[min(1, len(top) - 1)]
        prefix = prepare_transition_renders(hdf5, tag, RENDERS_DIR, f"{g}_tag{tag}")
        grid_render_sets.append(render_set_from_cache(RENDERS_DIR, prefix))
        grid_labels.append(g)
        print(f"  grid {g}: tag={tag}")

    # Scene 3: selection reveal tiles (4 groups × 3 halos each)
    print("\nPre-rendering selection reveal tiles …")
    prepare_selection_renders(RENDERS_DIR)

    # Scene 4: multifield collage tiles (4 tour groups × 7 halos × 4 fields)
    for g in TOUR_GROUPS:
        prepare_group_multifield_renders(g, RENDERS_DIR, n_halos=7)

    # Scene 5: two halos from R1_notR4 for the dual 3D rotation
    rot_hdf5 = os.path.join(PARTICLE_DIR, FILE_MAP["R1_notR4"])
    rot_top  = get_top_halos(rot_hdf5, n=2)
    rot_tag_1 = rot_top[0][1]                          # most massive
    rot_tag_2 = rot_top[min(1, len(rot_top) - 1)][1]   # second most massive (or same)
    print(f"  Rotation halo 1 (Gas+DM):   R1_notR4 tag={rot_tag_1}")
    print(f"  Rotation halo 2 (Stars+GT): R1_notR4 tag={rot_tag_2}")

    # ── Phase 2: Clear frames directory ───────────────────────────────────────
    print("\n── Phase 2: Clearing frame directory ──")
    if os.path.exists(FRAMES_DIR):
        shutil.rmtree(FRAMES_DIR)
    os.makedirs(FRAMES_DIR)
    frame_idx = 0

    # ── Phase 3: Generate all frames ──────────────────────────────────────────
    print("\n── Phase 3: Frame generation ──")

    # Scene 1 — Intro (8 s)
    print("  Scene 1: Intro …")
    frame_idx, _ = save_frames(
        scene_intro(duration=8, fade_out=True),
        FRAMES_DIR, start_idx=frame_idx, label="intro")

    # Scene 2 — 3×2 grid field transitions (~22 s at hold=3.0, xfade=1.5)
    if len(grid_render_sets) >= 6:
        print("  Scene 2: 3×2 grid field transitions …")
        frame_idx, _ = save_frames(
            scene_six_halo_grid_transition(
                grid_render_sets[:6],
                hold_sec=3.0, xfade_sec=1.5,
                group_labels=None,
                fade_in_sec=0.8, fade_out_sec=0.8,
            ),
            FRAMES_DIR, start_idx=frame_idx, label="grid_transition")
    else:
        print(f"  WARNING: only {len(grid_render_sets)} groups available for grid (need 6)")

    # Scene 3 — Selection criteria reveal (~12.5 s)
    print("  Scene 3: Selection criteria reveal …")
    frame_idx, _ = save_frames(
        scene_selection_reveal(
            renders_dir=RENDERS_DIR,
            total_sec=12.5,
            fade_in_sec=1.5,
            fade_out_sec=1.0,
        ),
        FRAMES_DIR, start_idx=frame_idx, label="selection_reveal")

    # Scene 4 — Multifield collage tour (~21 s at hold=4.0, xfade=1.2)
    print("  Scene 4: Multifield collage tour …")
    frame_idx, _ = save_frames(
        scene_group_multifield_tour(
            TOUR_GROUPS,
            renders_dir=RENDERS_DIR,
            n_halos=7,
            hold_sec=4.0,
            xfade_sec=1.2,
            fade_in_sec=0.6,
            fade_out_sec=0.6,
        ),
        FRAMES_DIR, start_idx=frame_idx, label="collage_tour")

    # Scene 5 — Dual 1×2 synced 3D rotation (~20 s total)
    #   Pair 1 (10 s): Gas (left) | DM (right)          — halo 1
    #   Pair 2 (10 s): Stars (left) | Gas Temp (right)  — halo 2
    print("  Scene 5: Dual 1×2 synced 3D rotation …")
    frame_idx, _ = save_frames(
        scene_dual_rotation_3d_synced(
            rot_hdf5, rot_tag_1,
            rot_hdf5, rot_tag_2,
            duration_1=10, duration_2=10,
            n_azimuthal=2, phi_max=np.pi / 2,
            n_bins=900,
            fade_in_sec=0.8,
            fade_mid_sec=0.7,
            fade_out_sec=0.8,
        ),
        FRAMES_DIR, start_idx=frame_idx, label="dual_rotation")

    total_secs = frame_idx / FPS
    print(f"\n  Total frames: {frame_idx}  (~{total_secs:.0f} s)")

    # ── Phase 4: Encode ────────────────────────────────────────────────────────
    print("\n── Phase 4: Encoding ──")
    encode_video(FRAMES_DIR, OUTPUT_VIDEO, fps=FPS, w=W, h=H, crf=16)

    print(f"\n  Output: {OUTPUT_VIDEO}")
    print("=" * 65)


if __name__ == "__main__":
    main()
