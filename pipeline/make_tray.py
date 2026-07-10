"""
Synthetic tray generator: composites MVTec metal_nut images into a fixed
grid, simulating a tray of parts photographed from above.

Why this exists: the real T-nut + tray rig doesn't exist yet, but the tray
pipeline (slice grid -> classify each cell -> count) can be built and demoed
today against images this script produces. Bonus: because *we* choose what
goes in every cell, each tray comes with a ground-truth JSON sidecar -- the
exact labels and box positions a future single-shot YOLO tray detector would
need for training, with zero hand-labeling.

Usage:
    python3 make_tray.py                       # 3x4 tray, 3 defects, 1 empty
    python3 make_tray.py --rows 4 --cols 5 --defects 6 --empties 3
    python3 make_tray.py --seed 42             # reproducible layout

Outputs (in demo/trays/):
    tray_<timestamp>.jpg    the tray photo
    tray_<timestamp>.json   ground truth: grid size + per-cell label/source
"""

import argparse
import json
import random
import time
from pathlib import Path

import cv2
import numpy as np

DATA_ROOT = Path(__file__).parent.parent / "training data" / "metal_nut" / "test"
OUT_DIR = Path(__file__).parent.parent / "demo" / "trays"

# Native MVTec resolution -- do NOT shrink. The model was trained on 700px
# images; downscaling + JPEG compression adds artifacts a scratch detector
# reads as surface damage (first 320px/JPEG attempt failed all 11 nuts).
CELL = 700
TRAY_BG = (38, 40, 44)   # BGR -- dark tray plate, close to MVTec's background
SLOT_RING = (55, 58, 63)  # faint circle marking an empty slot

DEFECT_CLASSES = ["bent", "color", "flip", "scratch"]


def list_images(folder):
    return sorted((DATA_ROOT / folder).glob("*.png"))


def make_empty_cell():
    """A plain tray cell with a faint slot ring -- deliberately near-uniform,
    which is exactly what the pipeline's empty-slot check keys on."""
    cell = np.full((CELL, CELL, 3), TRAY_BG, dtype=np.uint8)
    cv2.circle(cell, (CELL // 2, CELL // 2), int(CELL * 0.38), SLOT_RING, 3)
    return cell


def make_nut_cell(image_path):
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Couldn't read {image_path}")
    return cv2.resize(img, (CELL, CELL), interpolation=cv2.INTER_AREA)


def build_tray(rows, cols, n_defects, n_empties, rng):
    n_cells = rows * cols
    if n_defects + n_empties > n_cells:
        raise SystemExit(f"defects + empties ({n_defects + n_empties}) exceeds grid size ({n_cells})")

    # Assign a label to every cell position, then shuffle the positions.
    labels = (["defect"] * n_defects) + (["empty"] * n_empties)
    labels += ["good"] * (n_cells - len(labels))
    rng.shuffle(labels)

    good_pool = list_images("good")
    defect_pools = {c: list_images(c) for c in DEFECT_CLASSES}

    tray = np.full((rows * CELL, cols * CELL, 3), TRAY_BG, dtype=np.uint8)
    cells = []
    for idx, label in enumerate(labels):
        r, c = divmod(idx, cols)
        y, x = r * CELL, c * CELL

        if label == "empty":
            tile, source = make_empty_cell(), None
        elif label == "good":
            source = rng.choice(good_pool)
            tile = make_nut_cell(source)
        else:
            defect_class = rng.choice(DEFECT_CLASSES)
            source = rng.choice(defect_pools[defect_class])
            tile = make_nut_cell(source)
            label = f"defect:{defect_class}"

        tray[y:y + CELL, x:x + CELL] = tile
        cells.append({
            "row": r, "col": c, "label": label,
            "source": str(source.relative_to(DATA_ROOT)) if source else None,
            # pixel box of this cell -- ready-made YOLO training annotation
            "box": [x, y, x + CELL, y + CELL],
        })

    return tray, cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--defects", type=int, default=3)
    ap.add_argument("--empties", type=int, default=1)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    tray, cells = build_tray(args.rows, args.cols, args.defects, args.empties, rng)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    img_path = OUT_DIR / f"tray_{stamp}.png"  # lossless -- no JPEG artifacts
    json_path = OUT_DIR / f"tray_{stamp}.json"

    cv2.imwrite(str(img_path), tray)
    json_path.write_text(json.dumps({
        "rows": args.rows, "cols": args.cols, "cell_px": CELL, "cells": cells,
    }, indent=2))

    n_def = sum(1 for c in cells if c["label"].startswith("defect"))
    n_emp = sum(1 for c in cells if c["label"] == "empty")
    print(f"Tray: {args.rows}x{args.cols} -> {img_path}")
    print(f"Ground truth: {json_path}")
    print(f"Contents: {len(cells) - n_def - n_emp} good, {n_def} defective, {n_emp} empty")


if __name__ == "__main__":
    main()
