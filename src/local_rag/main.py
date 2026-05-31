from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, engine, store
from .api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    engine.init_db()
    store.init_store()
    yield


app = FastAPI(title="Mac Mini Local RAG", lifespan=lifespan)

# Mount the JSON API router
app.include_router(router)

# Mount static frontend
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.get("/")
def serve_ui():
    """Serves the main frontend application."""
    return FileResponse(config.STATIC_DIR / "index.html")


def start():
    """Entry point mapped to start-rag-server in pyproject.toml."""
    import uvicorn

    uvicorn.run("local_rag.main:app", host="0.0.0.0", port=8000, reload=False)
