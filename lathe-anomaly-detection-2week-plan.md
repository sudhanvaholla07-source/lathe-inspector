# Lathe Part Anomaly Detection — 2-Week Build Plan (v2, replaces the generic IoT dashboard plan)

**Project:** Detect defective lathe-machined parts by comparing a captured image against a reference image, triggered automatically by camera-based motion detection, running on a Raspberry Pi 5 with a Hailo-8L AI accelerator.
**Mode:** Solo, full-time, physical hardware (Pi 5, Camera Module, Hailo AI Kit) already in hand.
**Window:** Wed Jul 1 – Tue Jul 14, 2026.

## What changed from the original plan

The old plan treated this as a generic "sensors → dashboard" project. It's now a computer-vision quality-control system: the trigger's job is purely to detect "a part just finished machining and is sitting still," which fires a camera capture; the real work is comparing that capture against a known-good reference image. YOLO is the eventual defect classifier, but you don't have labeled training data yet — so the plan front-loads a classical image-diffing pipeline (align, subtract, threshold) as the working v1, and treats YOLO fine-tuning as a follow-on phase once real inspection data has accumulated. This also flips the build order: last time we started with the database schema; this time we start with the physical capture pipeline on the Pi, because that's the riskiest, least-proven part of the system.

**Hardware correction:** there's no accelerometer in this build — the "AI accelerator" on hand is a Hailo-8L (Raspberry Pi AI Kit), a neural-network inference chip, not a vibration sensor. That removes the accelerometer-trigger idea entirely, but it's a net win: YOLO inference can run hardware-accelerated on the Pi instead of slow CPU inference once you get to that phase. The trigger is now purely camera-based: watch the video feed, detect when motion stops and something is sitting still in the capture zone, then fire the capture. No extra sensor hardware needed.

## Architecture in one paragraph

The Pi camera runs continuously at a low frame rate. A motion-detection loop (frame differencing between consecutive grayscale frames) watches for the scene going from "moving" (an arm/chuck placing or ejecting a part) to "still" for a short stability window — that stillness is the trigger, replacing what would've been an accelerometer event. On trigger, the Pi captures a full-resolution frame, aligns it to a stored reference image (feature matching + homography, so minor placement/rotation differences don't cause false positives), then the two are diffed pixel-by-pixel (grayscale, blurred to cut noise, thresholded to a binary mask). A diff score above a tuned threshold means "anomaly" — the Pi saves the result (pass/fail, score, both images, the diff overlay) and pushes it to a small backend (Postgres via Prisma), which a React dashboard reads so the manager can review inspections and defect trends. Every inspection the manager confirms or corrects becomes a labeled training example — once you've accumulated enough of them, that's when you fine-tune YOLO, compile it to Hailo's `.hef` format, and run it hardware-accelerated on the Pi in place of (or alongside) the diffing logic.

## Concept check: why diffing before YOLO

YOLO needs labeled examples of what a defect looks like to learn from — with zero data, it has nothing to fit. Classical diffing needs no training data at all: it just needs one clean reference image and gives you a working pass/fail system on day one. It also becomes your labeling pipeline for free — every real inspection run through it produces an image + a preliminary verdict that the manager can confirm or correct, which is exactly the labeled dataset YOLO will need later.

---

## Phase 1: Hardware bring-up & capture pipeline (Days 1–3)

**Day 1 (Wed Jul 1) — Camera capture + Hailo bring-up**
Get the Pi camera capturing an image on a manual trigger (keypress) via `picamera2`. Separately, confirm the Hailo-8L is recognized (`hailortcli scan`) and the software stack is installed — no inference yet, just proving the hardware path works. Two independent, proven pieces.

**Day 2 (Thu Jul 2) — Motion-based auto-trigger**
Build the "part is ready" detector: continuously diff consecutive frames, track motion energy, and declare "still" once it drops below a threshold for a short stability window (this replaces the debounce concept from an accelerometer — same idea, different signal: ignore noise/settling, only fire once per genuinely finished part). Wire that event to call the camera capture script.

**Day 3 (Fri Jul 3) — Reference images + alignment**
Capture a handful of reference images per part type under your actual lighting/jig setup. Build the alignment step: feature matching (ORB is fast enough for a Pi) between captured and reference image, then a homography transform to warp the capture into the reference's frame. This step exists because a part's exact placement will never be pixel-identical between two images — without alignment, diffing would flag position as if it were a defect.

