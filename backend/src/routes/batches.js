// Batches: labeled production runs that tray scans accumulate into.
//
// Lifecycle: POST creates an OPEN batch -> scan pipeline submits
// inspections carrying batchId -> PATCH /:id/close freezes it. Totals are
// computed from member inspections' tray payloads at read time, so there
// are no counters to drift out of sync with the underlying scans.

const express = require("express");
const prisma = require("../db");
const { requireAuth } = require("../middleware/auth");

const router = express.Router();
router.use(requireAuth);

// Per-variant totals across a set of inspections. A variant-scan tray
// payload looks like { rows, cols, total, empty, variants: {name: count},
// cells: [...] }; older defect-tray payloads (pass/fail counts, no
// variants key) still contribute to the part total.
function aggregate(inspections) {
  const variants = {};
  let parts = 0;
  for (const insp of inspections) {
    const tray = insp.tray;
    if (!tray) continue;
    parts += tray.total || 0;
    for (const [name, count] of Object.entries(tray.variants || {})) {
      variants[name] = (variants[name] || 0) + count;
    }
  }
  return { trays: inspections.filter((i) => i.tray).length, parts, variants };
}

// POST /batches { label } -- open a new batch.
router.post("/", async (req, res) => {
  const { label } = req.body;
  if (!label || !label.trim()) {
    return res.status(400).json({ error: "label is required" });
  }
  const batch = await prisma.batch.create({ data: { label: label.trim() } });
  res.status(201).json(batch);
});

// GET /batches -- newest first, each with its aggregated totals.
router.get("/", async (req, res) => {
  const where = {};
  if (req.query.status) where.status = req.query.status;

  const batches = await prisma.batch.findMany({
    where,
    include: { inspections: { select: { tray: true } } },
    orderBy: { createdAt: "desc" },
    take: 50,
  });

  res.json(batches.map(({ inspections, ...batch }) => ({
    ...batch,
    ...aggregate(inspections),
  })));
});

// GET /batches/:id -- one batch with totals and its scan list.
router.get("/:id", async (req, res) => {
  const batch = await prisma.batch.findUnique({
    where: { id: req.params.id },
    include: {
      inspections: {
        include: { partType: true },
        orderBy: { timestamp: "desc" },
      },
    },
  });
  if (!batch) return res.status(404).json({ error: "batch not found" });

  res.json({ ...batch, ...aggregate(batch.inspections) });
});

// PATCH /batches/:id/close
router.patch("/:id/close", async (req, res) => {
  const batch = await prisma.batch.update({
    where: { id: req.params.id },
    data: { status: "CLOSED", closedAt: new Date() },
  });
  res.json(batch);
});

module.exports = router;
