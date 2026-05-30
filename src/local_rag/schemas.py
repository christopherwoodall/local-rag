from pydantic import BaseModel


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


class TagUpdateRequest(BaseModel):
    tags: list[str]
