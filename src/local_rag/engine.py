import uuid

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models

from . import config
from .schemas import DocumentMeta, SearchQuery, SearchResultItem

print("Loading ML models and initializing DB connections...")
qdrant_client = QdrantClient(host=config.QDRANT_HOST, port=6333)
dense_embed_model = TextEmbedding(model_name="nomic-ai/nomic-embed-text-v1.5")
sparse_embed_model = SparseTextEmbedding(model_name="Qdrant/bm25")
doc_converter = DocumentConverter()
chunker = HybridChunker()


def init_db():
    """Ensures Qdrant collection and payload indexes exist."""
    if not qdrant_client.collection_exists(config.COLLECTION_NAME):
        qdrant_client.create_collection(
            collection_name=config.COLLECTION_NAME,
            vectors_config={
                "dense": models.VectorParams(size=768, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
        )
        qdrant_client.create_payload_index(
            config.COLLECTION_NAME,
            field_name="source",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        qdrant_client.create_payload_index(
            config.COLLECTION_NAME,
            field_name="tags",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )


def get_all_documents() -> list[DocumentMeta]:
    """Aggregates all distinct documents and their associated tags from Qdrant."""
    results, _ = qdrant_client.scroll(
        collection_name=config.COLLECTION_NAME,
        with_payload=["source", "tags"],
        limit=10000,
    )
    doc_map = {}
    for point in results[0]:
        src = point.payload.get("source")
        if not src:
            continue
        if src not in doc_map:
            doc_map[src] = {"name": src, "chunks": 0, "tags": set()}
        doc_map[src]["chunks"] += 1
        doc_map[src]["tags"].update(point.payload.get("tags", []))

    return [
        DocumentMeta(name=v["name"], chunks=v["chunks"], tags=list(v["tags"]))
        for v in doc_map.values()
    ]


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


def process_and_ingest(file_path: str, filename: str, tags: list[str]) -> int:
    """Extracts, chunks, embeds, and pushes a PDF to Qdrant."""
    # Delete existing chunks for idempotency
    qdrant_client.delete(
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

    conversion_result = doc_converter.convert(file_path)
    markdown_text = conversion_result.document.export_to_markdown()

    with open(config.DOCS_DIR / f"{filename}.md", "w", encoding="utf-8") as f:
        f.write(markdown_text)

    chunks = [
        c.text for c in chunker.chunk(conversion_result.document) if c.text.strip()
    ]
    if not chunks:
        return 0

    chunks_prefixed = [f"search_document: {c}" for c in chunks]
    dense_vectors = list(dense_embed_model.embed(chunks_prefixed))
    sparse_vectors = list(sparse_embed_model.embed(chunks))

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
                },
                payload={
                    "text": chunk,
                    "source": filename,
                    "chunk_index": idx,
                    "tags": tags,
                },
            )
        )

    qdrant_client.upsert(collection_name=config.COLLECTION_NAME, points=points)
    return len(chunks)


def search(req: SearchQuery) -> list[SearchResultItem]:
    """Executes the correct search topology (dense, sparse, or RRF hybrid)."""
    query_prefixed = f"search_query: {req.query}"
    query_dense = list(dense_embed_model.embed([query_prefixed]))[0].tolist()
    query_sparse_raw = list(sparse_embed_model.embed([req.query]))[0]
    query_sparse = {
        "indices": query_sparse_raw.indices.tolist(),
        "values": query_sparse_raw.values.tolist(),
    }

    query_filter = None
    if req.tags:
        must_conditions = [
            models.FieldCondition(key="tags", match=models.MatchValue(value=t))
            for t in req.tags
        ]
        query_filter = models.Filter(must=must_conditions)

    if req.mode == "dense":
        results = qdrant_client.search(
            collection_name=config.COLLECTION_NAME,
            query_vector=("dense", query_dense),
            query_filter=query_filter,
            limit=req.limit,
        )
    elif req.mode == "sparse":
        results = qdrant_client.search(
            collection_name=config.COLLECTION_NAME,
            query_vector=("sparse", query_sparse),
            query_filter=query_filter,
            limit=req.limit,
        )
    else:
        prefetch = [
            models.Prefetch(vector={"dense": query_dense}, limit=req.limit),
            models.Prefetch(vector={"sparse": query_sparse}, limit=req.limit),
        ]
        results = qdrant_client.query_points(
            collection_name=config.COLLECTION_NAME,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=query_filter,
            limit=req.limit,
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
