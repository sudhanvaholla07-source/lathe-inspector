"""
Variant tray generator: composites a MIX of part types (metal nuts and
screws, standing in for real part variants) into a grid tray.

Two jobs, two modes:

DATASET MODE (--count N): generates N trays and writes them as a ready-to-
train YOLO dataset (images + label files + data.yaml). Because the
generator places every part itself, it knows every box and class -- so the
"months of hand-labeling" a variant detector normally needs costs nothing.
    python3 make_variant_tray.py --count 180

DEMO MODE (default): generates one tray + a ground-truth JSON sidecar,
for feeding the scan pipeline something it has never seen.
    python3 make_variant_tray.py
    python3 make_variant_tray.py --rows 4 --cols 5 --empties 3

Note on realism: nut tiles have dark backgrounds, screw tiles white ones,
so a model could partly "cheat" by background color. Fine for the demo --
real part variants will be photographed on one consistent tray, which
removes the shortcut and, if anything, makes the task cleaner.
"""

import argparse
import json
import random
import time
from pathlib import Path

import cv2
import numpy as np

DATA_ROOT = Path(__file__).parent.parent / "training data"
DEMO_DIR = Path(__file__).parent.parent / "demo" / "trays"
DATASET_DIR = DATA_ROOT / "yolo_dataset_variants"

# Variant name -> folders of source images. Any condition (good or
# defective) works: this model identifies WHICH part, not whether it's ok.
VARIANT_SOURCES = {
    "metal_nut": ["metal_nut/train/good", "metal_nut/test/good"],
    "screw": ["screw/train/good", "screw/test/good"],
}
VARIANTS = list(VARIANT_SOURCES)  # index = YOLO class id

CELL = 320           # variant ID doesn't need the 700px defect-level detail
TRAY_BG = (38, 40, 44)
SLOT_RING = (55, 58, 63)


def load_pools():
    pools = {}
    for variant, folders in VARIANT_SOURCES.items():
        paths = []
        for folder in folders:
            paths += sorted((DATA_ROOT / folder).glob("*.png"))
        if not paths:
            raise SystemExit(f"No images found for variant {variant!r}")
        pools[variant] = paths
    return pools


def make_empty_cell():
    cell = np.full((CELL, CELL, 3), TRAY_BG, dtype=np.uint8)
    cv2.circle(cell, (CELL // 2, CELL // 2), int(CELL * 0.38), SLOT_RING, 2)
    return cell


def build_tray(rows, cols, n_empties, pools, rng):
    n_cells = rows * cols
    if n_empties >= n_cells:
        raise SystemExit("more empties than cells")

    slots = [None] * n_empties
    slots += [rng.choice(VARIANTS) for _ in range(n_cells - n_empties)]
    rng.shuffle(slots)

    tray = np.full((rows * CELL, cols * CELL, 3), TRAY_BG, dtype=np.uint8)
    cells = []
    for idx, variant in enumerate(slots):
        r, c = divmod(idx, cols)
        y, x = r * CELL, c * CELL
        if variant is None:
            tile = make_empty_cell()
        else:
            src = rng.choice(pools[variant])
            tile = cv2.resize(cv2.imread(str(src)), (CELL, CELL), interpolation=cv2.INTER_AREA)
        tray[y:y + CELL, x:x + CELL] = tile
        cells.append({"row": r, "col": c, "variant": variant,
                      "box": [x, y, x + CELL, y + CELL]})
    return tray, cells


def yolo_label_lines(cells, img_w, img_h):
    """One YOLO line per occupied cell: class x_center y_center w h (0-1)."""
    lines = []
    for cell in cells:
        if cell["variant"] is None:
            continue
        x0, y0, x1, y1 = cell["box"]
        lines.append(
            f"{VARIANTS.index(cell['variant'])} "
            f"{(x0 + x1) / 2 / img_w:.6f} {(y0 + y1) / 2 / img_h:.6f} "
            f"{(x1 - x0) / img_w:.6f} {(y1 - y0) / img_h:.6f}"
        )
    return lines


def dataset_mode(count, rng, pools):
    import shutil
    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)
    n_val = max(1, int(count * 0.2))

    for i in range(count):
        split = "val" if i < n_val else "train"
        rows = rng.choice([3, 3, 4])         # mostly 3x4, sometimes bigger
        cols = rng.choice([4, 4, 5])
        n_empties = rng.randint(0, 3)
        tray, cells = build_tray(rows, cols, n_empties, pools, rng)

        img_dir = DATASET_DIR / "images" / split
        lbl_dir = DATASET_DIR / "labels" / split
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        stem = f"tray_{i:04d}"
        cv2.imwrite(str(img_dir / f"{stem}.png"), tray)
        h, w = tray.shape[:2]
        (lbl_dir / f"{stem}.txt").write_text("\n".join(yolo_label_lines(cells, w, h)))

    (DATASET_DIR / "data.yaml").write_text(
        f"path: {DATASET_DIR.resolve()}\ntrain: images/train\nval: images/val\n"
        f"names:\n" + "".join(f"  {i}: {v}\n" for i, v in enumerate(VARIANTS))
    )
    print(f"dataset: {count - n_val} train + {n_val} val trays -> {DATASET_DIR}")
    print("NOTE: data.yaml embeds this machine's absolute path -- regenerate "
          "(or fix the path line) if the dataset moves to another machine.")


def demo_mode(rows, cols, empties, rng, pools):
    tray, cells = build_tray(rows, cols, empties, pools, rng)
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    img_path = DEMO_DIR / f"variant_tray_{stamp}.png"
    cv2.imwrite(str(img_path), tray)
    counts = {v: sum(1 for c in cells if c["variant"] == v) for v in VARIANTS}
    (DEMO_DIR / f"variant_tray_{stamp}.json").write_text(json.dumps(
        {"rows": rows, "cols": cols, "cell_px": CELL, "counts": counts, "cells": cells}, indent=2))
    print(f"Tray: {rows}x{cols} -> {img_path}")
    print("Contents:", ", ".join(f"{n} {v}" for v, n in counts.items()),
          f"+ {sum(1 for c in cells if c['variant'] is None)} empty")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, help="dataset mode: number of trays to generate")
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--empties", type=int, default=1)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    pools = load_pools()
    if args.count:
        dataset_mode(args.count, rng, pools)
    else:
        demo_mode(args.rows, args.cols, args.empties, rng, pools)


if __name__ == "__main__":
    main()
