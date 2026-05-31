"""Driver: ingest an audio file via POST /api/ingest/audio (multipart/form-data).

Transcription is CPU-bound and may take several minutes.
"""

from __future__ import annotations

import sys
from pathlib import Path

from _client import client, parse_tags, show, tags_field

DEFAULT_AUDIO = Path(__file__).resolve().parents[1] / "samples" / "audio.mp3"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_AUDIO
    if not path.is_file():
        print(f"file not found: {path}")
        return 1

    tags = parse_tags(sys.argv[2] if len(sys.argv) > 2 else None)

    print(f"Uploading {path.name} … transcription may take several minutes.")
    with client() as c, open(path, "rb") as f:
        resp = c.post(
            "/api/ingest/audio",
            files={"file": (path.name, f, "audio/mpeg")},
            data={"tags": tags_field(tags)},
        )
    show(resp, "/api/ingest/audio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
