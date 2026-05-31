# Local RAG

A fully local, Apple-Silicon-optimized Retrieval-Augmented Generation (RAG) server. Ingest **PDFs, web pages, and audio**, then run **hybrid vector search** over the results — all on your own machine, with a built-in modular web UI.

- **Qdrant** — hybrid vector store (dense + sparse + spectrogram vectors), the source of truth for search.
- **MongoDB** — metadata and full document/transcript content backing the library and reader UI.
- **Docling** — structured PDF parsing and chunking.
- **FastEmbed (ONNX)** — CPU-accelerated dense (`nomic-embed-text-v1.5`) and sparse (BM25) embeddings.
- **faster-whisper** — local CPU audio transcription (CTranslate2, Apple-Silicon friendly).
- **FastAPI** — JSON API plus a vanilla ES-module plugin frontend served at `/`.

## Architecture summary

The system is a **dual store**:

- **Qdrant** holds all vectors and is authoritative for retrieval. The collection (`local_agent_knowledge`) carries **three named vectors**: `dense` (768-dim, COSINE), `sparse` (BM25/IDF), and `spectrogram` (128-dim log-mel, COSINE).
- **MongoDB** holds document metadata and the full extracted text/transcript used by the UI's document list and reader. MongoDB writes are **non-critical** — if Mongo is unavailable, ingestion and search still work (only the metadata/library features degrade).

Ingestion is handled by **self-registering ingestor plugins** (PDF, URL, Audio) routed by source type, and the frontend is a **manifest-driven plugin system** loaded as native ES modules. For details see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

> **Note:** The `spectrogram` vector is currently **stored but not yet queried** by any endpoint — it is reserved for future audio-similarity search. Search today uses `dense`, `sparse`, or `hybrid` (RRF) modes.

## Prerequisites

- **Docker** with **Compose v2** (`docker compose ...`). Docker Desktop or OrbStack (recommended on macOS).
- **Python 3.13** (the project pins `requires-python == 3.13`).
- **[uv](https://docs.astral.sh/uv/)** for dependency management and running.

## Quick start

```bash
# 1. Install dependencies (creates/updates the .venv via uv)
make install

# 2. Start the backing services (Qdrant + MongoDB) in the background
make up

# 3. Start the API server (also ensures services are up)
make run
```

Then open:

- **Web UI** — http://localhost:8000
- **Swagger / OpenAPI** — http://localhost:8000/docs

Press `Ctrl+C` to stop the server. Stop the Docker services with `make down`.

> **First run is slow.** On first startup the server downloads the embedding models and the Whisper `medium` model (~1.5 GB). Subsequent starts are fast.

## Configuration

Configuration is via environment variables (sensible localhost defaults):

| Variable      | Default                     | Description                          |
| ------------- | --------------------------- | ------------------------------------ |
| `QDRANT_HOST` | `localhost`                 | Qdrant host (REST on port `6333`).   |
| `MONGO_URI`   | `mongodb://localhost:27017` | MongoDB connection string.           |
| `MONGO_DB`    | `rag`                       | MongoDB database name.               |

| Service     | Port    |
| ----------- | ------- |
| API server  | `8000`  |
| Qdrant REST | `6333`  |
| MongoDB     | `27017` |

## Make commands

| Command        | Description                                                        |
| -------------- | ----------------------------------------------------------------- |
| `make install` | Install all dependencies (incl. dev) via `uv sync --extra dev`.   |
| `make up`      | Start Docker services (Qdrant + MongoDB).                         |
| `make down`    | Stop and remove Docker services (database data is preserved).     |
| `make serve`   | Run the RAG API server (uvicorn on `:8000`).                      |
| `make run`     | Start Docker services, then run the API server.                  |
| `make logs`    | Tail Docker service logs (Qdrant + MongoDB).                      |
| `make clean`   | Stop services + remove build/cache artifacts (**keeps DB data**). |
| `make lint`    | Lint and format the code with Ruff.                              |
| `make build`   | Build the application wheel.                                     |
| `make tree`    | Show the source tree.                                            |
| `make lines`   | Count lines of code.                                            |

## Known gotchas

### Apple Silicon / Whisper is CPU-only
The Whisper model is loaded with `device="cpu"` and `compute_type="int8"` — there is **no CUDA on Apple Silicon**, so do not change this. The `medium` model downloads (~1.5 GB) on first run and transcription is **CPU-bound and blocking**: ingesting audio can take several minutes. This is expected for a local home server.

### Qdrant schema migration is manual
Hybrid search uses Qdrant's RRF `FusionQuery`, which requires **Qdrant ≥ 1.10**; the Compose file pins `qdrant/qdrant:v1.18.0` to match the client.

The collection includes a `spectrogram` vector. **Qdrant cannot add a named vector to an existing collection**, so if you have an older collection that predates it, the server fails fast on startup with a `RuntimeError`. To migrate (this **deletes indexed vectors** — you must re-ingest):

```bash
curl -X DELETE http://localhost:6333/collections/local_agent_knowledge
```

Then restart the server; it recreates the collection with all three vectors. Document/transcript text in MongoDB is unaffected, but vectors must be rebuilt by re-ingesting.

> **Upgrading from a pre-1.18 Qdrant.** Qdrant 1.18 cannot load on-disk data written by much older versions (e.g. 1.9's segment format), and the container will **crash-loop on start** (`unknown variant 'on_disk'`). Because the collection must be recreated for the schema change anyway, the simplest fix is to clear the local Qdrant data directory and start fresh (only the vectors live here — re-ingest to rebuild them):
> ```bash
> make down
> rm -rf ./qdrant_storage      # destroys local vectors; MongoDB content is untouched
> make up
> ```

### MongoDB is optional but powers the UI
If MongoDB is down, the server still starts and vector search still works, but metadata features degrade: the document list (`GET /api/documents`), the reader (`GET /api/document/{filename}`), and tag persistence rely on MongoDB.

## Running as a macOS background service (launchd)

To keep the server running in the background and restart on crash/login, use `launchd`.

Create `~/Library/LaunchAgents/com.local.local-rag.plist` (replace `/Users/YOUR_USERNAME/path/to/local-rag` with your absolute project path):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.local.local-rag</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/path/to/local-rag/.venv/bin/start-rag-server</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/path/to/local-rag</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>QDRANT_HOST</key>
        <string>localhost</string>
        <key>MONGO_URI</key>
        <string>mongodb://localhost:27017</string>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/path/to/local-rag/server.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/path/to/local-rag/server_error.log</string>
</dict>
</plist>
```

Load and manage it:

```bash
launchctl load ~/Library/LaunchAgents/com.local.local-rag.plist   # load + start (RunAtLoad)
launchctl stop com.local.local-rag                                 # stop
launchctl unload ~/Library/LaunchAgents/com.local.local-rag.plist  # disable
tail -f /Users/YOUR_USERNAME/path/to/local-rag/server.log          # logs
```

> Qdrant and MongoDB must be running before the server starts. Ensure Docker is set to start on login so the Compose services are available.
