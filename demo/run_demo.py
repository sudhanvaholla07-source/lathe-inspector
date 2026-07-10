"""
Run the trained defect-detection model on a single photo and save an
annotated copy showing what it found.

Usage:
    python3 run_demo.py path/to/photo.jpg

What this does, step by step:
1. Loads the photo you captured (e.g. pulled off the Pi with scp).
2. Crops it to a centered square. Why: every training photo is square
   with the part filling most of the frame. The Pi camera shoots
   rectangular (4:3) photos -- feeding that directly to the model would
   squash it into a square during resizing, distorting the part's shape
   in a way the model never saw during training. Cropping first avoids
   that distortion.
3. Runs the trained model (best.pt) on the cropped photo.
4. Draws boxes + labels + confidence scores directly on the image and
   saves it next to the original, plus prints a plain-text summary.
"""

import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

WEIGHTS = Path(__file__).parent.parent / "training data" / "runs" / "detect" / "runs" / "metal_nut" / "weights" / "best.pt"


def crop_to_square(image):
    h, w = image.shape[:2]
    side = min(h, w)
    top = (h - side) // 2
    left = (w - side) // 2
    return image[top:top + side, left:left + side]


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 run_demo.py path/to/photo.jpg")
        sys.exit(1)

    photo_path = Path(sys.argv[1])
    if not photo_path.exists():
        print(f"Can't find {photo_path}")
        sys.exit(1)

    if not WEIGHTS.exists():
        print(f"Can't find trained weights at {WEIGHTS}")
        print("Make sure train_yolo.py has finished running first.")
        sys.exit(1)

    image = cv2.imread(str(photo_path))
    if image is None:
        print(f"Couldn't read {photo_path} as an image.")
        sys.exit(1)

    square = crop_to_square(image)

    model = YOLO(str(WEIGHTS))
    results = model.predict(square, imgsz=640, conf=0.25, verbose=False)
    result = results[0]

    # annotated = the cropped photo with boxes/labels drawn on top
    annotated = result.plot()
    out_path = photo_path.parent / f"{photo_path.stem}_result{photo_path.suffix}"
    cv2.imwrite(str(out_path), annotated)

    n = len(result.boxes)
    if n == 0:
        print("No defects detected -- part looks OK.")
    else:
        print(f"{n} potential defect(s) detected:")
        for box in result.boxes:
            cls_name = model.names[int(box.cls)]
            conf = float(box.conf)
            print(f"  - {cls_name} (confidence: {conf:.0%})")

    print(f"\nAnnotated image saved to: {out_path}")


if __name__ == "__main__":
    main()
