"""
Tray pipeline, Pi edition: same logic as pipeline/run_tray_pipeline.py, but
inference runs on the Hailo chip via the compiled HEF instead of ultralytics
on a laptop. With this script, the laptop is out of the loop entirely:
capture, inference, and backend submission all happen from the Pi.

Output format (verified with hailo_probe.py, not assumed): hailo.run()
returns a list with one ndarray per class [bent, color, flip, scratch],
each row = [y0, x0, y1, x1, score], coordinates normalized 0-1. NMS was
baked into the HEF at compile time, so no post-processing beyond a score
threshold is needed here.

Usage:
    python3 run_tray_pipeline_pi.py tray_photo.png --rows 3 --cols 4
    python3 run_tray_pipeline_pi.py tray_photo.png --dry-run

Environment variables:
    BACKEND_URL     e.g. http://192.168.1.50:4000  (your Mac's IP while the
                    backend still lives there -- localhost won't work from
                    the Pi, it means "the Pi itself")
    BACKEND_EMAIL / BACKEND_PASSWORD / PART_TYPE_NAME  same as laptop version
"""

import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np
import requests
from picamera2.devices import Hailo

HEF_PATH = os.environ.get("HEF_PATH", "/home/sudhanva/lathe-inspector-pi/yolov11n.hef")
CLASS_NAMES = ["bent", "color", "flip", "scratch"]
MODEL_SIZE = 640
CONFIDENCE_THRESHOLD = 0.25
EMPTY_STD_THRESHOLD = 15.0

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:4000")
BACKEND_EMAIL = os.environ.get("BACKEND_EMAIL", "pi@lathe.local")
BACKEND_PASSWORD = os.environ.get("BACKEND_PASSWORD", "change-me-please")
PART_TYPE_NAME = os.environ.get("PART_TYPE_NAME", "M8 Tee Nut")

RESULTS_DIR = Path(__file__).parent / "results"
COLORS = {"PASS": (90, 200, 90), "FAIL": (70, 70, 230), "EMPTY": (130, 130, 130)}


# ---------- backend plumbing (same handshake as the laptop scripts) ----------

def login():
    resp = requests.post(f"{BACKEND_URL}/auth/login",
                         json={"email": BACKEND_EMAIL, "password": BACKEND_PASSWORD})
    if resp.status_code == 200:
        return resp.json()["token"]
    signup = requests.post(f"{BACKEND_URL}/auth/signup", json={
        "email": BACKEND_EMAIL, "password": BACKEND_PASSWORD,
        "name": "Pi Capture Station", "role": "OPERATOR",
    })
    signup.raise_for_status()
    resp = requests.post(f"{BACKEND_URL}/auth/login",
                         json={"email": BACKEND_EMAIL, "password": BACKEND_PASSWORD})
    resp.raise_for_status()
    return resp.json()["token"]


def get_part_type(token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BACKEND_URL}/part-types", headers=headers)
    resp.raise_for_status()
    for pt in resp.json():
        if pt["name"] == PART_TYPE_NAME:
            return pt
    raise RuntimeError(f"No part type named {PART_TYPE_NAME!r} registered on the backend")


def submit_tray(token, part_type_id, photo_path, annotated_path, verdict, score, tray):
    headers = {"Authorization": f"Bearer {token}"}
    with open(photo_path, "rb") as captured, open(annotated_path, "rb") as annotated:
        resp = requests.post(
            f"{BACKEND_URL}/inspections", headers=headers,
            data={"partTypeId": part_type_id, "result": verdict,
                  "score": str(score), "method": "YOLO", "tray": json.dumps(tray)},
            files={"capturedImage": captured, "diffImage": annotated},
        )
    resp.raise_for_status()
    return resp.json()


# ---------- tray logic (identical concepts to the laptop version) ----------

def slice_cells(image, rows, cols):
    h, w = image.shape[:2]
    ch, cw = h // rows, w // cols
    for r in range(rows):
        for c in range(cols):
            y, x = r * ch, c * cw
            yield r, c, image[y:y + ch, x:x + cw], (x, y, x + cw, y + ch)


