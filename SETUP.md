# Running everything locally

One reference doc pulling together every piece built so far. Do these roughly in order the first time; after that, each piece can be started independently.

## Prerequisites (install once)

- **Node.js** (v18+) — check with `node -v`. Get it from nodejs.org if missing.
- **Python 3.9+** — check with `python3 --version`.
- **PostgreSQL** — either install locally, or run it via Docker if you have Docker Desktop:
  ```
  docker run --name lathe-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres
  ```
  If installing natively on Mac instead: `brew install postgresql@16 && brew services start postgresql@16`, then `createdb lathe_backend`.

---

## 1. Backend (Express + Postgres)

```
cd "/Users/sudhanva/Desktop/lathe-inspector/backend"
npm install
cp .env.example .env
```

Open `.env` and fill in:
- `DATABASE_URL` — your actual Postgres connection string (e.g. `postgresql://postgres:postgres@localhost:5432/lathe_backend`)
- `JWT_SECRET` — any long random string (`openssl rand -hex 32` in Terminal generates one)

Then:
```
npm run generate
npm run migrate
npm start
```

Should print `Backend listening on port 4000`. Leave this running in its own Terminal tab/window — everything else assumes it's up.

Quick check it's alive: open `http://localhost:4000/health` in a browser, should show `{"ok":true}`.

Already had the backend running before? A new migration was added (the `REJECTED` result type) — run `npm run migrate` again to pick it up before starting the server.

---

## 2. Training pipeline (already run once, here's how to redo it)

```
cd "/Users/sudhanva/Desktop/lathe-inspector/training data"
pip3 install ultralytics opencv-python
tar -xf metal_nut.tar.xz          # skip if the metal_nut/ folder already exists
python3 convert_mvtec_to_yolo.py  # rebuilds yolo_dataset/ from scratch
python3 train_yolo.py             # takes ~1.5 hours on a laptop CPU
```

Trained weights land at `training data/runs/detect/runs/metal_nut/weights/best.pt`. This is already done — only rerun if you want to retrain (e.g. with more epochs or more data).

---

## 3. Demo / inference on a photo

Needs `best.pt` from step 2 to already exist.

```
cd "/Users/sudhanva/Desktop/lathe-inspector/demo"
python3 run_demo.py /path/to/your/photo.jpg
```

Prints what it found and saves an annotated copy next to the original photo.

---

## 4. Raspberry Pi (separate machine — not run on your Mac)

This part runs on the Pi itself, reached over SSH from your Mac:

```
ssh pi@raspberrypi.local
```

Copy the Pi code over (run this from your Mac, in a separate Terminal tab):
```
scp -r "/Users/sudhanva/Desktop/lathe-inspector/pi" pi@raspberrypi.local:~/lathe-inspector-pi
```

Back in the SSH session:
```
cd ~/lathe-inspector-pi
chmod +x hailo_check.sh
./hailo_check.sh          # confirms the Hailo-8L is detected
sudo apt install -y python3-picamera2
python3 capture.py        # press Enter to capture, q to quit
```

Pulling a captured photo back to your Mac (run on your Mac):
```
scp pi@raspberrypi.local:~/lathe-inspector-pi/captures/<filename>.jpg .
```

Note: `capture.py` doesn't talk to the backend yet — it only saves photos locally on the Pi. Wiring it to `POST /inspections` (step 1's backend) is the next real piece of work.

---

## 5. Dashboard (React)

Needs the backend (step 1) running first — the dashboard is just a UI on top of it.

```
cd "/Users/sudhanva/Desktop/lathe-inspector/frontend"
npm install
cp .env.example .env    # VITE_API_URL, defaults to http://localhost:4000 which is right if you're following step 1 as-is
npm run dev
```

Opens at `http://localhost:5173`. First visit: click "Need an account? Sign up" to create a MANAGER account (only managers can confirm inspection results — operators can view but not confirm). Then:

- **Inspections** page — the main feed, filterable by part type and result (Pass/Fail/Rejected). Managers see Confirm PASS/FAIL buttons on unconfirmed entries (not shown for Rejected, since there's nothing to confirm on a non-product photo).
- **Machines** page — register a machine and its part types (each part type needs one reference/known-good image, uploaded here). **Do this before running the pipeline** — `run_pipeline.py` looks up the part type by name and now requires it to already exist, rather than guessing one from the test photo.
- **Stats** page — production counts (Produced, Pass, Fail, Rejected) and pass rate, filterable by part type.

Once a machine + part type exists here, run `pipeline/run_pipeline.py` (step 3) against a photo to create inspections.

Verified in the sandbox: full backend flow (signup → login → create machine → create part type with image upload → create PASS/FAIL/REJECTED inspections with image upload, correctly sorted into `uploads/pass|deformed|rejected` → list → stats → manager-confirm) tested end-to-end against every route the dashboard calls, and `npm run build` compiles cleanly. Not click-tested in an actual browser here (sandbox can't keep a server running long enough for that) — that part happens the first time you run it above.

---

## Quick-reference: what's running where

| Piece | Runs on | Command |
|---|---|---|
| Backend API | Your Mac | `npm start` in `backend/` |
| Postgres | Your Mac (or Docker) | background service |
| Dashboard | Your Mac | `npm run dev` in `frontend/` |
| Training | Your Mac | `python3 train_yolo.py` in `training data/` |
| Demo/inference | Your Mac | `python3 run_demo.py <photo>` in `demo/` |
| Camera capture | Raspberry Pi | `python3 capture.py` over SSH |
| Hailo inference | Raspberry Pi | not built yet — next phase |
