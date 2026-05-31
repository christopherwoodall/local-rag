"""Shared helpers for the ingestion test drivers.

Start the API first (e.g. `make run`), then drive an endpoint:

    uv run python tests/ingest_document.py path/to/file.pdf tag1,tag2
    uv run python tests/ingest_url.py https://example.com tag1,tag2
    uv run python tests/ingest_audio.py            # defaults to samples/audio.mp3

Override the target server with RAG_BASE_URL (default http://127.0.0.1:8000).
"""

from __future__ import annotations

import json
import os

import httpx

BASE_URL = os.getenv("RAG_BASE_URL", "http://127.0.0.1:8000")


def parse_tags(raw: str | None) -> list[str]:
    """Turn a comma-separated CLI string into a clean tag list."""
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def tags_field(tags: list[str]) -> str:
    """Encode tags the way the multipart endpoints expect (a JSON string)."""
    return json.dumps(tags)


def client() -> httpx.Client:
    # No timeout: audio transcription is CPU-bound and can take several minutes.
    return httpx.Client(base_url=BASE_URL, timeout=None)


def show(resp: httpx.Response, path: str) -> None:
    print(f"POST {path} -> {resp.status_code}")
    if resp.status_code == 204:
        print("(204 No Content — nothing was ingested)")
        return
    try:
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except ValueError:
        print(resp.text)
