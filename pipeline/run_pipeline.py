"""
End-to-end pipeline: check a photo is actually the expected product, run
the trained model to decide pass/fail, and upload the result to the backend.

This is the script that (eventually) runs on the Pi after every capture --
today it's tested by pointing it at a photo file manually. Once the T-nut
and camera rig are ready, the "load a photo from disk" step gets replaced
by calling capture.py's capture_image() directly instead of reading a path
off the command line -- everything after that stays the same.

Before running this against a new part type, register it (with a real
reference image) from the dashboard's Machines page first -- this script no
longer creates part types on the fly.

Usage:
    python3 run_pipeline.py path/to/photo.jpg

Environment variables (set these, or edit the defaults below):
    BACKEND_URL           e.g. http://localhost:4000
    BACKEND_EMAIL         account this script logs in as (created
                          automatically on first run if it doesn't exist yet)
    BACKEND_PASSWORD
    PART_TYPE_NAME        must match an already-registered part type
    SIMILARITY_THRESHOLD  0-1, how close a photo must be to the reference
                          image to be treated as the real product at all
"""

import os
import sys
from pathlib import Path

import cv2
import numpy as np
import requests
from ultralytics import YOLO

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:4000")
BACKEND_EMAIL = os.environ.get("BACKEND_EMAIL", "pi@lathe.local")
BACKEND_PASSWORD = os.environ.get("BACKEND_PASSWORD", "change-me-please")
PART_TYPE_NAME = os.environ.get("PART_TYPE_NAME", "M8 Tee Nut")

# Which trained model to run. Default stays the metal_nut model; point the
# WEIGHTS env var at another run's best.pt to inspect a different part type
# (e.g. the Kolektor commutator model) without touching this file.
WEIGHTS = Path(os.environ.get(
    "WEIGHTS",
    str(Path(__file__).parent.parent
        / "training data" / "runs" / "detect" / "runs" / "metal_nut" / "weights" / "best.pt"),
))
CONFIDENCE_THRESHOLD = 0.25

# Below this histogram-correlation score against the part type's reference
# image, we don't even bother running YOLO -- the photo doesn't look enough
# like the expected part to be worth scoring, so it gets REJECTED instead of
# PASS/FAIL. See check_is_product() for what this number means; tune via
# SIMILARITY_THRESHOLD if real-world lighting makes this too strict/loose.
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.5"))


def crop_to_square(image):
    h, w = image.shape[:2]
    side = min(h, w)
    top = (h - side) // 2
    left = (w - side) // 2
    return image[top:top + side, left:left + side]


def login():
    """
    Logs into the backend and returns a bearer token. If the account
    doesn't exist yet, creates it first -- the Pi needs its own account
    just like a human dashboard user would, and this makes first-time
    setup a non-event instead of a manual step.
    """
    resp = requests.post(f"{BACKEND_URL}/auth/login", json={
        "email": BACKEND_EMAIL, "password": BACKEND_PASSWORD,
    })
    if resp.status_code == 200:
        return resp.json()["token"]

    print("No account for this Pi yet -- creating one.")
    signup = requests.post(f"{BACKEND_URL}/auth/signup", json={
        "email": BACKEND_EMAIL, "password": BACKEND_PASSWORD,
        "name": "Pi Capture Station", "role": "OPERATOR",
    })
    signup.raise_for_status()

    resp = requests.post(f"{BACKEND_URL}/auth/login", json={
        "email": BACKEND_EMAIL, "password": BACKEND_PASSWORD,
    })
    resp.raise_for_status()
    return resp.json()["token"]


def get_part_type(token, name=PART_TYPE_NAME):
    """
    Looks up an already-registered part type by name. Registering a part
    type -- choosing its real reference (known-good) image -- is now a
    deliberate one-time setup step done through the dashboard's Machines
    page, not something this script should do on the fly. It used to
    self-bootstrap by reusing whatever test photo you passed in as the
    reference image, which quietly broke the point of this whole file:
    every submitted photo compared "successfully" against itself. Fail
    loudly instead, so a missing part type is obvious rather than silently
    wrong.
    """
    headers = {"Authorization": f"Bearer {token}"}
    existing = requests.get(f"{BACKEND_URL}/part-types", headers=headers)
    existing.raise_for_status()
    for pt in existing.json():
        if pt["name"] == name:
            return pt
    raise RuntimeError(
        f"No part type named {name!r} is registered yet. Add it (with a real "
        f"reference image) from the dashboard's Machines page first, or set "
        f"PART_TYPE_NAME to match an existing one."
    )


