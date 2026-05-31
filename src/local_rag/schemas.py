from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class SearchQuery(BaseModel):
    query: str
    limit: int = 5
    tags: list[str] = []
    mode: str = "hybrid"


class SearchResultItem(BaseModel):
    text: str
    score: float
    source: str
    chunk_index: int
    tags: list[str] = []


class DocumentMeta(BaseModel):
    name: str
    chunks: int
    tags: list[str]


class IngestResult(BaseModel):
    source: str
    source_type: str
    chunks: int
    tags: list[str]


class TagUpdateRequest(BaseModel):
    tags: list[str]


class URLIngestRequest(BaseModel):
    url: HttpUrl
    tags: list[str] = []


class DocumentRecord(BaseModel):
    filename: str
    source_type: str
    tags: list[str] = []
    chunk_count: int = 0
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    markdown_content: str = ""
    source_url: str | None = None
    content_hash: str | None = None
