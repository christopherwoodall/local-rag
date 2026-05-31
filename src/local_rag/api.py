import contextlib
import json
import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from . import config, engine
from .schemas import (
    DocumentMeta,
    SearchQuery,
    SearchResultItem,
    TagUpdateRequest,
    URLIngestRequest,
)
from .store import mongo_store

router = APIRouter(prefix="/api")


def _safe_upload_path(filename: str) -> Path:
    """Resolves a user-supplied filename strictly within the upload directory.

    Rejects path traversal (``../``) and absolute paths before any filesystem
    access, returning a 400.
    """
    base = config.UPLOAD_DIR.resolve()
    candidate = (base / filename).resolve()
    if not candidate.is_relative_to(base):
        raise HTTPException(400, "Invalid filename")
    return candidate


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
    spectrogram = (
        engine.get_spectrogram(filename) if record.source_type == "audio" else None
    )
    return {
        "content": record.markdown_content,
        "source_type": record.source_type,
        "source_url": record.source_url,
        "spectrogram": spectrogram,
    }


@router.get("/file/{filename}")
def get_file(filename: str):
    path = _safe_upload_path(filename)
    if not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path)


@router.delete("/document/{filename}")
def delete_document(filename: str):
    path = _safe_upload_path(filename)
    engine.delete_document(filename)
    with contextlib.suppress(Exception):
        mongo_store.delete_document(filename)
    path.unlink(missing_ok=True)
    return {"deleted": filename}


@router.patch("/tags/{filename}")
def update_tags(filename: str, body: TagUpdateRequest):
    engine.update_document_tags(filename, body.tags)
    return {"filename": filename, "tags": body.tags}


@router.post("/ingest")
async def ingest_pdf(
    file: Annotated[UploadFile, File(...)], tags: Annotated[str, Form()] = "[]"
):
    tag_list = json.loads(tags)
    safe_name = Path(file.filename).name
    dest = config.UPLOAD_DIR / safe_name
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        result = engine.ingest(str(dest), tag_list, filename=safe_name)
    except ValueError as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, str(e)) from e

    if result.chunks == 0:
        dest.unlink(missing_ok=True)
        return {"message": "No text extracted."}
    return {
        "message": f"Successfully ingested {safe_name}",
        "chunks": result.chunks,
    }


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
    safe_name = Path(file.filename).name
    dest = config.UPLOAD_DIR / safe_name
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        result = engine.ingest(str(dest), tag_list, filename=safe_name)
    except ValueError as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, str(e)) from e

    if result.chunks == 0:
        dest.unlink(missing_ok=True)
        return Response(status_code=204)
    return result


@router.post("/search", response_model=list[SearchResultItem])
def search_knowledge(search_req: SearchQuery):
    return engine.search(search_req)
