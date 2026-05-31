# API Reference

Base URL: `http://localhost:8000`. All JSON endpoints are mounted under the `/api` prefix. Interactive docs are available at `/docs` (Swagger) and `/openapi.json`.

The frontend SPA is served at `/`, and static assets under `/static`.

## Schemas

Defined in `src/local_rag/schemas.py`.

### `SearchQuery`
| Field   | Type        | Default    | Notes                                  |
| ------- | ----------- | ---------- | -------------------------------------- |
| `query` | `str`       | _required_ | Search text.                           |
| `limit` | `int`       | `5`        | Max results.                           |
| `tags`  | `list[str]` | `[]`       | Filter — results must match all tags.  |
| `mode`  | `str`       | `"hybrid"` | One of `hybrid`, `dense`, `sparse`.    |

### `SearchResultItem`
| Field         | Type        | Notes                         |
| ------------- | ----------- | ----------------------------- |
| `text`        | `str`       | Chunk text.                   |
| `score`       | `float`     | Relevance score.              |
| `source`      | `str`       | Document filename or URL.     |
| `chunk_index` | `int`       | Chunk position in the source. |
| `tags`        | `list[str]` | Tags on the chunk.            |

### `DocumentMeta`
| Field    | Type        | Notes                       |
| -------- | ----------- | --------------------------- |
| `name`   | `str`       | Filename / source id.       |
| `chunks` | `int`       | Number of indexed chunks.   |
| `tags`   | `list[str]` | Document tags.              |

### `IngestResult`
| Field         | Type        | Notes                                  |
| ------------- | ----------- | -------------------------------------- |
| `source`      | `str`       | Filename or URL.                       |
| `source_type` | `str`       | `pdf` \| `url` \| `audio`.             |
| `chunks`      | `int`       | Number of chunks indexed.              |
| `tags`        | `list[str]` | Tags applied.                          |

### `URLIngestRequest`
| Field  | Type        | Default    | Notes                       |
| ------ | ----------- | ---------- | --------------------------- |
| `url`  | `HttpUrl`   | _required_ | Must be a valid http(s) URL.|
| `tags` | `list[str]` | `[]`       | Tags to apply.              |

### `TagUpdateRequest`
| Field  | Type        | Default    |
| ------ | ----------- | ---------- |
| `tags` | `list[str]` | _required_ |

> **Multipart `tags` quirk:** the file-upload endpoints (`/api/ingest`, `/api/ingest/audio`) take `tags` as a **JSON-encoded string** form field (e.g. `tags='["research","docs"]'`), defaulting to `"[]"`. The JSON endpoint (`/api/ingest/url`) takes `tags` as a normal JSON array.

---

## Endpoints

### `GET /api/documents`
List all ingested documents (read from MongoDB).

**Response `200`** — `list[DocumentMeta]`
```json
[{ "name": "paper.pdf", "chunks": 12, "tags": ["research"] }]
```

```bash
curl http://localhost:8000/api/documents
```

---

### `GET /api/document/{filename}`
Return the full extracted text / transcript for a document.

- **`200`** — `{ "content": "<markdown or transcript text>" }`
- **`404`** — `{ "detail": "Document not found" }`

```bash
curl http://localhost:8000/api/document/paper.pdf
```

---

### `PATCH /api/tags/{filename}`
Overwrite the tags on every chunk of a document (updates Qdrant payloads and MongoDB).

**Body** — `TagUpdateRequest`
```json
{ "tags": ["research", "ml"] }
```

**Response `200`**
```json
{ "filename": "paper.pdf", "tags": ["research", "ml"] }
```

```bash
curl -X PATCH http://localhost:8000/api/tags/paper.pdf \
  -H "Content-Type: application/json" \
  -d '{"tags":["research","ml"]}'
```

---

### `POST /api/ingest`
Ingest a **PDF** (`multipart/form-data`). Routed to the PDF ingestor by file suffix.

**Form fields**
| Field  | Type            | Default | Notes                              |
| ------ | --------------- | ------- | ---------------------------------- |
| `file` | file            | —       | The `.pdf` file.                   |
| `tags` | string (JSON)   | `"[]"`  | JSON-encoded list of tags.         |

**Responses**
- **`200`** — `{ "message": "Successfully ingested <name>", "chunks": <n> }`
- **`200`** (no extractable text) — `{ "message": "No text extracted." }`
- **`422`** — `{ "detail": "<error>" }` (e.g. unsupported source)

```bash
curl -X POST http://localhost:8000/api/ingest \
  -F 'file=@paper.pdf' \
  -F 'tags=["research"]'
```

> **Note:** this endpoint returns a `{message, chunks}` object (not `IngestResult`), unlike the URL/audio endpoints below.

---

### `POST /api/ingest/url`
Fetch a web page, extract clean markdown, chunk, embed, and store. (`application/json`)

**Body** — `URLIngestRequest`
```json
{ "url": "https://example.com/article", "tags": ["web"] }
```

**Responses**
- **`200`** — `IngestResult`
- **`204`** — no content could be extracted (nothing stored).
- **`422`** — fetch failed (non-2xx) or extraction error.

```bash
curl -X POST http://localhost:8000/api/ingest/url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/article","tags":["web"]}'
```

Example `200` body:
```json
{ "source": "https://example.com/article", "source_type": "url", "chunks": 7, "tags": ["web"] }
```

---

### `POST /api/ingest/audio`
Transcribe an audio file with Whisper, embed the transcript, and store with a spectrogram vector. (`multipart/form-data`)

**Form fields**
| Field  | Type            | Default | Notes                                          |
| ------ | --------------- | ------- | ---------------------------------------------- |
| `file` | file            | —       | `.mp3`, `.wav`, `.m4a`, or `.ogg`.             |
| `tags` | string (JSON)   | `"[]"`  | JSON-encoded list of tags.                     |

**Responses**
- **`200`** — `IngestResult` (`source_type: "audio"`)
- **`400`** — unsupported audio format.
- **`422`** — no speech detected / transcript could not be chunked.
- **`204`** — zero chunks produced (nothing stored).

```bash
curl -X POST http://localhost:8000/api/ingest/audio \
  -F 'file=@meeting.mp3' \
  -F 'tags=["meetings"]'
```

> Transcription is CPU-bound and can take **several minutes**. The request blocks until it completes.

---

### `POST /api/search`
Run a vector search. (`application/json`)

**Body** — `SearchQuery`
```json
{ "query": "vector databases", "limit": 5, "tags": ["research"], "mode": "hybrid" }
```

**Search modes**
- `hybrid` (default) — RRF fusion over `dense` + `sparse` (requires Qdrant ≥ 1.10).
- `dense` — dense vector only.
- `sparse` — sparse (BM25) vector only.

**Response `200`** — `list[SearchResultItem]`
```json
[{ "text": "…", "score": 0.83, "source": "paper.pdf", "chunk_index": 3, "tags": ["research"] }]
```

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"vector databases","limit":5,"mode":"hybrid"}'
```
