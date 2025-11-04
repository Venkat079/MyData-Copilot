const express = require("express");
const multer = require("multer");
const path = require("path");
const fs = require("fs");
const { v4: uuidv4 } = require("uuid");
const fetch = require("node-fetch");
const { getDb } = require("../utils/mongo");
const auth = require("../middleware/auth");

const router = express.Router();

// uploads dir
const UPLOAD_DIR = path.join(__dirname, "..", "uploads");
if (!fs.existsSync(UPLOAD_DIR)) fs.mkdirSync(UPLOAD_DIR, { recursive: true });

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOAD_DIR),
  filename: (req, file, cb) =>
    cb(null, `${Date.now()}-${uuidv4()}${path.extname(file.originalname)}`),
});
const upload = multer({ storage, limits: { fileSize: 200 * 1024 * 1024 } }); // 200MB

/**
 * POST /api/upload
 * Handles file upload
 */
router.post("/", auth, (req, res) => {
  upload.single("file")(req, res, async (err) => {
    if (err) {
      console.error("Multer error during file upload:", err);
      return res.status(400).json({
        message: "Upload error (multer)",
        error: err.message || err.code || String(err),
      });
    }

    try {
      if (!req.file) {
        console.warn("Upload attempt without file for user:", req.user?.id);
        return res.status(400).json({ message: "No file uploaded" });
      }

      const db = getDb();
      const ownerId = req.user.id;

      console.log("Upload received - user:", ownerId, "file:", req.file);

      const fileRec = {
        id: uuidv4(),
        ownerId,
        originalName: req.file.originalname,
        filename: req.file.filename,
        path: req.file.path,
        mimeType: req.file.mimetype,
        size: req.file.size,
        uploadedAt: new Date(),
      };

      await db.collection("files").insertOne(fileRec);

      // Call Python service to process the file
      const pythonUrl = (
        process.env.PYTHON_RAG_URL || "http://localhost:8000"
      ).replace(/\/$/, "");
      try {
        const resp = await fetch(`${pythonUrl}/process-file`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            file_id: fileRec.id,
            owner_id: ownerId,
            path: fileRec.path,
            original_name: fileRec.originalName,
          }),
        });
        const text = await resp.text().catch(() => "");
        console.log(
          `Python /process-file response: status=${
            resp.status
          }, body=${text.slice(0, 200)}`
        );
      } catch (err) {
        console.warn("Failed to call python service:", err.message);
      }

      return res.json({
        ok: true,
        file: {
          id: fileRec.id,
          name: fileRec.originalName,
          url: `/uploads/${fileRec.filename}`,
        },
      });
    } catch (err) {
      console.error("Unhandled error in upload handler:", err);
      return res.status(500).json({
        message: "Upload failed",
        error: err.message || String(err),
      });
    }
  });
});

/**
 * GET /api/files
 * Returns list of user’s uploaded files
 */
router.get("/", auth, async (req, res) => {
  try {
    const db = getDb();
    const files = await db
      .collection("files")
      .find({ ownerId: req.user.id })
      .toArray();
    const mapped = files.map((f) => ({
      id: f.id,
      name: f.originalName,
      filename: f.filename,
      url: `${req.protocol}://${req.get("host")}/uploads/${f.filename}`,
      type: f.mimeType,
      size: f.size,
      createdAt: f.uploadedAt,
    }));
    return res.json({ files: mapped });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ message: "Failed to fetch files" });
  }
});

/**
 * GET /api/files/:id
 * Returns file metadata + chunks
 */
router.get("/:id", auth, async (req, res) => {
  try {
    const db = getDb();
    const id = req.params.id;
    const file = await db
      .collection("files")
      .findOne({ id, ownerId: req.user.id });
    if (!file) return res.status(404).json({ message: "File not found" });

    const chunks = await db
      .collection("chunks")
      .find({ fileId: id, ownerId: req.user.id })
      .toArray();

    return res.json({
      file: {
        id: file.id,
        name: file.originalName,
        filename: file.filename,
        url: `${req.protocol}://${req.get("host")}/uploads/${file.filename}`,
        type: file.mimeType,
        size: file.size,
        createdAt: file.uploadedAt,
        chunks: chunks.map((c) => ({ text: c.text, index: c.chunkIndex })),
      },
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ message: "Failed to fetch file" });
  }
});

/**
 * DELETE /api/files/:id
 * Deletes file record, chunks, and vectors
 */
router.delete("/:id", auth, async (req, res) => {
  const db = getDb();
  const fileId = req.params.id;
  const ownerId = req.user.id;

  try {
    // 1. Check file exists
    const file = await db.collection("files").findOne({ id: fileId, ownerId });
    if (!file) {
      return res.status(404).json({ message: "File not found" });
    }

    // 2. Delete file record from DB
    await db.collection("files").deleteOne({ id: fileId, ownerId });

    // 3. Call Python service (POST instead of DELETE)
    const pythonUrl = (
      process.env.PYTHON_RAG_URL || "http://localhost:8000"
    ).replace(/\/$/, "");

    let deletedResult = {};
    try {
      const resp = await fetch(`${pythonUrl}/delete-file`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner_id: ownerId, file_id: fileId }),
      });
      const text = await resp.text();
      try {
        deletedResult = JSON.parse(text);
      } catch {
        deletedResult = { raw: text };
      }
      console.log(`Python /delete-file response:`, deletedResult);
    } catch (err) {
      console.error("Failed to call python delete-file:", err.message);
    }

    // 4. Optionally, delete file from disk
    try {
      if (file.path && fs.existsSync(file.path)) {
        fs.unlinkSync(file.path);
      }
    } catch (err) {
      console.warn("Could not delete uploaded file from disk:", err.message);
    }

    return res.json({
      ok: true,
      message: "File and related chunks deleted successfully",
      result: deletedResult,
    });
  } catch (err) {
    console.error("Error deleting file:", err);
    return res.status(500).json({ message: "Failed to delete file" });
  }
});

module.exports = router;
