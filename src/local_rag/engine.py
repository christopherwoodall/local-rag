import contextlib

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from fastembed import SparseTextEmbedding, TextEmbedding
from faster_whisper import WhisperModel
from qdrant_client import QdrantClient, models

from . import config
from .schemas import IngestResult, SearchQuery, SearchResultItem
from .store import mongo_store

print("Loading ML models and initializing DB connections...")
qdrant_client = QdrantClient(host=config.QDRANT_HOST, port=6333)
dense_embed_model = TextEmbedding(model_name="nomic-ai/nomic-embed-text-v1.5")
sparse_embed_model = SparseTextEmbedding(model_name="Qdrant/bm25")
doc_converter = DocumentConverter()
chunker = HybridChunker()

print("Loading Whisper model (this may take a moment on first run)...")
# CTranslate2 CPU backend — works on Apple Silicon without CUDA.
# int8 reduces memory footprint on the Mac Mini.
whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")
print("Whisper model loaded.")

# Target collection schema — used for both creation and migration checks.
_DENSE_CONFIG = models.VectorParams(size=768, distance=models.Distance.COSINE)
_SPEC_CONFIG = models.VectorParams(size=128, distance=models.Distance.COSINE)
_SPARSE_CONFIG = models.SparseVectorParams(modifier=models.Modifier.IDF)


def init_db():
    """Ensures Qdrant collection and payload indexes exist.

    The collection carries three named vectors: dense, spectrogram, sparse.
    Qdrant cannot add a named vector to an existing collection, so if an older
    collection lacks 'spectrogram' we block startup and require the operator to
    delete it and re-ingest (no silent data loss).
    """
    if qdrant_client.collection_exists(config.COLLECTION_NAME):
        info = qdrant_client.get_collection(config.COLLECTION_NAME)
        has_spectrogram = "spectrogram" in (info.config.params.vectors or {})
        if not has_spectrogram:
            print(
                "\n⚠️  MIGRATION: Adding the 'spectrogram' vector requires recreating "
                f"the collection '{config.COLLECTION_NAME}'.\n"
                "   All existing indexed documents must be re-ingested.\n"
                "   Delete the collection and restart to proceed, e.g.:\n"
                f"     curl -X DELETE http://localhost:6333/collections/{config.COLLECTION_NAME}\n"
            )
            raise RuntimeError(
                f"Collection '{config.COLLECTION_NAME}' requires manual migration. "
                "See startup log for instructions."
            )
        return

    qdrant_client.create_collection(
        collection_name=config.COLLECTION_NAME,
        vectors_config={
            "dense": _DENSE_CONFIG,
            "spectrogram": _SPEC_CONFIG,
        },
        sparse_vectors_config={
            "sparse": _SPARSE_CONFIG,
        },
    )
    for field in ("source", "tags", "node_type"):
        qdrant_client.create_payload_index(
            config.COLLECTION_NAME,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )


def update_document_tags(filename: str, tags: list[str]):
    """Overwrites tags for all chunks belonging to a specific document."""
    qdrant_client.set_payload(
        collection_name=config.COLLECTION_NAME,
        payload={"tags": tags},
        points=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source", match=models.MatchValue(value=filename)
                    )
                ]
            )
        ),
    )
    with contextlib.suppress(Exception):
        mongo_store.update_tags(filename, tags)


def ingest(source: str, tags: list[str], **kwargs) -> IngestResult:
    """Routes a source to its registered ingestor plugin and ingests it."""
    ingestor = registry.get_ingestor(source)
    return ingestor.ingest(source, tags, **kwargs)


def search(req: SearchQuery) -> list[SearchResultItem]:
    """Executes the correct search topology (dense, sparse, or RRF hybrid)."""
    query_prefixed = f"search_query: {req.query}"
    query_dense = list(dense_embed_model.embed([query_prefixed]))[0].tolist()
    query_sparse_raw = list(sparse_embed_model.embed([req.query]))[0]
    query_sparse_vec = models.SparseVector(
        indices=query_sparse_raw.indices.tolist(),
        values=query_sparse_raw.values.tolist(),
    )

    query_filter = None
    if req.tags:
        must_conditions = [
            models.FieldCondition(key="tags", match=models.MatchValue(value=t))
            for t in req.tags
        ]
        query_filter = models.Filter(must=must_conditions)

    if req.mode == "dense":
        results = qdrant_client.query_points(
            collection_name=config.COLLECTION_NAME,
            query=query_dense,
            using="dense",
            query_filter=query_filter,
            limit=req.limit,
            with_payload=True,
        ).points
    elif req.mode == "sparse":
        results = qdrant_client.query_points(
            collection_name=config.COLLECTION_NAME,
            query=query_sparse_vec,
            using="sparse",
            query_filter=query_filter,
            limit=req.limit,
            with_payload=True,
        ).points
    else:
        results = qdrant_client.query_points(
            collection_name=config.COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=query_dense,
                    using="dense",
                    limit=req.limit * 2,
                    filter=query_filter,
                ),
                models.Prefetch(
                    query=query_sparse_vec,
                    using="sparse",
                    limit=req.limit * 2,
                    filter=query_filter,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=req.limit,
            with_payload=True,
        ).points

    return [
        SearchResultItem(
            text=pt.payload.get("text", ""),
            score=pt.score if pt.score is not None else 0.0,
            source=pt.payload.get("source", ""),
            chunk_index=pt.payload.get("chunk_index", 0),
            tags=pt.payload.get("tags", []),
        )
        for pt in results
    ]


from . import ingestors  # noqa: E402, F401
from .ingestors.base import registry  # noqa: E402
