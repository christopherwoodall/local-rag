import json
import os
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastembed import SparseTextEmbedding, TextEmbedding
from pydantic import BaseModel
from qdrant_client import QdrantClient, models

# --- Path Resolution for Packaged UI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DOCS_DIR = os.getenv("DOCS_DIR", "./documents")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
qdrant_client = QdrantClient(host=QDRANT_HOST, port=6333)
COLLECTION_NAME = "local_agent_knowledge"

print("Loading local embedding models via ONNX...")
dense_embed_model = TextEmbedding(model_name="nomic-ai/nomic-embed-text-v1.5")
sparse_embed_model = SparseTextEmbedding(model_name="Qdrant/bm25")

doc_converter = DocumentConverter()
chunker = HybridChunker()


# --- Startup Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure necessary directories exist
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)

    if not qdrant_client.collection_exists(COLLECTION_NAME):
        print(f"Creating hybrid collection: {COLLECTION_NAME}")
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "dense": models.VectorParams(size=768, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
        )
        # Create payload indexes for fast filtering
        qdrant_client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="source",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        qdrant_client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="tags",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
    yield


app = FastAPI(title="Mac Mini Local Agent RAG API", lifespan=lifespan)

# Mount the static UI directory using the absolute path
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Pydantic Schemas ---
class SearchQuery(BaseModel):
    query: str
    limit: int = 5
    tags: list[str] = []  # Optional tag filters
    mode: str = "hybrid"  # "hybrid", "dense", or "sparse"


class SearchResultItem(BaseModel):
    text: str
    score: float
    source: str
    chunk_index: int
    tags: list[str] = []


# --- UI & Reader Endpoints ---


@app.get("/")
def serve_ui():
    """Serves the main dashboard UI."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/document/{filename}")
def get_document_text(filename: str):
    """Serves the full markdown for the reader tab."""
    path = os.path.join(DOCS_DIR, f"{filename}.md")
    if not os.path.exists(path):
        raise HTTPException(404, "Document not found")
    with open(path, encoding="utf-8") as f:
        return {"content": f.read()}


# --- Tag Management Endpoints ---


@app.get("/tags")
async def get_all_tags():
    """Returns a map of filenames to their associated tags."""
    results, _ = qdrant_client.scroll(
        collection_name=COLLECTION_NAME, with_payload=["source", "tags"], limit=10000
    )
    tag_map = {}
    for point in results[0]:
        src = point.payload.get("source", "")
        tags = point.payload.get("tags", [])
        if src not in tag_map:
            tag_map[src] = set()
        tag_map[src].update(tags)

    return {k: list(v) for k, v in tag_map.items()}


@app.patch("/tags/{filename}")
async def update_tags(filename: str, body: dict[str, Any]):
    """Updates the tags for all chunks of a specific document."""
    new_tags = body.get("tags", [])
    qdrant_client.set_payload(
        collection_name=COLLECTION_NAME,
        payload={"tags": new_tags},
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
    return {"filename": filename, "tags": new_tags}


# --- Core RAG Endpoints ---


@app.post("/ingest", status_code=201)
async def ingest_pdf(
    file: Annotated[UploadFile, File(...)],
    tags: Annotated[str, Form()] = "[]",
    # TODO: Fix linting errors
    # file: UploadFile = File(...),
    # tags: str = Form(default="[]") # Accept tags as a JSON string array
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    tag_list = json.loads(tags)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        # Idempotency: Delete old chunks for this file
        qdrant_client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source", match=models.MatchValue(value=file.filename)
                        )
                    ]
                )
            ),
        )

        # Extraction & Chunking via Docling
        conversion_result = doc_converter.convert(temp_path)
        markdown_text = conversion_result.document.export_to_markdown()

        # Save markdown locally for the Reader UI
        with open(
            os.path.join(DOCS_DIR, f"{file.filename}.md"), "w", encoding="utf-8"
        ) as f:
            f.write(markdown_text)

        chunk_iter = chunker.chunk(conversion_result.document)
        chunks = [chunk.text for chunk in chunk_iter if chunk.text.strip()]

        if not chunks:
            return {"message": "No text extracted."}

        # Add required prefix for Nomic embedding model
        chunks_prefixed = [f"search_document: {c}" for c in chunks]
        dense_vectors = list(dense_embed_model.embed(chunks_prefixed))
        sparse_vectors = list(sparse_embed_model.embed(chunks))

        points = []
        for idx, chunk in enumerate(chunks):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{file.filename}_{idx}"))
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
                        "source": file.filename,
                        "chunk_index": idx,
                        "tags": tag_list,  # Inject tags directly into payload
                    },
                )
            )

        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
        return {
            "message": f"Successfully ingested {file.filename}",
            "chunks": len(chunks),
        }

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/search", response_model=list[SearchResultItem])
async def search_knowledge(search_req: SearchQuery):
    query_prefixed = f"search_query: {search_req.query}"

    query_dense = list(dense_embed_model.embed([query_prefixed]))[0].tolist()
    query_sparse_raw = list(sparse_embed_model.embed([search_req.query]))[0]
    query_sparse = {
        "indices": query_sparse_raw.indices.tolist(),
        "values": query_sparse_raw.values.tolist(),
    }

    # Apply tag filtering (Intersection: document must have ALL requested tags)
    query_filter = None
    if search_req.tags:
        must_conditions = [
            models.FieldCondition(key="tags", match=models.MatchValue(value=t))
            for t in search_req.tags
        ]
        query_filter = models.Filter(must=must_conditions)

    # Configure search strategies based on UI toggle
    if search_req.mode == "dense":
        results = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=("dense", query_dense),
            query_filter=query_filter,
            limit=search_req.limit,
        )
    elif search_req.mode == "sparse":
        results = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=("sparse", query_sparse),
            query_filter=query_filter,
            limit=search_req.limit,
        )
    else:  # Hybrid RRF
        prefetch = [
            models.Prefetch(vector={"dense": query_dense}, limit=search_req.limit),
            models.Prefetch(vector={"sparse": query_sparse}, limit=search_req.limit),
        ]
        results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=query_filter,
            limit=search_req.limit,
        ).points

    return [
        SearchResultItem(
            text=point.payload.get("text", ""),
            score=point.score if point.score is not None else 0.0,
            source=point.payload.get("source", ""),
            chunk_index=point.payload.get("chunk_index", 0),
            tags=point.payload.get("tags", []),
        )
        for point in results
    ]


def start():
    """Entry point for the mac-rag-server command line script."""
    import uvicorn

    # Make accessible across your local network
    uvicorn.run("local_rag.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    start()
