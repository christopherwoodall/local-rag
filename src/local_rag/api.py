import json
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from . import config, engine
from .schemas import DocumentMeta, SearchQuery, SearchResultItem, TagUpdateRequest

router = APIRouter(prefix="/api")


@router.get("/documents", response_model=list[DocumentMeta])
def get_documents():
    return engine.get_all_documents()


@router.get("/document/{filename}")
def get_document_text(filename: str):
    path = config.DOCS_DIR / f"{filename}.md"
    if not path.exists():
        raise HTTPException(404, "Document not found on disk")
    with open(path, encoding="utf-8") as f:
        return {"content": f.read()}


@router.patch("/tags/{filename}")
def update_tags(filename: str, body: TagUpdateRequest):
    engine.update_document_tags(filename, body.tags)
    return {"filename": filename, "tags": body.tags}


@router.post("/ingest")
async def ingest_pdf(
    file: Annotated[UploadFile, File(...)], tags: Annotated[str, Form()] = "[]"
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDFs are supported.")

    tag_list = json.loads(tags)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        chunks_processed = engine.process_and_ingest(temp_path, file.filename, tag_list)
        if chunks_processed == 0:
            return {"message": "No text extracted."}
        return {
            "message": f"Successfully ingested {file.filename}",
            "chunks": chunks_processed,
        }
    finally:
        Path(temp_path).unlink(missing_ok=True)


@router.post("/search", response_model=list[SearchResultItem])
def search_knowledge(search_req: SearchQuery):
    return engine.search(search_req)
