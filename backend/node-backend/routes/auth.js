// node-backend/routes/auth.js
const express = require("express");
const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const { v4: uuidv4 } = require("uuid");
const { getDb } = require("../utils/mongo");
const router = express.Router();

const JWT_SECRET = process.env.JWT_SECRET || "change_this_jwt_secret";
const TOKEN_EXPIRES_IN = process.env.TOKEN_EXPIRES_IN || "7d";

router.post("/register", async (req, res) => {
  try {
    const db = getDb();
    const { name, email, password } = req.body || {};
    if (!email || !password)
      return res.status(400).json({ message: "Email and password required" });

    const existing = await db
      .collection("users")
      .findOne({ email: email.toLowerCase() });
    if (existing)
      return res.status(409).json({ message: "User already exists" });

    const id = uuidv4();
    const passwordHash = bcrypt.hashSync(password, 10);
    const user = {
      id,
      name: name || "",
      email: email.toLowerCase(),
      passwordHash,
      createdAt: new Date(),
    };
    await db.collection("users").insertOne(user);
    const token = jwt.sign({ sub: id, email: user.email }, JWT_SECRET, {
      expiresIn: TOKEN_EXPIRES_IN,
    });
    return res.json({
      token,
      user: { id: user.id, email: user.email, name: user.name },
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ message: "Server error" });
  }
});

router.post("/login", async (req, res) => {
  try {
    const db = getDb();
    const { email, password } = req.body || {};
    if (!email || !password)
      return res.status(400).json({ message: "Email and password required" });

    const user = await db
      .collection("users")
      .findOne({ email: email.toLowerCase() });
    if (!user) return res.status(401).json({ message: "Invalid credentials" });

    const ok = bcrypt.compareSync(password, user.passwordHash);
    if (!ok) return res.status(401).json({ message: "Invalid credentials" });

    const token = jwt.sign({ sub: user.id, email: user.email }, JWT_SECRET, {
      expiresIn: TOKEN_EXPIRES_IN,
    });
    return res.json({
      token,
      user: { id: user.id, email: user.email, name: user.name },
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ message: "Server error" });
  }
});

module.exports = router;