def fetch_reference_image(part_type):
    """
    Downloads the part type's reference image from the backend and decodes
    it into the same in-memory format cv2.imread() would give us, so it can
    be compared against the freshly captured photo.
    """
    url = f"{BACKEND_URL}{part_type['referenceImageUrl']}"
    resp = requests.get(url)
    resp.raise_for_status()
    array = np.frombuffer(resp.content, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Couldn't decode reference image from {url}")
    return image


def check_is_product(captured_square, reference_square):
    """
    A cheap sanity check that runs *before* YOLO: is this photo even of the
    right kind of object, or did the camera pick up a face, an empty bench,
    someone's hand, etc.? YOLO was only ever trained to find defects on a
    metal nut -- it was never shown "not a nut" examples, so it has no way
    to say "this isn't a product at all" (it'll happily draw a defect box on
    a photo of your face, since that's the closest thing to its training
    distribution it can produce).

    Instead of training a whole separate classifier for this (which would
    need its own "not a product" dataset we don't have), we reuse the
    reference image every part type already has: convert both images to HSV
    color histograms and measure how correlated they are. A real part under
    the same rig/lighting should look broadly similar in color/shape
    distribution to its reference photo; a face or an empty background
    won't. This is exactly the classical "diffing" approach from the
    original project plan, now serving as a gate in front of YOLO rather
    than the primary detector.
    """
    ref_hsv = cv2.cvtColor(reference_square, cv2.COLOR_BGR2HSV)
    cap_hsv = cv2.cvtColor(captured_square, cv2.COLOR_BGR2HSV)

    ref_hist = cv2.calcHist([ref_hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
    cap_hist = cv2.calcHist([cap_hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
    cv2.normalize(ref_hist, ref_hist)
    cv2.normalize(cap_hist, cap_hist)

    similarity = cv2.compareHist(ref_hist, cap_hist, cv2.HISTCMP_CORREL)
    return similarity >= SIMILARITY_THRESHOLD, similarity


RESULTS_DIR = Path(__file__).parent / "results"


def run_yolo_inference(square, photo_path):
    """Runs the defect detector. Only called once check_is_product() has
    already confirmed the photo is worth scoring."""
    model = YOLO(str(WEIGHTS))
    results = model.predict(square, imgsz=640, conf=CONFIDENCE_THRESHOLD, verbose=False)
    result = results[0]

    annotated = result.plot()
    RESULTS_DIR.mkdir(exist_ok=True)
    annotated_path = RESULTS_DIR / f"{Path(photo_path).stem}_annotated.jpg"
    cv2.imwrite(str(annotated_path), annotated)

    if len(result.boxes) == 0:
        return "PASS", 0.0, annotated_path

    confidences = [float(b.conf) for b in result.boxes]
    return "FAIL", max(confidences), annotated_path


def save_rejected_snapshot(square, photo_path):
    """No YOLO annotation makes sense for a rejected (not-a-product) photo --
    there's nothing to draw boxes on. Just save the plain square crop so
    there's still something to look at in the dashboard's diff-image slot."""
    RESULTS_DIR.mkdir(exist_ok=True)
    snapshot_path = RESULTS_DIR / f"{Path(photo_path).stem}_rejected.jpg"
    cv2.imwrite(str(snapshot_path), square)
    return snapshot_path


def submit_inspection(token, part_type_id, photo_path, annotated_path, verdict, score, method):
    headers = {"Authorization": f"Bearer {token}"}
    with open(photo_path, "rb") as captured, open(annotated_path, "rb") as annotated:
        resp = requests.post(
            f"{BACKEND_URL}/inspections",
            headers=headers,
            data={"partTypeId": part_type_id, "result": verdict, "score": str(score), "method": method},
            files={"capturedImage": captured, "diffImage": annotated},
        )
    resp.raise_for_status()
    return resp.json()


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 run_pipeline.py path/to/photo.jpg")
        sys.exit(1)
    photo_path = sys.argv[1]

    print(f"Backend: {BACKEND_URL}")
    print("Logging in...")
    token = login()

    print(f"Looking up part type {PART_TYPE_NAME!r}...")
    part_type = get_part_type(token)

    image = cv2.imread(str(photo_path))
    if image is None:
        raise ValueError(f"Couldn't read {photo_path} as an image")
    captured_square = crop_to_square(image)
    reference_square = crop_to_square(fetch_reference_image(part_type))

    print("Checking this is actually the expected product...")
    is_product, similarity = check_is_product(captured_square, reference_square)
    print(f"Similarity to reference: {similarity:.2f} (threshold {SIMILARITY_THRESHOLD})")

    if not is_product:
        verdict, score, method = "REJECTED", similarity, "DIFF"
        annotated_path = save_rejected_snapshot(captured_square, photo_path)
        print("Result: REJECTED -- doesn't look like the registered part, skipping YOLO")
    else:
        print("Running inference...")
        # Feed YOLO the FULL image, not the square crop. The square crop is
        # only for the histogram gate (where both sides get cropped alike).
        # Cropping a non-square part (e.g. commutator strips) before
        # inference mangles it into something outside the training
        # distribution and produces phantom defects.
        verdict, score, annotated_path = run_yolo_inference(image, photo_path)
        method = "YOLO"
        print(f"Result: {verdict}  (score: {score:.2f})")

    print("Submitting to backend...")
    inspection = submit_inspection(token, part_type["id"], photo_path, annotated_path, verdict, score, method)
    print(f"Inspection saved: {inspection['id']}")
    print(f"View the full feed at: GET {BACKEND_URL}/inspections")


if __name__ == "__main__":
    main()
