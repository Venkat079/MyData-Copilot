// node-backend/utils/mongo.js
const { MongoClient } = require("mongodb");
const uri = process.env.MONGO_URI || "mongodb://localhost:27017/mydata";

let client;
let db;

async function connect() {
  if (db) return db;
  client = new MongoClient(uri);
  await client.connect();
  db = client.db(); // uses DB name from URI or default
  // ensure indexes
  await db
    .collection("users")
    .createIndex({ email: 1 }, { unique: true })
    .catch(() => {});
  await db.collection("chunks").createIndex({ ownerId: 1 });
  return db;
}

function getDb() {
  if (!db) throw new Error("Mongo not connected. Call connect() first.");
  return db;
}

module.exports = { connect, getDb };
