# Hailo compile recipe & gotchas

How `best.pt` becomes `yolov11n.hef` running on the Pi's Hailo-8L. Everything
here is already encoded in `compile_hef_colab.ipynb`; this file explains *why*
each piece is the way it is, for the next time something changes.

## The pipeline

```
best.pt ──(ultralytics export, Mac)──▶ best.onnx
best.onnx + calibration images ──(Dataflow Compiler, Colab x86 Linux)──▶ yolov11n.hef
yolov11n.hef ──(scp)──▶ Pi ──(HailoRT / picamera2 Hailo wrapper)──▶ inference
```

Why Colab: the Dataflow Compiler only runs on x86-64 Linux (not macOS, not the
Pi's ARM). Colab is a free x86 Linux VM. The compiler (huge) *builds* the
model; HailoRT (small, on the Pi) *executes* it.

Why calibration images: the chip does int8 math. The compiler watches the model
process ~200–1000 representative images (no labels needed) to choose the
float→int8 value mappings. We used 205 MVTec images; below 1024 the compiler
silently drops to optimization level 0 (basic quantization). Next compile:
1000+ images and a Colab GPU runtime for better accuracy.

## Version pinning (the important part)

| Component | Version | Why |
|---|---|---|
| Dataflow Compiler | 3.34.0 (`py3-none` wheel, Linux x86_64) | Hailo-8/8L family. The 5.x line is for Hailo-10H. |
| Hailo Model Zoo | **v2.19.0** (git tag, not master) | Each MZ release pins one DFC version — v2.19.0 ↔ DFC 3.34.0. `master` now requires DFC 5.4.0 and will refuse to install. Pairing is in the MZ `setup.py` (`CUR_DFC_VERSION`) and `docs/CHANGELOG.rst`. |
| Target arch | `--hw-arch hailo8l` | Our chip is the **8L** (13 TOPS AI HAT+), verified via `hailortcli fw-control identify`. A HEF for the wrong arch won't load. Never assume from the product name — check the chip. |
| Classes | `--classes 4` | bent, color, flip, scratch. The default NMS config assumes COCO's 80. |

## Gotchas we hit (all fixed in the notebook)

1. **`venv` fails on Colab** — `ensurepip` crashes on Colab's custom Python
   build, leaving a venv with no pip and cryptic "No such file" errors later.
   Use `virtualenv` (bundles its own pip).
2. **Model zoo won't install with build isolation** — its `setup.py` checks
   the DFC package is installed, but pip's isolated build sandbox can't see the
   venv. Install with `pip install --no-build-isolation -e ...`.
3. **`KeyError: 'USER'` at compile time** — the compiler reads the `USER` env
   var, which Colab doesn't set. `%env USER=root` before compiling.
4. **Download the right thing** — the Developer Zone offers a 9 GB "AI Software
   Suite (Docker)"; that's for Linux workstations. We only need the ~500 MB
   Dataflow Compiler `.whl` (Software Sub-Package → Dataflow Compiler). Watch
   the device tab (Hailo-8/8L vs Hailo-10H) — it changes which package you get.
5. **Result buffers are device-owned on the Pi** — reading `hailo.run()`
   results after the `with Hailo(...)` block closes segfaults (use-after-free).
   Read/copy inside the block.

## Verified on-chip behavior

- `hailortcli run yolov11n.hef` → ~81 FPS on the 8L (dummy data).
- Output (via `pi/hailo_probe.py`): list of 4 ndarrays, one per class in
  training order `[bent, color, flip, scratch]`; each row
  `[y0, x0, y1, x1, score]`, normalized 0–1. NMS is baked into the HEF
  (added automatically by the model zoo recipe at compile time).
- Quantization cost vs the float32 laptop model on the identical tray:
  confidences 0.95/0.94/0.98 → 0.91/0.92/0.98. No verdict changes.

## Recompiling after retraining

1. Mac: `python3 -c "from ultralytics import YOLO; YOLO('best.pt').export(format='onnx', opset=11, imgsz=640)"`
2. Replace `best.onnx` (and optionally the calibration zip — use *new-rig*
   images once they exist; calibration should match deployment conditions).
3. Rerun the notebook (Runtime → Run all). Consider a GPU runtime + 1000+
   calibration images to escape optimization level 0.
4. `scp` the new `.hef` to the Pi. Done — nothing else changes unless the
   class list changed (then update `CLASS_NAMES` in `pi/run_tray_pipeline_pi.py`
   and `--classes` in the notebook).

If the model *architecture* changes (yolo11s/m, different family), the model
zoo recipe name (`hailomz compile yolov11n`) must change too, and this whole
recipe should be re-validated.
