"""
Probe: run ONE image through the compiled HEF on the Hailo chip and print
the raw output structure.

Why this exists: before porting the tray pipeline to the Pi, we need to see
exactly what the chip returns -- the HEF was compiled with NMS baked in, so
the output should be per-class detection lists, but the precise nesting,
coordinate convention (corner order? normalized 0-1 or pixels?), and dtype
are best observed rather than assumed. This script prints all of it, plus a
best-guess decode, so the real pipeline's parser gets built on facts.

Usage (on the Pi):
    python3 hailo_probe.py test_good.png
    python3 hailo_probe.py test_scratch.png
"""

import sys

import cv2
import numpy as np
from picamera2.devices import Hailo   # Pi-provided wrapper around HailoRT

HEF_PATH = "/home/sudhanva/lathe-inspector-pi/yolov11n.hef"
CLASS_NAMES = ["bent", "color", "flip", "scratch"]  # index = class id, from training data.yaml
MODEL_SIZE = 640


def describe(obj, indent=0):
    """Recursively print the shape/type of whatever the chip returned."""
    pad = "  " * indent
    if isinstance(obj, np.ndarray):
        print(f"{pad}ndarray shape={obj.shape} dtype={obj.dtype}")
        if obj.size and obj.ndim <= 2:
            print(f"{pad}  first row: {obj.reshape(-1, obj.shape[-1])[0] if obj.ndim > 1 else obj[:6]}")
    elif isinstance(obj, (list, tuple)):
        print(f"{pad}{type(obj).__name__} len={len(obj)}")
        for i, item in enumerate(obj):
            print(f"{pad}[{i}]:")
            describe(item, indent + 1)
    else:
        print(f"{pad}{type(obj).__name__}: {obj}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 hailo_probe.py path/to/image.png")
        sys.exit(1)

    image = cv2.imread(sys.argv[1])
    if image is None:
        raise SystemExit(f"Couldn't read {sys.argv[1]}")

    # Model expects 640x640 RGB; cv2 loads BGR, so convert.
    resized = cv2.resize(image, (MODEL_SIZE, MODEL_SIZE))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    with Hailo(HEF_PATH) as hailo:
        print(f"Input shape the HEF expects: {hailo.get_input_shape()}")
        results = hailo.run(rgb)

        # Everything below stays INSIDE the with-block: the result buffers
        # belong to the device, and reading them after it closes is a
        # use-after-free (learned via segfault). np.copy pulls the data into
        # normal Python-owned memory.
        print("\n===== RAW OUTPUT STRUCTURE =====")
        describe(results)
        results = [np.copy(np.asarray(r)) if np.asarray(r).size else np.empty((0, 5))
                   for r in results]

    # Best-guess decode: NMS-postprocessed YOLO HEFs usually return one array
    # per class, each row = [y0, x0, y1, x1, score] normalized 0-1.
    print("\n===== BEST-GUESS DECODE =====")
    try:
        for class_id, dets in enumerate(results):
            dets = np.asarray(dets).reshape(-1, 5) if np.asarray(dets).size else []
            for det in dets:
                y0, x0, y1, x1, score = det
                print(f"{CLASS_NAMES[class_id]:8s} score={score:.2f} "
                      f"box=({x0:.2f},{y0:.2f})-({x1:.2f},{y1:.2f})")
        print("(no lines above = no detections = a clean PASS image)")
    except Exception as e:
        print(f"Guess didn't fit the structure ({e}) -- the raw dump above is what matters.")


if __name__ == "__main__":
    main()
