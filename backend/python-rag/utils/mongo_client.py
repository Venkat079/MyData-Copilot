# python-rag/utils/mongo_client.py
import os
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/mydata")
_client = None
_db = None

def get_db():
    global _client, _db
    if _db:
        return _db
    _client = MongoClient(MONGO_URI)
    _db = _client.get_default_database()
    # Useful indexes
    try:
        _db.users.create_index("email", unique=True)
        _db.chunks.create_index([("ownerId", 1), ("fileId", 1), ("chunkIndex", 1)])
        _db.files.create_index([("ownerId", 1), ("id", 1)])
    except Exception:
        pass
    return _db
