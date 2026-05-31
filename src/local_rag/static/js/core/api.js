const API_BASE = "/api";

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseError(res) {
  let detail = res.statusText;
  try {
    const body = await res.json();
    if (body && body.detail) {
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    }
  } catch {
    // non-JSON error body; keep statusText
  }
  return new ApiError(res.status, detail);
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, options);
  } catch (e) {
    throw new ApiError(0, `Network error: ${e.message}`);
  }
  if (!res.ok) throw await parseError(res);
  return res;
}

export const api = {
  async listDocuments() {
    const res = await request("/documents");
    return res.json();
  },

  async getDocument(name) {
    const res = await request(`/document/${encodeURIComponent(name)}`);
    return res.json();
  },

  async updateTags(name, tags) {
    const res = await request(`/tags/${encodeURIComponent(name)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags }),
    });
    return res.json();
  },

  async ingestPdf(file, tags) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("tags", JSON.stringify(tags));
    const res = await request("/ingest", { method: "POST", body: formData });
    return res.json();
  },

  async ingestAudio(file, tags) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("tags", JSON.stringify(tags));
    const res = await request("/ingest/audio", { method: "POST", body: formData });
    if (res.status === 204) return { empty: true };
    return res.json();
  },

  async ingestUrl(url, tags) {
    const res = await request("/ingest/url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, tags }),
    });
    if (res.status === 204) return { empty: true };
    return res.json();
  },

  async search({ query, limit, tags, mode }) {
    const res = await request("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit, tags, mode }),
    });
    return res.json();
  },
};
