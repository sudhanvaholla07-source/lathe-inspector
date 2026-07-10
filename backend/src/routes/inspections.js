const express = require("express");
const multer = require("multer");
const path = require("path");
const fs = require("fs");
const prisma = require("../db");
const { requireAuth, requireRole } = require("../middleware/auth");

const router = express.Router();
router.use(requireAuth);

const UPLOADS_ROOT = path.join(__dirname, "..", "..", "uploads");
const upload = multer({ dest: UPLOADS_ROOT });

const VALID_RESULTS = ["PASS", "FAIL", "REJECTED"];

// Which subfolder a result's images land in. Keeping deformed (FAIL) parts
// physically separate from good ones is what the user asked for -- makes it
// trivial to eyeball "everything that got flagged" without filtering, and
// keeps rejected (not-a-product) captures out of the way entirely since
// they're not real inspection data.
const RESULT_FOLDER = { PASS: "pass", FAIL: "deformed", REJECTED: "rejected" };

// multer always saves to the flat uploads/ root first (that's the only path
// it knows before the request body -- containing `result` -- has been
// parsed). Once we know the result, move the file into its subfolder and
// return the new relative URL.
function fileToSubfolder(file, result) {
  const folder = RESULT_FOLDER[result];
  const dir = path.join(UPLOADS_ROOT, folder);
  fs.mkdirSync(dir, { recursive: true });
  const dest = path.join(dir, file.filename);
  fs.renameSync(file.path, dest);
  return `/uploads/${folder}/${file.filename}`;
}

// This is the endpoint the Pi calls after every inspection: capturedImage
// (required) is the photo just taken; diffImage (optional) is the visual
// overlay showing what the diffing pipeline flagged. Everything else is
// plain form fields alongside the files (multipart/form-data, not JSON --
// that's what lets files and fields travel in a single request).
router.post(
  "/",
  upload.fields([{ name: "capturedImage", maxCount: 1 }, { name: "diffImage", maxCount: 1 }]),
  async (req, res) => {
    const { partTypeId, result, score, method, tray, batchId } = req.body;

    // Scans made as part of a production run carry a batchId; the batch
    // must exist and still be open (scanning into a closed batch would
    // silently corrupt a frozen record).
    if (batchId) {
      const batch = await prisma.batch.findUnique({ where: { id: batchId } });
      if (!batch) return res.status(400).json({ error: "batch not found" });
      if (batch.status !== "OPEN") {
        return res.status(400).json({ error: "batch is closed" });
      }
    }

    // Tray pipeline sends counts + per-cell results as a JSON string form
    // field (multipart forms can't nest objects). Absent for single-part
    // inspections; malformed JSON is a client bug worth failing loudly on.
    let trayData = null;
    if (tray) {
      try {
        trayData = JSON.parse(tray);
      } catch {
        return res.status(400).json({ error: "tray must be valid JSON" });
      }
    }

    if (!partTypeId || !result || score === undefined) {
      return res.status(400).json({ error: "partTypeId, result, and score are required" });
    }
    if (!VALID_RESULTS.includes(result)) {
      return res.status(400).json({ error: "result must be PASS, FAIL, or REJECTED" });
    }
    if (!req.files || !req.files.capturedImage) {
      return res.status(400).json({ error: "capturedImage file is required" });
    }

    const capturedImageUrl = fileToSubfolder(req.files.capturedImage[0], result);
    const diffImageUrl = req.files.diffImage ? fileToSubfolder(req.files.diffImage[0], result) : null;

    const inspection = await prisma.inspection.create({
      data: {
        partTypeId,
        result,
        score: parseFloat(score),
        method: method === "YOLO" ? "YOLO" : "DIFF",
        capturedImageUrl,
        diffImageUrl,
        tray: trayData,
        batchId: batchId || null,
      },
    });

    res.status(201).json(inspection);
  }
);

// GET /inspections?partTypeId=...&result=FAIL -- the dashboard's main feed.
router.get("/", async (req, res) => {
  const where = {};
  if (req.query.partTypeId) where.partTypeId = req.query.partTypeId;
  if (req.query.result) where.result = req.query.result;

  const inspections = await prisma.inspection.findMany({
    where,
    include: { partType: true },
    orderBy: { timestamp: "desc" },
    take: 100,
  });
  res.json(inspections);
});

// GET /inspections/stats?partTypeId=... -- counts for the Stats page.
// "produced" deliberately excludes REJECTED captures -- a rejected photo
// isn't a unit that came off the machine, it's a bad capture (wrong object,
// empty frame), so it shouldn't inflate or deflate a production count.
//
// Counting rows stopped working once tray inspections existed: one tray row
// represents many physical parts. So instead of prisma.count(), we pull each
// inspection's result + tray payload and count *parts* -- a tray contributes
// its per-slot pass/fail counts, a single-part inspection contributes 1.
// Empty slots count as nothing (no part was there). REJECTED stays a
// per-capture count since it means "bad photo", not "bad part".
router.get("/stats", async (req, res) => {
  const where = {};
  if (req.query.partTypeId) where.partTypeId = req.query.partTypeId;

  // ?since=<ISO date> -- only count inspections after this moment. This is
  // what powers the dashboard's "Reset counters" button: nothing is deleted,
  // the counting window just starts fresh from when the button was pressed.
  if (req.query.since) {
    const since = new Date(req.query.since);
    if (!isNaN(since)) where.timestamp = { gte: since };
  }

  const inspections = await prisma.inspection.findMany({
    where,
    select: { result: true, tray: true },
  });

  let pass = 0, fail = 0, rejected = 0;
  for (const insp of inspections) {
    if (insp.tray) {
      pass += insp.tray.pass || 0;
      fail += insp.tray.fail || 0;
    } else if (insp.result === "PASS") pass += 1;
    else if (insp.result === "FAIL") fail += 1;
    else if (insp.result === "REJECTED") rejected += 1;
  }

  const produced = pass + fail;
  res.json({
    produced,
    pass,
    fail,
    rejected,
    totalCaptures: produced + rejected,
    passRate: produced > 0 ? pass / produced : null,
  });
});

// PATCH /inspections/:id/confirm -- a manager confirming or correcting the
// automated verdict. This is the "labeling harvest" from the project plan:
// every confirmed inspection becomes a clean training example for YOLO later.
router.patch("/:id/confirm", requireRole("MANAGER"), async (req, res) => {
  const { confirmedResult } = req.body;
  if (!["PASS", "FAIL"].includes(confirmedResult)) {
    return res.status(400).json({ error: "confirmedResult must be PASS or FAIL" });
  }

  const inspection = await prisma.inspection.update({
    where: { id: req.params.id },
    data: { confirmedResult, confirmedAt: new Date() },
  });

  res.json(inspection);
});

module.exports = router;
