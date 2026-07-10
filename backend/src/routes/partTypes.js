const express = require("express");
const multer = require("multer");
const path = require("path");
const prisma = require("../db");
const { requireAuth } = require("../middleware/auth");

const router = express.Router();
router.use(requireAuth);

const upload = multer({ dest: path.join(__dirname, "..", "..", "uploads") });

// Registering a part type means uploading the one reference (known-good)
// image everything else gets diffed against later.
router.post("/", upload.single("referenceImage"), async (req, res) => {
  const { name, machineId } = req.body;
  if (!name || !machineId) {
    return res.status(400).json({ error: "name and machineId are required" });
  }
  if (!req.file) {
    return res.status(400).json({ error: "referenceImage file is required" });
  }

  const partType = await prisma.partType.create({
    data: {
      name,
      machineId,
      referenceImageUrl: `/uploads/${req.file.filename}`,
    },
  });

  res.status(201).json(partType);
});

router.get("/", async (req, res) => {
  const where = req.query.machineId ? { machineId: req.query.machineId } : {};
  const partTypes = await prisma.partType.findMany({ where, orderBy: { createdAt: "desc" } });
  res.json(partTypes);
});

module.exports = router;
