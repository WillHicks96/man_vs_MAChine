# video_v2 — HACC Cluster Zoo Video Components

Reusable scene modules for the cluster morphology visualization video.
Output: `cluster_zoo_v2.mp4`  (1920×1080, 24 fps, H264)

## Quick start

```bash
# Run the full video assembler (~74 s output):
/home/nramachandra/anaconda3/envs/cosmodev/bin/python3 assemble_video_v2.py

# Preview individual scenes (no opencosmo needed for intro):
python3 scene_intro.py        → preview_intro.png
python3 scene_collage.py      → preview_collage.png   (renders 28 tiles first)
python3 scene_transitions.py  → preview_transition_single/three.png
python3 scene_rotation.py     → preview_rotation_faceon/rotated.png
```

## Files

| File | Purpose |
|---|---|
| `video_utils.py` | Shared constants, image utilities, OpenCosmo render helpers, encoder |
| `scene_intro.py` | Animated title card with relaxation criteria explanations |
| `scene_collage.py` | 7 × 4 gas-projection grid (one column per group, 4 halos each) |
| `scene_transitions.py` | DM → Stars → Gas → Gas Temperature field crossfades |
| `scene_rotation.py` | Custom particle-projection rotation (2D histogram, any axis) |
| `assemble_video_v2.py` | Master script: renders all scenes, encodes video |
| `renders/` | Cached opencosmo tile PNGs (auto-populated on first run) |

## Color palette

Matches `multifield_4field_random6_massive.png`:

| Field | Colormap |
|---|---|
| Dark Matter | `pink` |
| Stars | `gist_yarg_r` |
| Gas | `plasma_r` |
| Gas Temperature | `rainbow_r` |

## Particle data

```
/data/a/cpac/nramachandra/Projects/AmSC/particle_data/
  R1.hdf5, R1andR2.hdf5, R1andR3.hdf5, R1andR4.hdf5
  R1notR2.hdf5, R1notR3.hdf5, R1notR4.hdf5
```

Each file is an opencosmo StructureCollection with 30 halos and four
particle types: `dm_particles`, `gas_particles`, `star_particles`, `agn_particles`.

## Tuning key parameters

**Pacing** — in `scene_transitions.py`:
```python
scene_single_halo_transition(rset, hold_sec=2.5, xfade_sec=1.2)
scene_three_halo_transition(rsets, hold_sec=2.5, xfade_sec=1.2)
```

**Collage layout** — in `scene_collage.py`:
```python
N_ROWS = 4      # halos per group column
HEADER_H = 52   # header height in pixels
SEP = 1         # separator width in pixels
```

**Rotation** — in `scene_rotation.py`:
```python
scene_halo_rotation(hdf5, tag, duration=12, n_rotations=1,
                     particle_type="gas", phi_wobble=0.18)
scene_halo_rotation_multifield(hdf5, tag, secs_per_field=8)
```

**Video quality** — in `video_utils.py` / `assemble_video_v2.py`:
```python
encode_video(..., crf=16)   # lower = better quality, larger file
```

## Reusing in tools/

All modules are self-contained (absolute paths, no relative imports beyond
`video_utils`).  To move to `tools/`, update `EXPERIMENT_DIR` and `PARTICLE_DIR`
in `video_utils.py` and copy all six files.
