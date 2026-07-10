"""
Convert KolektorSDD2 (commutator surface defects) into YOLO detection format.

Differences from the MVTec converter that justify a separate script:
- Layout: flat train/ and test/ folders where every image `NNNNN.png` has a
  sibling pixel mask `NNNNN_GT.png` (white = defect), instead of MVTec's
  per-defect-type folders.
- Classes: a single class, `defect`. Kolektor doesn't distinguish crack
  types, so neither can the model.
- Split: KSDD2 ships an official train/test split -- we keep it (their train
  -> our train, their test -> our val) so results stay comparable to
  published benchmarks on this dataset.
- Balance: only ~10% of images are defective. We keep ALL defective images
  and subsample the clean ones to roughly match, otherwise the model mostly
  learns "predict nothing" (same trick as the MVTec converter, but the
  imbalance here is much stronger).

Usage:
    python3 convert_kolektor_to_yolo.py
"""

import random
import shutil
from pathlib import Path

import cv2

SRC = Path(__file__).parent / "kolektor"
OUT = Path(__file__).parent / "yolo_dataset_kolektor"

CLASSES = ["defect"]
GOOD_PER_DEFECT = 1.5   # clean images kept per defective image
MIN_BLOB_AREA = 20      # ignore mask specks smaller than this (pixels)
SEED = 42


def mask_to_boxes(mask, img_w, img_h):
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        if cv2.contourArea(c) < MIN_BLOB_AREA:
            continue
        x, y, w, h = cv2.boundingRect(c)
        boxes.append(((x + w / 2) / img_w, (y + h / 2) / img_h, w / img_w, h / img_h))
    return boxes


def collect(split_dir):
    """Returns (defective, clean) lists of (image_path, boxes)."""
    defective, clean = [], []
    for img_path in sorted(split_dir.glob("*.png")):
        if img_path.stem.endswith("_GT"):
            continue
        mask_path = img_path.with_name(f"{img_path.stem}_GT.png")
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            print(f"warning: no mask for {img_path.name}, skipping")
            continue
        h, w = mask.shape[:2]
        boxes = mask_to_boxes(mask, w, h) if mask.max() > 0 else []
        (defective if boxes else clean).append((img_path, boxes))
    return defective, clean


def write_split(examples, split):
    img_dir = OUT / "images" / split
    lbl_dir = OUT / "labels" / split
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)
    for img_path, boxes in examples:
        shutil.copyfile(img_path, img_dir / img_path.name)
        lines = [f"0 {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for x, y, w, h in boxes]
        (lbl_dir / f"{img_path.stem}.txt").write_text("\n".join(lines))


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    random.seed(SEED)

    for src_split, out_split in [("train", "train"), ("test", "val")]:
        defective, clean = collect(SRC / src_split)
        n_clean = min(len(clean), int(len(defective) * GOOD_PER_DEFECT))
        kept_clean = random.sample(clean, n_clean)
        examples = defective + kept_clean
        random.shuffle(examples)
        write_split(examples, out_split)
        print(f"{out_split}: {len(defective)} defective + {n_clean} clean "
              f"(subsampled from {len(clean)})")

    (OUT / "data.yaml").write_text(
        f"path: {OUT}\ntrain: images/train\nval: images/val\n"
        f"names:\n  0: defect\n"
    )
    print(f"wrote dataset to: {OUT}")


if __name__ == "__main__":
    main()
