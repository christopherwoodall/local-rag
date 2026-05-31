export function createState(bus) {
  const data = {
    documents: [],
    globalTags: new Set(),
    activeTags: new Set(),
    mode: "hybrid",
    currentDoc: null,
  };

  function setDocuments(docs) {
    data.documents = Array.isArray(docs) ? docs : [];
    data.globalTags = new Set();
    data.documents.forEach((d) => (d.tags || []).forEach((t) => data.globalTags.add(t)));
    data.activeTags.forEach((t) => {
      if (!data.globalTags.has(t)) data.activeTags.delete(t);
    });
    bus.emit("state:documents", data.documents);
  }

  function toggleActiveTag(tag) {
    if (data.activeTags.has(tag)) data.activeTags.delete(tag);
    else data.activeTags.add(tag);
    bus.emit("state:filters", Array.from(data.activeTags));
  }

  function clearActiveTags() {
    data.activeTags.clear();
    bus.emit("state:filters", []);
  }

  function setMode(mode) {
    data.mode = mode;
    bus.emit("state:mode", mode);
  }

  function setCurrentDoc(name) {
    data.currentDoc = name;
    bus.emit("state:currentDoc", name);
  }

  return {
    get documents() {
      return data.documents;
    },
    get globalTags() {
      return data.globalTags;
    },
    get activeTags() {
      return data.activeTags;
    },
    get mode() {
      return data.mode;
    },
    get currentDoc() {
      return data.currentDoc;
    },
    findDocument(name) {
      return data.documents.find((d) => d.name === name) || null;
    },
    setDocuments,
    toggleActiveTag,
    clearActiveTags,
    setMode,
    setCurrentDoc,
  };
}
