from __future__ import annotations

import contextlib
import logging
import uuid
from pathlib import Path

import librosa
import numpy as np
from qdrant_client import models

from .. import config, engine
from ..schemas import DocumentRecord, IngestResult
from ..store import mongo_store
from .base import BaseIngestor

logger = logging.getLogger(__name__)

_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg"}
_SPECTROGRAM_DIM = 128


def _compute_spectrogram_vector(file_path: str) -> list[float]:
    """Load audio, compute a 128-band log-mel spectrogram, average over time,
    and L2-normalise to produce a 128-dim unit vector."""
    y, sr = librosa.load(file_path, sr=16000, mono=True)
    mel = librosa.feature.melspectrogram(
        y=y, sr=sr, n_mels=_SPECTROGRAM_DIM, hop_length=512
    )
    log_mel = librosa.power_to_db(mel, ref=np.max)
    vec = log_mel.mean(axis=1)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def _character_chunk(text: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    chunks = []
    start = 0
    step = max_chars - overlap
    while start < len(text):
        chunks.append(text[start : start + max_chars])
        start += step
    return [c for c in chunks if c.strip()]


class AudioIngestor(BaseIngestor):
    source_type = "audio"

    def can_handle(self, source: str) -> bool:
        return Path(source).suffix.lower() in _AUDIO_EXTENSIONS

    def ingest(
        self, source: str, tags: list[str], filename: str | None = None, **kwargs
    ) -> IngestResult:
        filename = filename or Path(source).name

        segments, info = engine.whisper_model.transcribe(source, beam_size=5)
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
        if not transcript:
            raise ValueError(f"No speech detected in audio file: {filename}")
        logger.info(
            "Transcribed '%s': %.1fs, lang=%s", filename, info.duration, info.language
        )

        spectrogram_vec = _compute_spectrogram_vector(source)

        chunks = _character_chunk(transcript, max_chars=1500, overlap=200)
        if not chunks:
            raise ValueError(f"Transcript could not be chunked: {filename}")

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

        chunks_prefixed = [f"search_document: {c}" for c in chunks]
        dense_vectors = list(engine.dense_embed_model.embed(chunks_prefixed))
        sparse_vectors = list(engine.sparse_embed_model.embed(chunks))

        points = []
        for idx, chunk in enumerate(chunks):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{filename}_{idx}"))
            # Only the first chunk carries the real spectrogram vector;
            # spectrogram is a file-level feature, so others are zero-padded.
            spec_vec = spectrogram_vec if idx == 0 else [0.0] * _SPECTROGRAM_DIM
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vectors[idx].tolist(),
                        "sparse": {
                            "indices": sparse_vectors[idx].indices.tolist(),
                            "values": sparse_vectors[idx].values.tolist(),
                        },
                        "spectrogram": spec_vec,
                    },
                    payload={
                        "text": chunk,
                        "source": filename,
                        "chunk_index": idx,
                        "tags": tags,
                        "source_type": self.source_type,
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
            markdown_content=transcript,
        )
        with contextlib.suppress(Exception):
            mongo_store.upsert_document(record)

        return IngestResult(
            source=filename,
            source_type=self.source_type,
            chunks=len(chunks),
            tags=tags,
        )
