require("dotenv").config();
const express = require("express");
const cors = require("cors");
const path = require("path");

const authRoutes = require("./routes/auth");
const machineRoutes = require("./routes/machines");
const partTypeRoutes = require("./routes/partTypes");
const inspectionRoutes = require("./routes/inspections");
const batchRoutes = require("./routes/batches");

const app = express();

app.use(cors());
app.use(express.json());

// Serves uploaded images back out, e.g. /uploads/abc123.jpg -- the
// dashboard's <img> tags point straight at these URLs.
app.use("/uploads", express.static(path.join(__dirname, "..", "uploads")));

app.get("/health", (req, res) => res.json({ ok: true }));

app.use("/auth", authRoutes);
app.use("/machines", machineRoutes);
app.use("/part-types", partTypeRoutes);
app.use("/inspections", inspectionRoutes);
app.use("/batches", batchRoutes);

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => console.log(`Backend listening on port ${PORT}`));
