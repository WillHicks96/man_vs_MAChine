#!/usr/bin/env python3
"""
Combined particle projection gallery: rank-1 halo from each group, 4 fields.

Layout: 7 rows (groups) × 4 columns (DM | Stars | Gas | Gas Temp)
Each halo = most extreme by its group's criterion (rank 1 from shortlist).
Uses halo_projection_array one group at a time, composing into a single figure.

Output: phase7_particle_gallery.png
"""
import os
import io
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from PIL import Image
import opencosmo as oc
from opencosmo.analysis import halo_projection_array

EXPERIMENT_DIR = "/data/a/cpac/nramachandra/Projects/AmSC/claude_agent_experiments/runs/research_20260218_105441"
PARTICLE_DIR   = "/data/a/cpac/nramachandra/Projects/AmSC/particle_data"
SHORTLIST_FILE = os.path.join(EXPERIMENT_DIR, "halo_shortlist_30.txt")
OUT_FILE       = os.path.join(EXPERIMENT_DIR, "phase7_particle_gallery.png")

# Groups in display order (matching phase6 stacked profiles columns)
GROUP_ORDER = [
    ("R1",       "R1.hdf5",       r"$\mathbf{R1}$  (DM-relaxed baseline, $\delta_1 < 0.07$)"),
    ("R1_andR2", "R1andR2.hdf5",  r"$\mathbf{R1 \cap R2}$  (gas-coherent, $\delta_2 < 0.07$)"),
    ("R1_notR2", "R1notR2.hdf5",  r"$\mathbf{R1 \cap \neg R2}$  (gas-displaced, $\delta_2 \geq 0.07$)"),
    ("R1_andR3", "R1andR3.hdf5",  r"$\mathbf{R1 \cap R3}$  (cool-core, $K_\mathrm{core} < 150$)"),
    ("R1_notR3", "R1notR3.hdf5",  r"$\mathbf{R1 \cap \neg R3}$  (non-cool-core, $K_\mathrm{core} \geq 150$)"),
    ("R1_andR4", "R1andR4.hdf5",  r"$\mathbf{R1 \cap R4}$  (TPI cool-core, TPI $> 0$)"),
    ("R1_notR4", "R1notR4.hdf5",  r"$\mathbf{R1 \cap \neg R4}$  (TPI non-cool-core, TPI $\leq 0$)"),
]

FIELDS = [("dm",  "particle_mass"),
          ("star", "particle_mass"),
          ("gas",  "particle_mass"),
          ("gas",  "temperature")]
LABELS = ["Dark Matter", "Stars", "Gas Mass", "Gas Temp"]
CMAPS  = ["bone", "bone", "viridis", "viridis_r"]

COL_TITLES = ["Dark Matter", "Stellar Mass", "Gas Mass", "Gas Temperature"]

# ── parse rank-1 tag per group ────────────────────────────────────────────────
def get_rank1_tags(shortlist_path):
    rank1 = {}
    cur = None
    with open(shortlist_path) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("# ──"):
                cur = line.split()[2]
            elif cur and line and not line.startswith("#"):
                parts = line.split()
                if int(parts[0]) == 1:          # rank == 1
                    rank1[cur] = int(parts[2])  # unique_tag
    return rank1

rank1_tags = get_rank1_tags(SHORTLIST_FILE)
print("Rank-1 tags:", rank1_tags)

# ── render each group to an in-memory image ───────────────────────────────────
TEMP_DIR = os.path.join(EXPERIMENT_DIR, "_tmp_gallery")
os.makedirs(TEMP_DIR, exist_ok=True)

group_images = []   # list of (label, PIL.Image)

for group_name, fname, label in GROUP_ORDER:
    tag = rank1_tags.get(group_name)
    if tag is None:
        print(f"  WARNING: no rank-1 tag for {group_name} — skipping")
        continue

    hdf5_path = os.path.join(PARTICLE_DIR, fname)
    print(f"\n  {group_name}: tag={tag}")

    data = oc.open(hdf5_path)

    # 1 halo, 4 fields
    halo_ids = np.array([[tag, tag, tag, tag]])   # (1, 4)
    params = {
        "fields": (FIELDS,),
        "labels": (LABELS,),
        "cmaps":  (CMAPS,),
    }

    try:
        fig = halo_projection_array(halo_ids, data, params=params,
                                    length_scale="all left")
        # render to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        img = Image.open(buf).copy()
        group_images.append((label, img))
        print(f"    rendered OK  ({img.size[0]}×{img.size[1]} px)")
    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback; traceback.print_exc()

# ── compose combined figure ───────────────────────────────────────────────────
if not group_images:
    raise RuntimeError("No group images rendered — cannot compose gallery.")

n_groups = len(group_images)

# Each row-image from halo_projection_array is a 1×4 strip.
# Stack them vertically with a label column on the left.
strip_w, strip_h = group_images[0][1].size

# Figure: label strip (left) + image strips (right)
LABEL_FRAC = 0.18    # fraction of total width for label column
fig_w = 22           # inches
label_w = fig_w * LABEL_FRAC
img_w   = fig_w - label_w
img_h_each = img_w * (strip_h / strip_w)
total_h = img_h_each * n_groups + 0.8  # +0.8 for column title row

fig = plt.figure(figsize=(fig_w, total_h))

# GridSpec: n_groups rows + 1 title row; 2 cols (label | strip)
gs = gridspec.GridSpec(
    n_groups + 1, 2,
    figure=fig,
    width_ratios=[LABEL_FRAC, 1 - LABEL_FRAC],
    height_ratios=[0.06] + [1.0] * n_groups,
    hspace=0.015,
    wspace=0.01,
)

# --- column title row (span image column) ---
ax_title = fig.add_subplot(gs[0, 1])
ax_title.set_xlim(0, 4)
ax_title.set_ylim(0, 1)
ax_title.axis("off")
for ci, ct in enumerate(COL_TITLES):
    ax_title.text(ci + 0.5, 0.5, ct,
                  ha="center", va="center",
                  fontsize=13, fontweight="bold",
                  transform=ax_title.transData)

# top-left corner: blank
ax_tl = fig.add_subplot(gs[0, 0])
ax_tl.axis("off")

# --- group rows ---
for ri, (label, img) in enumerate(group_images):
    # label cell
    ax_lbl = fig.add_subplot(gs[ri + 1, 0])
    ax_lbl.axis("off")
    ax_lbl.text(0.95, 0.5, label,
                ha="right", va="center",
                fontsize=9, linespacing=1.5,
                transform=ax_lbl.transAxes)

    # image strip cell
    ax_img = fig.add_subplot(gs[ri + 1, 1])
    ax_img.imshow(np.array(img))
    ax_img.axis("off")

fig.suptitle(
    "Particle Projections by Relaxation Class\n"
    r"Rank-1 halo per group (most extreme) — Dark Matter $\cdot$ Stars $\cdot$ Gas $\cdot$ Temperature",
    fontsize=13, y=1.002, va="bottom"
)

fig.savefig(OUT_FILE, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"\nGallery saved to:\n  {OUT_FILE}")
