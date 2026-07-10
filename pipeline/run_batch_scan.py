"""
Batch scan: photograph a tray, DETECT every part on it (no fixed grid
needed), count parts per variant, and file the scan into a labeled
production batch on the backend.

How this differs from the defect tray pipeline: run_tray_pipeline.py slices
a known grid and asks "is this part ok?" per cell. This script instead runs
the variant detector over the WHOLE image -- the model finds each part and
says which variant it is, so parts can sit anywhere and empty slots are
simply places where nothing was detected. That's the industry ask: count
and classify, don't judge. (The defect models remain available as a later
"inspect each detected part" second pass.)

Usage:
    python3 run_batch_scan.py tray.png --batch "Order 4521"
    python3 run_batch_scan.py tray.png --batch "Order 4521" --dry-run

The batch is looked up by label among OPEN batches and created if it
doesn't exist, so operators only ever think in labels, not ids.

Env vars: BACKEND_URL / BACKEND_EMAIL / BACKEND_PASSWORD as usual;
PART_TYPE_NAME defaults to "Batch Scan" (register it once on the Machines
page -- any reference image is fine, it isn't used here); WEIGHTS to
override the variant detector weights.
"""

import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np
import requests
from ultralytics import YOLO

from run_pipeline import BACKEND_URL, login

PART_TYPE_NAME = os.environ.get("PART_TYPE_NAME", "Batch Scan")
WEIGHTS = Path(os.environ.get(
    "WEIGHTS",
    str(Path(__file__).parent.parent
        / "training data" / "runs" / "detect" / "runs" / "variants" / "weights" / "best.pt"),
))
CONFIDENCE_THRESHOLD = 0.4   # variant ID is easy; a confident model should clear this
RESULTS_DIR = Path(__file__).parent / "results"


def get_part_type(token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BACKEND_URL}/part-types", headers=headers)
    resp.raise_for_status()
    for pt in resp.json():
        if pt["name"] == PART_TYPE_NAME:
            return pt
    raise RuntimeError(
        f"No part type named {PART_TYPE_NAME!r} registered. Add it once from "
        f"the dashboard's Machines page (any reference image is fine)."
    )


def find_or_create_batch(token, label):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BACKEND_URL}/batches?status=OPEN", headers=headers)
    resp.raise_for_status()
    for batch in resp.json():
        if batch["label"] == label:
            return batch
    resp = requests.post(f"{BACKEND_URL}/batches", headers=headers, json={"label": label})
    resp.raise_for_status()
    print(f"Opened new batch: {label}")
    return resp.json()


def detect_variants(image):
    """Full-image detection -> (per-variant counts, per-part details)."""
    model = YOLO(str(WEIGHTS))
    result = model.predict(image, imgsz=640, conf=CONFIDENCE_THRESHOLD, verbose=False)[0]
    names = result.names  # class id -> variant name (from training data.yaml)

    counts, parts = {}, []
    for box in result.boxes:
        variant = names[int(box.cls)]
        counts[variant] = counts.get(variant, 0) + 1
        x0, y0, x1, y1 = (int(v) for v in box.xyxy[0])
        parts.append({"variant": variant, "conf": round(float(box.conf), 3),
                      "box": [x0, y0, x1, y1]})
    return counts, parts


def annotate(image, parts, counts):
    out = image.copy()
    palette = [(90, 200, 90), (230, 160, 60), (200, 90, 200), (90, 160, 230)]
    variant_color = {}
    for p in parts:
        color = variant_color.setdefault(p["variant"], palette[len(variant_color) % len(palette)])
        x0, y0, x1, y1 = p["box"]
        cv2.rectangle(out, (x0, y0), (x1, y1), color, 4)
        cv2.putText(out, f"{p['variant']} {p['conf']:.2f}", (x0 + 8, y0 + 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)

    banner = "   ".join(f"{v}: {n}" for v, n in sorted(counts.items()))
    banner = f"total: {sum(counts.values())}   {banner}"
    bar_h = max(60, out.shape[0] // 20)
    bar = np.full((bar_h, out.shape[1], 3), (25, 26, 29), dtype=np.uint8)
    cv2.putText(bar, banner, (20, int(bar_h * 0.68)), cv2.FONT_HERSHEY_SIMPLEX,
                bar_h / 65.0, (235, 235, 235), max(2, bar_h // 30), cv2.LINE_AA)
    return np.vstack([bar, out])


def submit(token, part_type_id, batch_id, photo_path, annotated_path, counts, parts):
    tray = {"total": sum(counts.values()), "variants": counts, "cells": parts}
    mean_conf = (sum(p["conf"] for p in parts) / len(parts)) if parts else 0.0
    headers = {"Authorization": f"Bearer {token}"}
    with open(photo_path, "rb") as captured, open(annotated_path, "rb") as annotated:
        resp = requests.post(
            f"{BACKEND_URL}/inspections", headers=headers,
            data={"partTypeId": part_type_id, "result": "PASS",
                  "score": str(round(mean_conf, 3)), "method": "YOLO",
                  "tray": json.dumps(tray), "batchId": batch_id},
            files={"capturedImage": captured, "diffImage": annotated},
        )
    resp.raise_for_status()
    return resp.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--batch", required=True, help="batch label, e.g. 'Order 4521'")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    image = cv2.imread(args.photo)
    if image is None:
        raise SystemExit(f"Couldn't read {args.photo}")

    print("Detecting parts...")
    counts, parts = detect_variants(image)
    for v, n in sorted(counts.items()):
        print(f"  {v}: {n}")
    print(f"  total: {sum(counts.values())}")

    RESULTS_DIR.mkdir(exist_ok=True)
    annotated_path = RESULTS_DIR / f"{Path(args.photo).stem}_batch_annotated.jpg"
    cv2.imwrite(str(annotated_path), annotate(image, parts, counts))
    print(f"Annotated overview: {annotated_path}")

    if args.dry_run:
        print("Dry run -- not submitting.")
        return

    token = login()
    part_type = get_part_type(token)
    batch = find_or_create_batch(token, args.batch)
    inspection = submit(token, part_type["id"], batch["id"], args.photo,
                        annotated_path, counts, parts)
    print(f"Scan filed into batch {batch['label']!r}: {inspection['id']}")


if __name__ == "__main__":
    main()
