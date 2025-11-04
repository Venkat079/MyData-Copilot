// node-backend/routes/query.js
const express = require("express");
const fetch = require("node-fetch");
const auth = require("../middleware/auth");
const router = express.Router();

const PY_URL = (process.env.PYTHON_RAG_URL || "http://localhost:8000").replace(
  /\/$/,
  ""
);

// POST /api/query
router.post("/", auth, async (req, res) => {
  const { query, scope } = req.body || {};
  if (!query) return res.status(400).json({ message: "query required" });

  try {
    const r = await fetch(`${PY_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        scope: scope || "mydata+general",
        owner_id: req.user.id,
      }),
    });

    const json = await r.json();
    return res.json(json);
  } catch (err) {
    console.error(err);
    return res
      .status(500)
      .json({ message: "Query failed", detail: err.message });
  }
});

module.exports = router;
