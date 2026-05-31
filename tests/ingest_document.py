"""Driver: ingest a document (PDF) via POST /api/ingest (multipart/form-data)."""

from __future__ import annotations

import sys
from pathlib import Path

from _client import client, parse_tags, show, tags_field


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python tests/ingest_document.py <file.pdf> [tag1,tag2]")
        return 2

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"file not found: {path}")
        return 1

    tags = parse_tags(sys.argv[2] if len(sys.argv) > 2 else None)

    print(f"Uploading {path.name} …")
    with client() as c, open(path, "rb") as f:
        resp = c.post(
            "/api/ingest",
            files={"file": (path.name, f, "application/pdf")},
            data={"tags": tags_field(tags)},
        )
    show(resp, "/api/ingest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
