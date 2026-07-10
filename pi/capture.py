"""
Day 1: manual-trigger camera capture for the lathe part inspection pipeline.

Run this on the Raspberry Pi 5 with the Camera Module attached.
Press Enter to capture an image; press 'q' + Enter to quit.

This intentionally does NOT auto-trigger yet -- Day 2 replaces the manual
keypress with a motion-based "part is ready" detector that calls the same
capture_image() function below, so nothing here gets thrown away.
"""

import time
from datetime import datetime
from pathlib import Path

from picamera2 import Picamera2

CAPTURE_DIR = Path(__file__).parent / "captures"
CAPTURE_DIR.mkdir(exist_ok=True)


def init_camera(resolution=(1640, 1232)):
    """
    Configure the camera for still capture.

    1640x1232 is the Camera Module's full-FOV, 2x2-binned mode -- a good
    balance of detail vs. file size/processing time to start with. Raise
    this once the pipeline works end-to-end if small defects need more
    resolution to show up in the diff.
    """
    picam2 = Picamera2()
    config = picam2.create_still_configuration(main={"size": resolution})
    picam2.configure(config)
    picam2.start()
    time.sleep(2)  # let auto-exposure/white-balance settle before first capture
    return picam2


def capture_image(picam2, label="part"):
    """Capture one still image and save it with a timestamped filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filepath = CAPTURE_DIR / f"{label}_{timestamp}.jpg"
    picam2.capture_file(str(filepath))
    return filepath


def main():
    print("Initializing camera...")
    picam2 = init_camera()
    print("Camera ready. Press Enter to capture, 'q' + Enter to quit.")

    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd == "q":
                break
            filepath = capture_image(picam2)
            print(f"Saved: {filepath}")
    finally:
        picam2.stop()
        print("Camera stopped.")


if __name__ == "__main__":
    main()
