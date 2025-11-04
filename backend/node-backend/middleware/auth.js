// node-backend/middleware/auth.js

const jwt = require("jsonwebtoken");
const { getDb } = require("../utils/mongo");
const secret = process.env.JWT_SECRET || "change_this_jwt_secret";

async function authMiddleware(req, res, next) {
  try {
    const auth = req.headers.authorization;
    if (!auth || !auth.startsWith("Bearer "))
      return res.status(401).json({ message: "Missing token" });
    const token = auth.split(" ")[1];
    const payload = jwt.verify(token, secret);
    const db = getDb();
    const user = await db.collection("users").findOne({ id: payload.sub });
    if (!user) return res.status(401).json({ message: "User not found" });
    req.user = { id: user.id, email: user.email, name: user.name };
    next();
  } catch (err) {
    console.error("auth error", err.message);
    return res.status(401).json({ message: "Unauthorized" });
  }
}

module.exports = authMiddleware;
