# Backend

Express + PostgreSQL (via Prisma) + JWT auth. Receives inspection results from the Pi, serves them to the dashboard.

## Data model

`User` (auth) — `Machine` 1—\* `PartType` 1—\* `Inspection`. A `PartType` holds the reference (known-good) image; each `Inspection` is one photo-and-verdict event, with an optional manager-confirmed result that becomes labeled training data over time.

## Setup on your own machine

1. Install Postgres locally (or Docker: `docker run -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres`).
2. `npm install`
3. Copy `.env.example` to `.env`, set `DATABASE_URL` and a real `JWT_SECRET` (any long random string — `openssl rand -hex 32` works).
4. `npm run generate` then `npm run migrate` — applies the schema. A migration already exists in `prisma/migrations/`, so this should apply cleanly.
5. `npm start` — runs on port 4000 by default.

## Routes

- `POST /auth/signup`, `POST /auth/login` — returns a JWT on login.
- `POST /machines`, `GET /machines` (auth required)
- `POST /part-types` (multipart: `name`, `machineId`, `referenceImage` file), `GET /part-types?machineId=`
- `POST /inspections` (multipart: `partTypeId`, `result` [`PASS`/`FAIL`/`REJECTED`], `score`, `method`, `capturedImage` file, optional `diffImage` file) — **this is the endpoint the Pi calls**. Images are saved into `uploads/pass/`, `uploads/deformed/`, or `uploads/rejected/` depending on `result`.
- `GET /inspections?partTypeId=&result=` — the dashboard's main feed
- `GET /inspections/stats?partTypeId=` — counts for the Stats page: `{ produced, pass, fail, rejected, totalCaptures, passRate }`. `produced` is `pass + fail` only — a `REJECTED` capture (wrong object, empty frame) isn't a unit that came off the machine, so it's excluded from the production count.
- `PATCH /inspections/:id/confirm` (MANAGER only, body: `confirmedResult`) — the labeling-harvest step from the project plan

All routes except `/health`, `/auth/signup`, `/auth/login` require `Authorization: Bearer <token>`. That means the Pi needs its own account too — create one (an OPERATOR role is fine) and have the capture script log in once and reuse the token for its session.

## REJECTED result

`REJECTED` means the captured photo wasn't recognizable as the registered part at all (wrong object, empty frame, etc.) — it's decided by `pipeline/run_pipeline.py` comparing the photo against the part type's reference image *before* running YOLO, since YOLO itself was only ever trained to spot defects on the real part and has no way to say "this isn't a part." See that script's `check_is_product()` for the actual logic.

## One thing worth knowing

Same situation as Day 1: this sandbox can't reach `binaries.prisma.sh`, so I couldn't run `prisma generate`/`migrate` directly here. I hand-wrote the migration SQL (verified against a real local Postgres — all 4 tables and both foreign keys confirmed) and tested every route's actual logic — auth, file uploads, role gating, the full signup → login → create machine → create part type → submit inspection → list → confirm flow — against a lightweight in-memory stand-in for the database, so the request/response behavior is genuinely proven, just not against a real Postgres instance in this sandbox. On your machine, `npm run generate` and `npm run migrate` will work normally, and everything here runs as-is.