def classify_cell(crop, hailo):
    """One slot -> EMPTY / PASS / FAIL (+ confidence, defect class)."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if float(gray.std()) < EMPTY_STD_THRESHOLD:
        return "EMPTY", 0.0, None

    # Chip expects 640x640 RGB; crops are BGR at cell resolution.
    rgb = cv2.cvtColor(cv2.resize(crop, (MODEL_SIZE, MODEL_SIZE)), cv2.COLOR_BGR2RGB)
    results = hailo.run(rgb)

    best_score, best_class = 0.0, None
    for class_id, dets in enumerate(results):
        dets = np.asarray(dets)
        for det in dets.reshape(-1, 5) if dets.size else []:
            score = float(det[4])
            if score >= CONFIDENCE_THRESHOLD and score > best_score:
                best_score, best_class = score, CLASS_NAMES[class_id]

    if best_class is None:
        return "PASS", 0.0, None
    return "FAIL", best_score, best_class


def annotate(image, cell_results, counts):
    out = image.copy()
    for cell in cell_results:
        x0, y0, x1, y1 = cell["box"]
        color = COLORS[cell["result"]]
        cw = x1 - x0
        thick = max(4, cw // 60)
        font = cw / 350.0
        cv2.rectangle(out, (x0 + thick, y0 + thick), (x1 - thick, y1 - thick), color, thick)
        tag = cell["result"]
        if cell["result"] == "FAIL":
            tag = f"{cell.get('defect') or 'FAIL'} {cell['score']:.2f}"
        cv2.putText(out, tag, (x0 + thick * 3, y0 + int(cw * 0.14)),
                    cv2.FONT_HERSHEY_SIMPLEX, font, color, max(2, thick // 2), cv2.LINE_AA)

    banner = (f"parts: {counts['total']}   pass: {counts['pass']}   "
              f"fail: {counts['fail']}   empty: {counts['empty']}")
    bar_h = max(70, out.shape[0] // 20)
    bar = np.full((bar_h, out.shape[1], 3), (25, 26, 29), dtype=np.uint8)
    cv2.putText(bar, banner, (20, int(bar_h * 0.68)), cv2.FONT_HERSHEY_SIMPLEX,
                bar_h / 60.0, (235, 235, 235), max(2, bar_h // 30), cv2.LINE_AA)
    return np.vstack([bar, out])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    image = cv2.imread(args.photo)
    if image is None:
        raise SystemExit(f"Couldn't read {args.photo}")

    print(f"Tray grid: {args.rows}x{args.cols}  |  HEF: {HEF_PATH}")
    cell_results = []
    # One device open for the whole tray; all reads happen inside the
    # with-block (device-owned buffers -- see hailo_probe.py).
    with Hailo(HEF_PATH) as hailo:
        for r, c, crop, box in slice_cells(image, args.rows, args.cols):
            verdict, score, defect = classify_cell(crop, hailo)
            cell_results.append({"row": r, "col": c, "result": verdict,
                                 "score": round(score, 3), "defect": defect, "box": box})
            extra = f" ({defect} {score:.2f})" if verdict == "FAIL" else ""
            print(f"  [{r},{c}] {verdict}{extra}")

    counts = {
        "rows": args.rows, "cols": args.cols,
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
          f"{counts['fail']} fail, {counts['empty']} empty")
    print(f"Tray verdict: {overall}")
    print(f"Annotated overview: {annotated_path}")

    if args.dry_run:
        print("Dry run -- not submitting.")
        return

    print(f"Submitting to backend at {BACKEND_URL} ...")
    token = login()
    part_type = get_part_type(token)
    inspection = submit_tray(token, part_type["id"], args.photo, annotated_path,
                             overall, overall_score, {**counts, "cells": cell_results})
    print(f"Inspection saved: {inspection['id']}")


if __name__ == "__main__":
    main()
