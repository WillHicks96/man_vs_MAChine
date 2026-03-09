#!/usr/bin/env python3
"""
Visualize shortlist halos (30 per group) using particle projections.

Outputs per group directory:
  individual/halo_NN_<tag>.png  — visualize_halo_quick (4-panel: DM, star, gas, gas temp)
  overview_dm.png               — 5x6 grid of DM projections
  overview_gas.png              — 5x6 grid of gas projections
  multifield_top10.png          — top 10 halos, DM + gas side by side
"""
import os, sys
import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import opencosmo as oc
from opencosmo.analysis import visualize_halo, halo_projection_array

# ── paths ─────────────────────────────────────────────────────────────────────
EXPERIMENT_DIR  = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/runs/research_20260218_105441"
PARTICLE_DIR    = "/data/a/cpac/nramachandra/Projects/AmSC/particle_data"
SHORTLIST_FILE  = os.path.join(EXPERIMENT_DIR, "halo_shortlist_30.txt")
OUTPUT_ROOT     = os.path.join(EXPERIMENT_DIR, "halo_viz")

# Map shortlist group names → particle HDF5 files
FILE_MAP = {
    "R1":       "R1.hdf5",
    "R1_andR2": "R1andR2.hdf5",
    "R1_andR3": "R1andR3.hdf5",
    "R1_andR4": "R1andR4.hdf5",
    "R1_notR2": "R1notR2.hdf5",
    "R1_notR3": "R1notR3.hdf5",
    "R1_notR4": "R1notR4.hdf5",
}

# ── parse shortlist ───────────────────────────────────────────────────────────
def parse_shortlist(path):
    """Return dict: group_name -> list of (rank, unique_tag) in rank order."""
    groups = {}
    cur = None
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("# ──"):
                cur = line.split()[2]
                groups[cur] = []
            elif cur and line and not line.startswith("#"):
                parts = line.split()
                groups[cur].append((int(parts[0]), int(parts[2])))
    return groups

# ── visualize one group ───────────────────────────────────────────────────────
def process_group(group_name, ranked_tags, hdf5_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    ind_dir = os.path.join(out_dir, "individual")
    os.makedirs(ind_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Group: {group_name}  ({len(ranked_tags)} halos)")
    print(f"  File : {os.path.basename(hdf5_path)}")
    print(f"  Out  : {out_dir}")
    print(f"{'='*60}")

    data = oc.open(hdf5_path)

    # ── 1. individual quick plots ─────────────────────────────────────────────
    print("  [1/3] Individual visualizations...")
    ok_tags = []
    for rank, tag in ranked_tags:
        save_path = os.path.join(ind_dir, f"halo_{rank:02d}_{tag}.png")
        try:
            fig = visualize_halo(tag, data)
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            ok_tags.append(tag)
            print(f"    rank {rank:02d}  tag={tag}  OK")
        except Exception as e:
            print(f"    rank {rank:02d}  tag={tag}  ERROR: {e}")

    if not ok_tags:
        print("  No successful halos — skipping overviews.")
        return

    # ── 2. Overview grids (DM and gas) ────────────────────────────────────────
    print("  [2/3] Overview grids (DM + gas)...")
    tags_arr = np.array(ok_tags[:30])
    n = len(tags_arr)
    # Pad to a 5×6 grid if needed
    nrows, ncols = 5, 6
    n_cells = nrows * ncols
    if n < n_cells:
        # repeat last tag to fill grid
        pad = np.full(n_cells - n, tags_arr[-1], dtype=tags_arr.dtype)
        tags_arr_grid = np.concatenate([tags_arr, pad])
    else:
        tags_arr_grid = tags_arr[:n_cells]
    grid = tags_arr_grid.reshape(nrows, ncols)

    for field, fname in [("dm", "overview_dm.png"), ("gas", "overview_gas.png")]:
        try:
            fig = halo_projection_array(grid, data, field=(field, "particle_mass"))
            fig.suptitle(f"{group_name}  —  {field.upper()} mass projection (5×6)", fontsize=12, y=1.01)
            fig.savefig(os.path.join(out_dir, fname), dpi=150, bbox_inches="tight")
            plt.close(fig)
            print(f"    {fname}  OK")
        except Exception as e:
            print(f"    {fname}  ERROR: {e}")

    # ── 3. Multifield top-10 (DM + gas side by side) ─────────────────────────
    print("  [3/3] Multifield top-10...")
    top10 = tags_arr[:10]
    halo_ids_mf = np.column_stack([top10, top10])   # (10, 2)
    params = {
        "fields": ([("dm", "particle_mass"), ("gas", "particle_mass")],) * len(top10),
        "labels": (["Dark Matter", "Gas"],) * len(top10),
        "cmaps":  (["gray", "cividis"],) * len(top10),
    }
    try:
        fig = halo_projection_array(halo_ids_mf, data, params=params, length_scale="all left")
        fig.suptitle(f"{group_name}  —  Top 10: DM & Gas projection", fontsize=12, y=1.005)
        fig.savefig(os.path.join(out_dir, "multifield_top10.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)
        print("    multifield_top10.png  OK")
    except Exception as e:
        print(f"    multifield_top10.png  ERROR: {e}")


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    groups = parse_shortlist(SHORTLIST_FILE)
    print(f"Parsed {len(groups)} groups from shortlist.")

    for group_name, fname in FILE_MAP.items():
        if group_name not in groups:
            print(f"WARNING: {group_name} not in shortlist — skipping")
            continue
        ranked_tags = groups[group_name]
        hdf5_path   = os.path.join(PARTICLE_DIR, fname)
        out_dir     = os.path.join(OUTPUT_ROOT, group_name)
        process_group(group_name, ranked_tags, hdf5_path, out_dir)

    print(f"\nAll done. Outputs in:\n  {OUTPUT_ROOT}/")

if __name__ == "__main__":
    main()
