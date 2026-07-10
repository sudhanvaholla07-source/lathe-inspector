"""
Fine-tune YOLO11n on the converted metal_nut dataset.

Run convert_mvtec_to_yolo.py first -- this script expects its output
at /tmp/mvtec_extract/yolo_dataset/data.yaml (adjust DATA_YAML below if
you changed that path.)

Why yolo11n.pt (pretrained) here but not in the sandbox smoke test:
this loads a checkpoint pretrained on COCO (millions of everyday-object
images) and fine-tunes it on our ~180 nut images, instead of learning
from random weights. Pretrained features (edges, textures, shapes) transfer
across almost any object, so fine-tuning converges dramatically faster and
with far less data than training from scratch -- which is exactly why the
sandbox's from-scratch run only proved the pipeline runs, not that it
detects anything useful. Ultralytics auto-downloads yolo11n.pt from
GitHub on first run here, which needs a normal internet connection (the
sandbox this was prototyped in blocks that download).

Usage:
    python3 train_yolo.py                     # metal_nut (default)
    python3 train_yolo.py --category screw
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

ap = argparse.ArgumentParser()
ap.add_argument("--category", default="metal_nut")
args = ap.parse_args()

DATASET_DIR = (
    "yolo_dataset" if args.category == "metal_nut" else f"yolo_dataset_{args.category}"
)
DATA_YAML = Path(__file__).parent / DATASET_DIR / "data.yaml"


def main():
    if not DATA_YAML.exists():
        raise FileNotFoundError(
            f"{DATA_YAML} not found -- run convert_mvtec_to_yolo.py "
            f"--category {args.category} first."
        )

    model = YOLO("yolo11n.pt")  # pretrained checkpoint, downloaded on first run

    model.train(
        data=str(DATA_YAML),
        epochs=100,       # small dataset -- more epochs, rely on early stopping
        patience=20,      # stop early if val mAP stalls for 20 epochs
        imgsz=640,        # full resolution; bump down to 320 only if training is too slow
        batch=8,
        device="cpu",     # change to 0 if you have a CUDA GPU available
        project="runs",
        name=args.category,
    )

    print(f"Training complete. Best weights: runs/{args.category}/weights/best.pt")


if __name__ == "__main__":
    main()
