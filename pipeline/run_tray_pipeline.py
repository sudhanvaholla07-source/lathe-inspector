"""
Tray pipeline: take one photo of a whole tray of parts arranged in a fixed
grid, classify every slot, and submit counts + an annotated overview to the
backend as a single inspection.

How it differs from run_pipeline.py (one part per photo): instead of one
verdict per image, we slice the image into its known grid cells and answer
three questions -- which slots are occupied, how many parts are there, and
which ones are defective. The fixed grid is what keeps this cheap: no object
detection is needed to *find* the parts, because the tray design already
tells us where every part can be.

Per cell the logic is:
  1. Empty check -- an empty slot is nearly uniform (grayscale std-dev < ~15)
     while any cell holding a nut is heavily textured (std-dev ~40). Measured
     on generated trays; tune EMPTY_STD_THRESHOLD if the real tray differs.
  2. Defect check -- the existing single-nut YOLO model runs on the cell
     crop. This works because each 320px cell crop looks like exactly what
     the model was trained on: one nut filling the frame. Boxes => FAIL.

Counts (total/pass/fail/empty) travel to the backend in a `tray` JSON field;
the tray's overall result is FAIL if any slot failed, else PASS.

Usage:
    python3 run_tray_pipeline.py ../demo/trays/tray_XXXX.jpg
    python3 run_tray_pipeline.py photo.jpg --rows 3 --cols 4
    python3 run_tray_pipeline.py photo.jpg --dry-run   # no backend submit

Grid size is read from the tray's ground-truth JSON sidecar if one sits next
to the image (make_tray.py writes one); otherwise pass --rows/--cols.
Same env vars as run_pipeline.py (BACKEND_URL, BACKEND_EMAIL, ...).
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import requests
from ultralytics import YOLO

# Reuse the auth + lookup plumbing from the single-part pipeline -- the
# backend handshake is identical, only the payload differs.
from run_pipeline import (
    BACKEND_URL, PART_TYPE_NAME, WEIGHTS, CONFIDENCE_THRESHOLD,
    RESULTS_DIR, login, get_part_type,
)

EMPTY_STD_THRESHOLD = 15.0

# BGR colors for the annotated overview
COLORS = {"PASS": (90, 200, 90), "FAIL": (70, 70, 230), "EMPTY": (130, 130, 130)}


def load_grid(photo_path, args):
    """Grid size from the sidecar JSON if present, else CLI args."""
    sidecar = Path(photo_path).with_suffix(".json")
    if sidecar.exists():
        meta = json.loads(sidecar.read_text())
        return meta["rows"], meta["cols"]
    if args.rows and args.cols:
        return args.rows, args.cols
    raise SystemExit("No ground-truth sidecar found -- pass --rows and --cols")


def slice_cells(image, rows, cols):
    """Cut the tray photo into rows*cols equal cells. Returns (r, c, crop,
    pixel-box) for each. Equal division is valid because the camera is fixed
    relative to the tray -- with a real rig, add a one-time corner-alignment
    calibration here instead."""
    h, w = image.shape[:2]
    ch, cw = h // rows, w // cols
    for r in range(rows):
        for c in range(cols):
            y, x = r * ch, c * cw
            yield r, c, image[y:y + ch, x:x + cw], (x, y, x + cw, y + ch)


def classify_cell(crop, model):
    """One slot -> EMPTY / PASS / FAIL (+ confidence)."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if float(gray.std()) < EMPTY_STD_THRESHOLD:
        return "EMPTY", 0.0

    result = model.predict(crop, imgsz=640, conf=CONFIDENCE_THRESHOLD, verbose=False)[0]
    if len(result.boxes) == 0:
        return "PASS", 0.0
    return "FAIL", max(float(b.conf) for b in result.boxes)


