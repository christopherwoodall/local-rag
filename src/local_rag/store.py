from __future__ import annotations

import logging

import pymongo
from motor.motor_asyncio import AsyncIOMotorClient

from . import config
from .schemas import DocumentRecord

logger = logging.getLogger(__name__)

COLLECTION = "documents"


class MongoStore:
    def __init__(self):
        self._sync_client: pymongo.MongoClient | None = None
        self._async_client: AsyncIOMotorClient | None = None

    def _sync_col(self):
        if self._sync_client is None:
            self._sync_client = pymongo.MongoClient(
                config.MONGO_URI, serverSelectionTimeoutMS=2000
            )
        return self._sync_client[config.MONGO_DB][COLLECTION]

    def _async_col(self):
        if self._async_client is None:
            self._async_client = AsyncIOMotorClient(
                config.MONGO_URI, serverSelectionTimeoutMS=2000
            )
        return self._async_client[config.MONGO_DB][COLLECTION]

    def upsert_document(self, record: DocumentRecord) -> None:
        try:
            doc = record.model_dump()
            doc["_id"] = record.filename
            self._sync_col().replace_one({"_id": record.filename}, doc, upsert=True)
        except Exception:
            logger.error("Mongo upsert_document failed for %s", record.filename)
            raise

    async def get_document(self, filename: str) -> DocumentRecord | None:
        try:
            doc = await self._async_col().find_one({"_id": filename})
            if not doc:
                return None
            doc.pop("_id", None)
            return DocumentRecord(**doc)
        except Exception:
            logger.error("Mongo get_document failed for %s", filename)
            raise

    async def list_documents(self) -> list[DocumentRecord]:
        try:
            cursor = self._async_col().find().sort("ingested_at", -1)
            docs = await cursor.to_list(length=None)
            records = []
            for doc in docs:
                doc.pop("_id", None)
                records.append(DocumentRecord(**doc))
            return records
        except Exception:
            logger.error("Mongo list_documents failed")
            raise

    def update_tags(self, filename: str, tags: list[str]) -> None:
        try:
            result = self._sync_col().update_one(
                {"_id": filename}, {"$set": {"tags": tags}}
            )
            if result.matched_count == 0:
                raise ValueError(f"Document not found: {filename}")
        except Exception:
            logger.error("Mongo update_tags failed for %s", filename)
            raise

    def delete_document(self, filename: str) -> None:
        try:
            self._sync_col().delete_one({"_id": filename})
        except Exception:
            logger.error("Mongo delete_document failed for %s", filename)
            raise


mongo_store: MongoStore = MongoStore()


def init_store() -> None:
    try:
        mongo_store._sync_col().database.client.admin.command("ping")
        logger.info("MongoDB connected")
    except Exception:
        logger.warning("MongoDB unavailable — metadata features degraded")