---

## Phase 2: Diffing-based detection (Days 4–6)

**Day 4 (Sat Jul 4) — Pixel diff**
Grayscale both aligned images, blur slightly (reduces false positives from sensor noise/lighting flicker), take the absolute difference, threshold into a binary mask. Run this against several known-good parts and tune the threshold until it stays quiet on parts you know are fine.

**Day 5 (Sun Jul 5) — Pass/fail decision + validation**
Turn the diff mask into a single decision: sum the anomalous area (or intensity), compare to a tuned cutoff, output pass/fail + a numeric score + a visual overlay (mask painted over the image) for human review. Deliberately damage or misalign a few parts and confirm the pipeline actually catches them — this is your first real accuracy check.

**Day 6 (Mon Jul 6) — Package as a running service**
Combine everything into one continuously-running script on the Pi: watch for the motion-stopped trigger → capture → align → diff → decide → save result (JSON + images) locally. This is a working MVP entirely on the edge device, no backend required yet.

---

## Phase 3: Getting results off the Pi (Days 7–8)

**Day 7 (Tue Jul 7) — Backend skeleton**
Express + Prisma + Postgres, new schema this time: `Machine`, `PartType` (has a reference image), `Inspection` (belongs to a `PartType`; stores captured/reference/diff image references, score, pass/fail, timestamp), `User` for manager login (JWT, same as before). One endpoint: receive an inspection result + images from the Pi.

**Day 8 (Wed Jul 8) — Pi → backend link**
Simplest reliable option: the Pi does a plain HTTP POST per inspection (result JSON + images) to the backend — this beats standing up MQTT/Mosquitto for something that fires once per finished part rather than a continuous stream.

---

## Phase 4: Dashboard (Days 9–11)

**Day 9 (Thu Jul 9) — Frontend shell**
React + Tailwind + Router: `/login`, `/dashboard`, `/part-types/:id`. JWT login flow wired to the backend.

**Day 10 (Fri Jul 10) — Inspection feed**
List/table of recent inspections: thumbnail, pass/fail badge, diff score, timestamp. Click through to a side-by-side view: reference image, captured image, diff overlay — this is the actual "manager can infer at a glance" surface.

**Day 11 (Sat Jul 11) — Trends + alerting**
Recharts view of defect rate over time, per part type. Flag/alert styling when defect rate spikes over a window — same "color-coded, scannable" principle as any factory dashboard.

---

## Phase 5: Data collection groundwork + deploy (Days 12–14)

**Day 12 (Sun Jul 12) — Labeling harvest**
Add a manager-facing control on each inspection: confirm or correct the verdict (the diffing pipeline will get some wrong — that's expected and fine). Every confirmed/corrected inspection is a clean labeled example. This is the dataset YOLO fine-tuning will eventually train on, accumulating automatically from real production use with zero extra labeling effort.

**Day 13 (Mon Jul 13) — Deploy**
Backend + Postgres → Railway (or Supabase for Postgres+auth). Frontend → Vercel. Point the Pi's HTTP POST at the deployed backend URL instead of localhost.

**Day 14 (Tue Jul 14) — End-to-end test + docs**
Run a real lathe session end to end: trigger, capture, diff, upload, dashboard update. Fix what breaks. Write a short README on the pipeline and where the tuned thresholds live, so future-you doesn't have to reverse-engineer them.

---

## What's explicitly out of scope for these 2 weeks

YOLO training/fine-tuning itself. You need a real batch of labeled examples first (a reasonable starting target once Phase 5 has been running a while is 100+ confirmed images per class — normal/defect types). Once you have that, fine-tuning a YOLOv8n (nano) checkpoint is a short, well-documented process — worth scheduling as its own follow-up sprint rather than cramming it in here.

## If time runs short

Cut in this order: trend charts/alerting (Day 11) → deploy (do it locally, deploy later) → labeling-harvest UI (log everything to Postgres regardless, add the confirm/correct control later). Do not cut the alignment step (Day 3) or the diff tuning against known-good parts (Day 4) — a diffing pipeline that isn't tuned against real good parts will just be noise, and everything downstream depends on it being trustworthy.