def annotate(image, cell_results, counts):
    """Overview image: color-coded border per slot + a counts banner. This is
    the one artifact a human needs to glance at -- which slots to pull."""
    out = image.copy()
    for cell in cell_results:
        x0, y0, x1, y1 = cell["box"]
        color = COLORS[cell["result"]]
        # Scale line/text with cell size so annotations stay readable
        # whether cells are 320px or 700px.
        cw = x1 - x0
        thick = max(4, cw // 60)
        font = cw / 350.0
        cv2.rectangle(out, (x0 + thick, y0 + thick), (x1 - thick, y1 - thick), color, thick)
        tag = cell["result"] if cell["result"] != "FAIL" else f"FAIL {cell['score']:.2f}"
        cv2.putText(out, tag, (x0 + thick * 3, y0 + int(cw * 0.14)),
                    cv2.FONT_HERSHEY_SIMPLEX, font, color, max(2, thick // 2), cv2.LINE_AA)

    banner = (f"parts: {counts['total']}   pass: {counts['pass']}   "
              f"fail: {counts['fail']}   empty: {counts['empty']}")
    bar_h = max(70, out.shape[0] // 20)
    bar = np.full((bar_h, out.shape[1], 3), (25, 26, 29), dtype=np.uint8)
    cv2.putText(bar, banner, (20, int(bar_h * 0.68)), cv2.FONT_HERSHEY_SIMPLEX,
                bar_h / 60.0, (235, 235, 235), max(2, bar_h // 30), cv2.LINE_AA)
    return np.vstack([bar, out])


def submit_tray(token, part_type_id, photo_path, annotated_path, verdict, score, tray):
    headers = {"Authorization": f"Bearer {token}"}
    with open(photo_path, "rb") as captured, open(annotated_path, "rb") as annotated:
        resp = requests.post(
            f"{BACKEND_URL}/inspections",
            headers=headers,
            data={
                "partTypeId": part_type_id, "result": verdict,
                "score": str(score), "method": "YOLO",
                "tray": json.dumps(tray),
            },
            files={"capturedImage": captured, "diffImage": annotated},
        )
    resp.raise_for_status()
    return resp.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--rows", type=int)
    ap.add_argument("--cols", type=int)
    ap.add_argument("--dry-run", action="store_true", help="analyze only, don't submit")
    args = ap.parse_args()

    image = cv2.imread(args.photo)
    if image is None:
        raise SystemExit(f"Couldn't read {args.photo} as an image")
    rows, cols = load_grid(args.photo, args)
    print(f"Tray grid: {rows}x{cols}")

    # Load the model once, not per cell -- model load dominates runtime.
    model = YOLO(str(WEIGHTS))

    cell_results = []
    for r, c, crop, box in slice_cells(image, rows, cols):
        verdict, score = classify_cell(crop, model)
        cell_results.append({"row": r, "col": c, "result": verdict,
                             "score": round(score, 3), "box": box})
        print(f"  [{r},{c}] {verdict}" + (f" ({score:.2f})" if verdict == "FAIL" else ""))

    counts = {
        "rows": rows, "cols": cols,
        "empty": sum(1 for x in cell_results if x["result"] == "EMPTY"),
        "pass": sum(1 for x in cell_results if x["result"] == "PASS"),
        "fail": sum(1 for x in cell_results if x["result"] == "FAIL"),
    }
    counts["total"] = counts["pass"] + counts["fail"]

    overall = "FAIL" if counts["fail"] > 0 else "PASS"
    overall_score = max((x["score"] for x in cell_results), default=0.0)

    RESULTS_DIR.mkdir(exist_ok=True)
    annotated_path = RESULTS_DIR / f"{Path(args.photo).stem}_tray_annotated.jpg"
    cv2.imwrite(str(annotated_path), annotate(image, cell_results, counts))

    print(f"\nCounts: {counts['total']} parts -- {counts['pass']} pass, "
          f"{counts['fail']} fail, {counts['empty']} empty slots")
    print(f"Tray verdict: {overall}")
    print(f"Annotated overview: {annotated_path}")

    if args.dry_run:
        print("Dry run -- not submitting.")
        return

    print("Submitting to backend...")
    token = login()
    part_type = get_part_type(token)
    tray_payload = {**counts, "cells": cell_results}
    inspection = submit_tray(token, part_type["id"], args.photo, annotated_path,
                             overall, overall_score, tray_payload)
    print(f"Inspection saved: {inspection['id']}")


if __name__ == "__main__":
    main()
