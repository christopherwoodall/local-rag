import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = Path(
    os.getenv("UPLOAD_DIR", str(BASE_DIR.parent.parent / "data" / "uploads"))
)
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
COLLECTION_NAME = "local_agent_knowledge"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "rag")
