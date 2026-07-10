const express = require("express");
const prisma = require("../db");
const { requireAuth } = require("../middleware/auth");

const router = express.Router();
router.use(requireAuth);

router.post("/", async (req, res) => {
  const { name, location } = req.body;
  if (!name) return res.status(400).json({ error: "name is required" });

  const machine = await prisma.machine.create({ data: { name, location } });
  res.status(201).json(machine);
});

router.get("/", async (req, res) => {
  const machines = await prisma.machine.findMany({
    include: { partTypes: true },
    orderBy: { createdAt: "desc" },
  });
  res.json(machines);
});

module.exports = router;
