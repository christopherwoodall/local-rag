import { api } from "./core/api.js";
import { createBus } from "./core/bus.js";
import { createHost } from "./core/host.js";
import { createModal } from "./core/modal.js";
import { createNotify } from "./core/notify.js";
import { createState } from "./core/state.js";
import { createTags } from "./core/tags.js";
import { PLUGINS } from "./plugins.js";

const bus = createBus();
const state = createState(bus);
const notify = createNotify(document.getElementById("toast-root"));
const modal = createModal(document.getElementById("modal-root"));
const tags = createTags({ api, state, bus, notify, modal });

const services = { api, state, bus, notify, modal, tags };
const host = createHost(services);

async function refreshDocuments() {
  try {
    const docs = await api.listDocuments();
    state.setDocuments(docs);
  } catch (e) {
    notify.error(`Could not load documents: ${e.detail || e.message}`);
  }
}

bus.on("documents:changed", refreshDocuments);

bus.on("ingest:open", () => {
  const plugins = host.getIngestPlugins();
  if (!plugins.length) {
    notify.error("No ingest plugins available");
    return;
  }
  modal.open({ title: "add source", tabs: plugins, width: 460 });
});

await host.loadAll(PLUGINS);
await refreshDocuments();
