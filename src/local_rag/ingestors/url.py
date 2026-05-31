from __future__ import annotations

import contextlib
import uuid

import httpx
import trafilatura
from markdownify import markdownify
from qdrant_client import models

from .. import config, engine
from ..schemas import DocumentRecord, IngestResult
from ..store import mongo_store
from .base import BaseIngestor


def _chunk_text(text: str, size: int = 1500, overlap: int = 200) -> list[str]:
    chunks = []
    start = 0
    n = len(text)
    step = size - overlap
    while start < n:
        piece = text[start : start + size].strip()
        if piece:
            chunks.append(piece)
        start += step
    return chunks


class URLIngestor(BaseIngestor):
    source_type = "url"

    def can_handle(self, source: str) -> bool:
        return source.startswith("http://") or source.startswith("https://")

    def ingest(self, source: str, tags: list[str], **kwargs) -> IngestResult:
        response = httpx.get(source, follow_redirects=True, timeout=30)
        if not (200 <= response.status_code < 300):
            raise ValueError(f"Failed to fetch {source}: HTTP {response.status_code}")

        markdown_text = trafilatura.extract(
            response.text,
            output_format="markdown",
            include_tables=True,
            include_links=False,
        )
        if not markdown_text:
            markdown_text = markdownify(
                response.text, strip=["script", "style", "nav", "footer", "header"]
            )

        if not (markdown_text and markdown_text.strip()):
            return IngestResult(
                source=source, source_type=self.source_type, chunks=0, tags=tags
            )

        chunks = _chunk_text(markdown_text)
        if not chunks:
            return IngestResult(
                source=source, source_type=self.source_type, chunks=0, tags=tags
            )

        engine.qdrant_client.delete(
            collection_name=config.COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source", match=models.MatchValue(value=source)
                        )
                    ]
                )
            ),
        )

        chunks_prefixed = [f"search_document: {c}" for c in chunks]
        dense_vectors = list(engine.dense_embed_model.embed(chunks_prefixed))
        sparse_vectors = list(engine.sparse_embed_model.embed(chunks))

        points = []
        for idx, chunk in enumerate(chunks):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source}_{idx}"))
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vectors[idx].tolist(),
                        "sparse": {
                            "indices": sparse_vectors[idx].indices.tolist(),
                            "values": sparse_vectors[idx].values.tolist(),
                        },
                        "spectrogram": [0.0] * 128,  # zero-pad for non-audio sources
                    },
                    payload={
                        "text": chunk,
                        "source": source,
                        "chunk_index": idx,
                        "tags": tags,
                    },
                )
            )

        engine.qdrant_client.upsert(
            collection_name=config.COLLECTION_NAME, points=points
        )

        record = DocumentRecord(
            filename=source,
            source_type=self.source_type,
            tags=tags,
            chunk_count=len(chunks),
            markdown_content=markdown_text,
            source_url=source,
        )
        with contextlib.suppress(Exception):
            mongo_store.upsert_document(record)

        return IngestResult(
            source=source,
            source_type=self.source_type,
            chunks=len(chunks),
            tags=tags,
        )
