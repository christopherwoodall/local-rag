import json
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from . import engine
from .schemas import (
    DocumentMeta,
    SearchQuery,
    SearchResultItem,
    TagUpdateRequest,
    URLIngestRequest,
)
from .store import mongo_store

router = APIRouter(prefix="/api")


@router.get("/documents", response_model=list[DocumentMeta])
async def get_documents():
    records = await mongo_store.list_documents()
    return [
        DocumentMeta(name=r.filename, chunks=r.chunk_count, tags=r.tags)
        for r in records
    ]


@router.get("/document/{filename}")
async def get_document_text(filename: str):
    record = await mongo_store.get_document(filename)
    if not record:
        raise HTTPException(404, "Document not found")
    return {"content": record.markdown_content}


@router.patch("/tags/{filename}")
def update_tags(filename: str, body: TagUpdateRequest):
    engine.update_document_tags(filename, body.tags)
    return {"filename": filename, "tags": body.tags}


@router.post("/ingest")
async def ingest_pdf(
    file: Annotated[UploadFile, File(...)], tags: Annotated[str, Form()] = "[]"
):
    tag_list = json.loads(tags)
    with tempfile.NamedTemporaryFile(
        suffix=Path(file.filename).suffix, delete=False
    ) as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        result = engine.ingest(temp_path, tag_list, filename=file.filename)
        if result.chunks == 0:
            return {"message": "No text extracted."}
        return {
            "message": f"Successfully ingested {file.filename}",
            "chunks": result.chunks,
        }
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    finally:
        Path(temp_path).unlink(missing_ok=True)


@router.post(
    "/ingest/url",
    summary="Ingest a URL",
    description="Fetch a web page, extract clean markdown, chunk, embed, and store in the knowledge base.",
)
async def ingest_url(body: URLIngestRequest):
    try:
        result = engine.ingest(str(body.url), body.tags)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if result.chunks == 0:
        return Response(status_code=204)
    return result


@router.post(
    "/ingest/audio",
    summary="Ingest an audio file",
    description="Transcribe audio with Whisper, embed the transcript, and store with a spectrogram vector.",
)
async def ingest_audio(
    file: Annotated[UploadFile, File(...)],
    tags: Annotated[str, Form()] = "[]",
):
    allowed_suffixes = (".mp3", ".wav", ".m4a", ".ogg")
    if not file.filename.lower().endswith(allowed_suffixes):
        raise HTTPException(
            400, f"Unsupported audio format. Allowed: {list(allowed_suffixes)}"
        )

    tag_list = json.loads(tags)
    with tempfile.NamedTemporaryFile(
        suffix=Path(file.filename).suffix, delete=False
    ) as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        result = engine.ingest(temp_path, tag_list, filename=file.filename)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    finally:
        Path(temp_path).unlink(missing_ok=True)

    if result.chunks == 0:
        return Response(status_code=204)
    return result


@router.post("/search", response_model=list[SearchResultItem])
def search_knowledge(search_req: SearchQuery):
    return engine.search(search_req)
