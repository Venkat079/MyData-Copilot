require("dotenv").config();
const express = require("express");
const path = require("path");
const cors = require("cors");
const { connect } = require("./utils/mongo");

const app = express();
const PORT = process.env.PORT || 5000;
const CORS_ORIGIN = process.env.CORS_ORIGIN || "http://localhost:3000";

app.use(cors({ origin: CORS_ORIGIN, credentials: true }));
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true }));

// ensure uploads dir
const UPLOAD_DIR = path.join(__dirname, "uploads");
const fs = require("fs");
if (!fs.existsSync(UPLOAD_DIR)) fs.mkdirSync(UPLOAD_DIR, { recursive: true });
app.use("/uploads", express.static(UPLOAD_DIR));

// connect to mongo then start server
connect()
  .then(() => {
    console.log("Connected to MongoDB");

    app.use("/api/auth", require("./routes/auth"));
    app.use("/api/upload", require("./routes/files")); // POST /api/upload
    app.use("/api/files", require("./routes/files")); // GET /api/files
    app.use("/api/query", require("./routes/query"));

    // /api/me/stats
    const auth = require("./middleware/auth");

    app.get("/api/me", auth, async (req, res) => {
      try {
        res.json({
          id: req.user.id,
          name: req.user.name,
          email: req.user.email,
        });
      } catch (err) {
        console.error("Error in /api/me:", err);
        res.status(500).json({ message: "Failed to get user info" });
      }
    });

    app.get("/api/me/stats", auth, async (req, res) => {
      try {
        const db = require("./utils/mongo").getDb();
        const files = await db
          .collection("files")
          .find({ ownerId: req.user.id })
          .toArray();
        const pages = await db
          .collection("chunks")
          .countDocuments({ ownerId: req.user.id });
        const lastUpload = files.length
          ? files[files.length - 1].uploadedAt
          : null;
        return res.json({ files: files.length, pages, lastUpload });
      } catch (err) {
        console.error(err);
        return res.status(500).json({ message: "Stats error" });
      }
    });

    app.get("/api/ping", (req, res) =>
      res.json({ ok: true, now: new Date().toISOString() })
    );

    app.listen(PORT, () => {
      console.log(`Node backend listening on port ${PORT}`);
    });
  })
  .catch((err) => {
    console.error("Failed to connect to Mongo", err);
    process.exit(1);
  });

app.post("/api/chat", async (req, res) => {
  try {
    const response = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body),
    });
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Chat backend error" });
  }
});
