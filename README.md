# Lathe Inspector

Automated visual quality inspection for lathe-machined parts (T-nuts). A camera
photographs trays of finished parts, an AI model running on a Hailo accelerator
detects defects in each tray slot, and a web dashboard records every inspection
with per-part counts, manager review, and production stats.

**Current state:** the full pipeline works end-to-end on real hardware with a
proxy dataset (MVTec metal_nut standing in for the real T-nut). The Raspberry Pi
runs inference on its Hailo-8L chip at ~81 FPS — no laptop needed in the
inference path. The physical camera rig and real-part training data are the
remaining work.

---

## System overview

```
┌─────────────────────── Raspberry Pi 5 + Hailo-8L ───────────────────────┐
│  capture.py            run_tray_pipeline_pi.py                          │
│  (Pi camera)  ──photo──▶  slice tray into grid cells                    │
│                           ├─ empty-slot check (grayscale std-dev)       │
│                           ├─ per-cell defect inference (HEF on Hailo)   │
│                           └─ counts + annotated overview image          │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ HTTP (multipart POST /inspections)
                                   ▼
┌────────────── Backend (Node/Express + Prisma + Postgres) ───────────────┐
│  JWT auth · machines · part types · inspections · per-part stats        │
│  images stored in uploads/{pass,deformed,rejected}/                     │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ REST
                                   ▼
┌────────────────────── Dashboard (React + Vite) ──────────────────────────┐
│  Inspections feed · tray overviews · manager confirm (PASS/FAIL)         │
│  Stats: per-nut counts, pass rate, reset window, run history              │
└───────────────────────────────────────────────────────────────────────────┘
```

The design principle: the Pi owns capture and the AI decision, the backend owns
the permanent record, and the dashboard is a window onto that record — it never
computes anything itself.

## Repository layout

| Path | What it is |
|---|---|
| `backend/` | Express API. `prisma/schema.prisma` is the data model — read this first. |
| `frontend/` | React dashboard (Inspections, Machines, Stats pages). |
| `pipeline/` | Laptop-side scripts: single-part and tray pipelines (ultralytics YOLO). |
| `pi/` | Pi-side scripts: camera capture, Hailo probe, Hailo tray pipeline. |
| `hailo/` | Colab notebook that compiles the model for the Hailo chip + notes. |
| `training data/` | MVTec metal_nut dataset, YOLO-format labels, training runs/weights. |
| `demo/trays/` | Generated synthetic tray images + ground-truth JSON sidecars. |

## The model

YOLO11n object detector, trained ~100 epochs on the MVTec `metal_nut` dataset
(4 defect classes: `bent`, `color`, `flip`, `scratch`), mAP50 ≈ 0.78, 640×640
input. Weights: `training data/runs/detect/runs/metal_nut/weights/best.pt`.

MVTec is a **proxy dataset** — the real target part (T-nut) has no photos yet.
This proves the pipeline; it does not prove accuracy on the production part.
The model runs in two places:

- **Laptop:** `pipeline/*.py` load `best.pt` via ultralytics (float32).
- **Pi:** `pi/run_tray_pipeline_pi.py` loads `yolov11n.hef`, the same network
  compiled and int8-quantized for the Hailo-8L (see `hailo/NOTES.md`).
  Measured quantization cost: 1–4 points of confidence, no changed verdicts.

## How an inspection flows (tray)

1. A tray photo is taken (or generated synthetically with `make_tray.py`).
2. The image is sliced into its known grid cells — no object detection needed
   to *find* parts, because the fixed tray design says where every part can be.
3. Each cell: if grayscale std-dev < 15 it's an **EMPTY** slot (an empty slot is
   near-uniform; any nut is heavily textured — measured margin is ~3 vs ~40).
   Otherwise the cell crop goes through YOLO: any detection ≥ 0.25 confidence
   is a **FAIL** (with defect class), no detections is a **PASS**.
4. Counts (`total/pass/fail/empty`) + per-cell results travel to the backend in
   a `tray` JSON field; the overall verdict is FAIL if any slot failed. An
   annotated overview (color-coded borders + counts banner) is uploaded too.
5. Stats count **individual parts**, not trays: a tray row contributes its
   per-slot counts; single-part inspections contribute 1. REJECTED means "bad
   capture, not a part" and is never counted as production.
6. A manager can confirm/correct verdicts on the dashboard. `confirmedResult`
   stores the *truth*, not "was the model right" — accuracy is derived by
   comparing it to `result`, and every confirmation is a future training label.

## Running everything

Backend (Mac, terminal 1):
```
cd backend && npm start                  # http://localhost:4000
```

