const express = require("express");
const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const prisma = require("../db");

const router = express.Router();

// POST /auth/signup -- creates a user. In a real deployment you'd likely
// lock this down (invite-only, or MANAGER-only creation of OPERATOR
// accounts) -- left open here since this is the first account-creation
// path and there's nobody to gate it yet.
router.post("/signup", async (req, res) => {
  const { email, password, name, role } = req.body;
  if (!email || !password || !name) {
    return res.status(400).json({ error: "email, password, and name are required" });
  }

  const existing = await prisma.user.findUnique({ where: { email } });
  if (existing) {
    return res.status(409).json({ error: "An account with that email already exists" });
  }

  // bcrypt.hash is deliberately slow (it's designed to resist brute-force
  // guessing) -- never store the plaintext password, ever.
  const hashed = await bcrypt.hash(password, 10);

  const user = await prisma.user.create({
    data: { email, password: hashed, name, role: role === "MANAGER" ? "MANAGER" : "OPERATOR" },
  });

  res.status(201).json({ id: user.id, email: user.email, name: user.name, role: user.role });
});

// POST /auth/login -- verifies credentials and returns a signed JWT.
// The client stores this token and sends it as "Authorization: Bearer <token>"
// on every subsequent request.
router.post("/login", async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ error: "email and password are required" });
  }

  const user = await prisma.user.findUnique({ where: { email } });
  if (!user) {
    return res.status(401).json({ error: "Invalid email or password" });
  }

  const valid = await bcrypt.compare(password, user.password);
  if (!valid) {
    return res.status(401).json({ error: "Invalid email or password" });
  }

  const token = jwt.sign(
    { id: user.id, role: user.role },
    process.env.JWT_SECRET,
    { expiresIn: "7d" }
  );

  res.json({ token, user: { id: user.id, email: user.email, name: user.name, role: user.role } });
});

module.exports = router;
