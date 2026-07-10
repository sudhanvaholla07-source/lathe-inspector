"""
Convert an MVTec AD category (pixel masks) into YOLO detection format
(bounding boxes). Originally written for metal_nut; now parameterized so
each new part type (screw, ...) reuses the same conversion.

Why this step exists: MVTec ships ground-truth as a black-and-white mask
per defective image (white = defective pixels). YOLO wants a bounding box
per defect instead. This script finds the white blob(s) in each mask,
draws the tightest rectangle around each one, and writes that out as a
YOLO label line: `class_id x_center y_center width height`, all normalized
to 0-1 by image size (that normalization is what lets one label file work
regardless of the image's actual resolution).

"good" (non-defective) images get an empty label file -- YOLO reads that
as "no objects here," which is exactly what a detector needs to see during
training to learn what a clean part looks like versus a defective one.

Usage:
    python3 convert_mvtec_to_yolo.py                     # metal_nut (default)
    python3 convert_mvtec_to_yolo.py --category screw
"""

import argparse
import random
import shutil
from pathlib import Path

import cv2

# Defect class lists per MVTec category = its test/ subfolder names minus
# "good". Class order matters: it defines the class ids the model learns,
# and everything downstream (pipelines, CLASS_NAMES on the Pi) must match.
CATEGORY_CLASSES = {
    "metal_nut": ["bent", "color", "flip", "scratch"],
    "screw": ["manipulated_front", "scratch_head", "scratch_neck", "thread_side", "thread_top"],
}

ap = argparse.ArgumentParser()
ap.add_argument("--category", default="metal_nut", choices=sorted(CATEGORY_CLASSES))
args = ap.parse_args()

# SRC: where you extracted <category>.tar.xz -- right next to this script.
# OUT: the converted YOLO-ready dataset. metal_nut keeps its original
# un-suffixed folder name ("yolo_dataset") so existing paths keep working;
# every other category gets yolo_dataset_<category>.
SRC = Path(__file__).parent / args.category
OUT = Path(__file__).parent / (
    "yolo_dataset" if args.category == "metal_nut" else f"yolo_dataset_{args.category}"
)

CLASSES = CATEGORY_CLASSES[args.category]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASSES)}

# How many "good" (no-defect) images to include as negative examples.
# Roughly balanced against the defect count, or the model mostly learns
# "predict nothing." Computed at runtime in main().
VAL_FRACTION = 0.2
SEED = 42


def mask_to_boxes(mask_path, img_w, img_h):
    """Find each defective blob in a mask and return its YOLO-format box."""
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for c in contours:
        if cv2.contourArea(c) < 20:  # skip tiny noise specks in the mask
            continue
        x, y, w, h = cv2.boundingRect(c)
        x_center = (x + w / 2) / img_w
        y_center = (y + h / 2) / img_h
        boxes.append((x_center, y_center, w / img_w, h / img_h))
    return boxes


def collect_examples():
    """Build a flat list of (image_path, class_name_or_None, mask_path_or_None)."""
    examples = []

    for cls in CLASSES:
        img_dir = SRC / "test" / cls
        mask_dir = SRC / "ground_truth" / cls
        for img_path in sorted(img_dir.glob("*.png")):
            mask_path = mask_dir / f"{img_path.stem}_mask.png"
            examples.append((img_path, cls, mask_path))

    n_defect = len(examples)

    # negative (no-defect) examples: MVTec's test/good + a sample of
    # train/good, sized to roughly match the defect count so the classes
    # stay balanced regardless of category.
    test_good = sorted((SRC / "test" / "good").glob("*.png"))
    for img_path in test_good:
        examples.append((img_path, None, None))

    n_good_from_train = max(0, n_defect - len(test_good))
    train_good = sorted((SRC / "train" / "good").glob("*.png"))
    random.seed(SEED)
    sampled_good = random.sample(train_good, min(n_good_from_train, len(train_good)))
    for img_path in sampled_good:
        examples.append((img_path, None, None))

    return examples


def write_example(img_path, cls, mask_path, split):
    img_out_dir = OUT / "images" / split
    lbl_out_dir = OUT / "labels" / split
    img_out_dir.mkdir(parents=True, exist_ok=True)
    lbl_out_dir.mkdir(parents=True, exist_ok=True)

    # Keep filenames unique: every MVTec subfolder restarts numbering at
    # 000.png, so "good" images from test/good and train/good would
    # otherwise collide (both become good_000.png, silently overwriting
    # each other). Tagging with the split-source folder name fixes that.
    source_tag = img_path.parent.parent.name  # "test" or "train"
    prefix = cls if cls else f"good-{source_tag}"
    stem = f"{prefix}_{img_path.stem}"

    dst_img = img_out_dir / f"{stem}.png"
    shutil.copyfile(img_path, dst_img)  # copyfile (not copy) avoids a chmod step
    # that this connected folder's mount doesn't permit

    label_lines = []
    if cls is not None:
        h, w = cv2.imread(str(img_path)).shape[:2]
        for x_c, y_c, bw, bh in mask_to_boxes(mask_path, w, h):
            label_lines.append(f"{CLASS_TO_ID[cls]} {x_c:.6f} {y_c:.6f} {bw:.6f} {bh:.6f}")

    (lbl_out_dir / f"{stem}.txt").write_text("\n".join(label_lines))


def main():
    if OUT.exists():
        shutil.rmtree(OUT)

    examples = collect_examples()
    random.seed(SEED)
    random.shuffle(examples)

    n_val = int(len(examples) * VAL_FRACTION)
    val_examples = examples[:n_val]
    train_examples = examples[n_val:]

    for img_path, cls, mask_path in train_examples:
        write_example(img_path, cls, mask_path, "train")
    for img_path, cls, mask_path in val_examples:
        write_example(img_path, cls, mask_path, "val")

    data_yaml = OUT / "data.yaml"
    data_yaml.write_text(
        f"path: {OUT}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n" + "".join(f"  {i}: {name}\n" for i, name in enumerate(CLASSES))
    )

    print(f"train examples: {len(train_examples)}")
    print(f"val examples:   {len(val_examples)}")
    print(f"wrote dataset to: {OUT}")
    print(f"wrote config to:  {data_yaml}")


if __name__ == "__main__":
    main()