Dashboard (Mac, terminal 2):
```
cd frontend && npm run dev               # http://localhost:5173
```

Generate a synthetic tray + inspect it on the laptop:
```
cd pipeline
python3 make_tray.py --rows 3 --cols 4 --defects 3 --empties 1   # add --seed N for reproducible
python3 run_tray_pipeline.py "$(ls -t ../demo/trays/*.png | head -1)"
```

Single-part inspection (the original flow):
```
cd pipeline
python3 run_pipeline.py "../training data/metal_nut/test/good/000.png"
```

Inspect a tray **on the Pi/Hailo** (backend must be reachable — use the Mac's
LAN IP, not localhost):
```
ssh sudhanva@lathepi.local
cd ~/lathe-inspector-pi
BACKEND_URL=http://<mac-ip>:4000 python3 run_tray_pipeline_pi.py tray.png --rows 3 --cols 4
```

Sanity-check the chip / model:
```
hailortcli fw-control identify           # chip architecture (HAILO8L)
hailortcli run yolov11n.hef              # dummy-data FPS test (~81 FPS)
python3 hailo_probe.py test_scratch.png  # one real image, prints raw output structure
```

Useful knobs (env vars): `SIMILARITY_THRESHOLD` (single-part not-a-product
gate), `BACKEND_URL/EMAIL/PASSWORD`, `PART_TYPE_NAME`, `HEF_PATH`. In-code:
`CONFIDENCE_THRESHOLD` (0.25 — lower catches more defects at the cost of false
alarms; for QC, false alarms are the cheaper error) and `EMPTY_STD_THRESHOLD`.

## Synthetic trays and free training data

`pipeline/make_tray.py` composites MVTec images into a grid at **native 700 px
per cell, saved as PNG**. This matters: an earlier 320 px/JPEG version made the
model fail every nut — resampling blur and JPEG artifacts look like surface
damage to a scratch detector (train/test distribution shift). Keep generated
cells at native resolution and lossless.

Every generated tray writes a JSON sidecar with each cell's label and pixel
box — ready-made annotations for eventually training a single-shot tray
detector with zero hand-labeling.

## Hailo deployment (summary)

Compile once per model change, in Google Colab (the compiler needs x86 Linux):
`hailo/compile_hef_colab.ipynb` — upload the DFC wheel, `best.onnx`, and a
calibration zip to Drive, run the cells, get `yolov11n.hef` out. The notebook
already encodes every fix we discovered; the full recipe and gotcha list lives
in **`hailo/NOTES.md`**. Deploying = `scp` the new `.hef` to the Pi. Nothing
else changes.

Verified output format on-chip (via `pi/hailo_probe.py`): a list of 4 arrays
(one per class), each row `[y0, x0, y1, x1, score]`, normalized 0–1, NMS
already applied inside the HEF. Result buffers are device-owned — **read them
inside the `with Hailo(...)` block** or you get a segfault.

## Roadmap

1. **Camera → tray pipeline hookup** — feed `capture.py` output straight into
   `run_tray_pipeline_pi.py` (replaces the file argument; everything else stays).
2. **Physical rig** — slotted tray, rigid overhead camera, diffuse lighting
   (specular glare on machined metal reads as a color defect). Freeze geometry
   early: every hardware adjustment invalidates previously collected data.
   Target ≥ 300–400 px per nut in the capture.
3. **Real data** — photograph every tray for a couple of weeks; deliberately
   make a handful of defective parts. Expect the MVTec model to be useless on
   real T-nuts (different part) — the plumbing carries over, the brain gets
   replaced.
4. **Retrain and recompile** — retrain on rig images, re-run the Colab
   notebook (use a GPU runtime + 1000 calibration images to lift the
   quantization from optimization level 0), swap the `.hef`.
5. **Auto-capture trigger** and **per-cell manager confirmation** (tray
   confirms currently bless the whole tray, not individual slots).
6. Worth evaluating: **anomaly detection** (train on good parts only) — fits
   production reality, where good examples vastly outnumber defects.

## Known limitations

- Model is trained on a proxy part; accuracy numbers don't transfer to T-nuts.
- Quantization ran at optimization level 0 (205 calibration images, CPU-only
  Colab) — recoverable accuracy is being left on the table until recompile.
- The single-part REJECTED gate is a color-histogram comparison, not a
  classifier — it filters obviously-wrong photos, nothing more.
- Tray slicing assumes the tray exactly fills the frame; a real rig needs a
  one-time corner-alignment calibration in `slice_cells()`.
- Manager confirmation is tray-level, so tray inspections don't yet yield
  per-nut training labels.
