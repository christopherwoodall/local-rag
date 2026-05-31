from __future__ import annotations

import contextlib
import uuid
from pathlib import Path

from qdrant_client import models

from .. import config, engine
from ..schemas import DocumentRecord, IngestResult
from ..store import mongo_store
from .base import BaseIngestor


class PDFIngestor(BaseIngestor):
    source_type = "pdf"

    def can_handle(self, source: str) -> bool:
        return source.endswith(".pdf")

    def ingest(
        self, source: str, tags: list[str], filename: str | None = None, **kwargs
    ) -> IngestResult:
        filename = filename or Path(source).name

        engine.qdrant_client.delete(
            collection_name=config.COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source", match=models.MatchValue(value=filename)
                        )
                    ]
                )
            ),
        )

        conversion_result = engine.doc_converter.convert(source)
        markdown_text = conversion_result.document.export_to_markdown()

        chunks = [
            c.text
            for c in engine.chunker.chunk(conversion_result.document)
            if c.text.strip()
        ]
        if not chunks:
            return IngestResult(
                source=filename, source_type=self.source_type, chunks=0, tags=tags
            )

        chunks_prefixed = [f"search_document: {c}" for c in chunks]
        dense_vectors = list(engine.dense_embed_model.embed(chunks_prefixed))
        sparse_vectors = list(engine.sparse_embed_model.embed(chunks))

        points = []
        for idx, chunk in enumerate(chunks):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{filename}_{idx}"))
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
                        "source": filename,
                        "chunk_index": idx,
                        "tags": tags,
                    },
                )
            )

        engine.qdrant_client.upsert(
            collection_name=config.COLLECTION_NAME, points=points
        )

        record = DocumentRecord(
            filename=filename,
            source_type=self.source_type,
            tags=tags,
            chunk_count=len(chunks),
            markdown_content=markdown_text,
        )
        with contextlib.suppress(Exception):
            mongo_store.upsert_document(record)

        return IngestResult(
            source=filename,
            source_type=self.source_type,
            chunks=len(chunks),
            tags=tags,
        )
