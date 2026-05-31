"""Driver: ingest a web page via POST /api/ingest/url (application/json)."""

from __future__ import annotations

import sys

from _client import client, parse_tags, show

DEFAULT_URL = "https://example.com"


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    tags = parse_tags(sys.argv[2] if len(sys.argv) > 2 else None)

    print(f"Ingesting {url} …")
    with client() as c:
        resp = c.post("/api/ingest/url", json={"url": url, "tags": tags})
    show(resp, "/api/ingest/url")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
