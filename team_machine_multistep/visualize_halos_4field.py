#!/usr/bin/env python3
"""
4-field multifield visualizations: 6 random halos per group.
Each row = one halo; columns = Dark Matter | Stars | Gas | Gas Temperature.
Output: halo_viz/<group>/multifield_4field_random6.png
"""
import os
import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import opencosmo as oc
from opencosmo.analysis import halo_projection_array

# ── paths ─────────────────────────────────────────────────────────────────────
EXPERIMENT_DIR = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/runs/research_20260218_105441"
PARTICLE_DIR   = "/data/a/cpac/nramachandra/Projects/AmSC/particle_data"
OUTPUT_ROOT    = os.path.join(EXPERIMENT_DIR, "halo_viz")

FILE_MAP = {
    "R1":       "R1.hdf5",
    "R1_andR2": "R1andR2.hdf5",
    "R1_andR3": "R1andR3.hdf5",
    "R1_andR4": "R1andR4.hdf5",
    "R1_notR2": "R1notR2.hdf5",
    "R1_notR3": "R1notR3.hdf5",
    "R1_notR4": "R1notR4.hdf5",
}

N_HALOS = 6
RNG_SEED = 32 #42  # fixed for reproducibility

FIELDS  = [("dm",  "particle_mass"),
           ("star", "particle_mass"),
           ("gas",  "particle_mass"),
           ("gas",  "temperature")]
LABELS  = ["Dark Matter", "Stars", "Gas", "Gas Temp"]
# CMAPS   = ["bone", "hot", "cividis", "RdYlBu_r"]
CMAPS   = ["bone", "bone", "viridis", "viridis_r"]

# ── main ──────────────────────────────────────────────────────────────────────
rng = np.random.default_rng(RNG_SEED)

for group_name, fname in FILE_MAP.items():
    hdf5_path = os.path.join(PARTICLE_DIR, fname)
    out_dir   = os.path.join(OUTPUT_ROOT, group_name)
    out_file  = os.path.join(out_dir, "multifield_4field_random6.png")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  {group_name}  →  {os.path.basename(out_file)}")

    data = oc.open(hdf5_path)

    # all unique tags in this file
    all_tags = [int(halo["halo_properties"]["unique_tag"])
                for halo in data.halos()]

    # pick N_HALOS at random (without replacement)
    chosen = rng.choice(all_tags, N_HALOS, replace=False).tolist()
    print(f"  Selected tags: {chosen}")

    # halo_ids: (N_HALOS, 4) — same tag repeated once per field column
    halo_ids = np.column_stack([chosen] * len(FIELDS))

    params = {
        "fields": (FIELDS,)  * N_HALOS,
        "labels": (LABELS,)  * N_HALOS,
        "cmaps":  (CMAPS,)   * N_HALOS,
    }

    try:
        fig = halo_projection_array(halo_ids, data, params=params,
                                    length_scale="all left")
        fig.suptitle(
            f"{group_name}  —  6 random halos: DM | Stars | Gas | Gas Temp",
            fontsize=13, y=1.005
        )
        fig.savefig(out_file, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved: {out_file}")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback; traceback.print_exc()

print("\nAll done.")
