# Training — metal_nut dataset (dry run)

## What's here

- `convert_mvtec_to_yolo.py` — converts MVTec AD's pixel masks into YOLO bounding-box labels. Run this first; it expects the extracted dataset in a folder named `metal_nut` right next to this script, and writes the YOLO-format dataset to a new `yolo_dataset` folder, also right next to this script.
- `train_yolo.py` — fine-tunes a pretrained `yolo11n.pt` checkpoint on the converted dataset. This is the one to actually run for a real result.
- `smoketest_results/` — proof that the pipeline runs end-to-end: 3 epochs, trained from random weights (no internet access in the sandbox this was built in, so no pretrained checkpoint), mAP 0 across the board. That's expected and not a bug -- 3 epochs on 147 images with no transfer learning teaches a model nothing yet. It confirms conversion, training, and inference all execute without errors, not that the model is any good.

## To get an actual working model

Run `python3 convert_mvtec_to_yolo.py` then `python3 train_yolo.py` on a machine with normal internet access (your laptop, not a network-restricted sandbox) -- `train_yolo.py` needs to download the pretrained `yolo11n.pt` checkpoint from GitHub on first run, which several sandboxed environments block. With the pretrained checkpoint and 100 epochs (with early stopping), expect meaningfully non-zero mAP, though on ~180 images total it'll still be a modest proof-of-concept model, not production-grade -- that's what your own captured lathe images are for later.

## Reminder: this is a dry run

`metal_nut` isn't your part. This whole exercise validates the *pipeline* -- mask-to-bbox conversion, YOLO training, inference -- before pointing it at real lathe images. Swapping in your own data later means re-running `convert`-equivalent logic against your own annotated captures (once you have enough confirmed inspections from the diffing pipeline) and pointing `train_yolo.py`'s `DATA_YAML` at that instead.
