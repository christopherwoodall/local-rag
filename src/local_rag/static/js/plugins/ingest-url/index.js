function isValidHttpUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

export default {
  id: "ingest-url",
  label: "URL",
  icon: "ti-link",
  slot: "ingest",
  templateUrl: "/static/js/plugins/ingest-url/template.html",
  styleUrl: "/static/js/plugins/ingest-url/style.css",

  async mount({ root, api, bus, notify, modal, tags }) {
    const ref = (name) => root.querySelector(`[data-ref="${name}"]`);
    const urlInput = ref("url");
    const submit = ref("submit");
    const tagsField = tags.tagInput([]);
    ref("tagsMount").appendChild(tagsField.element);

    async function run() {
      const url = urlInput.value.trim();
      if (!isValidHttpUrl(url)) {
        notify.error("Enter a valid http(s) URL");
        return;
      }
      submit.disabled = true;
      submit.textContent = "fetching…";
      try {
        const res = await api.ingestUrl(url, tagsField.getTags());
        if (res.empty) {
          notify.info(`No extractable content at ${url}`);
        } else if (res.chunks) {
          notify.success(`Ingested ${res.chunks} chunks from ${url}`);
          bus.emit("documents:changed");
          modal.close();
        } else {
          notify.info("Nothing ingested.");
        }
      } catch (e) {
        notify.error(e.detail || e.message);
      } finally {
        submit.disabled = false;
        submit.textContent = "ingest url";
      }
    }

    submit.addEventListener("click", run);
    urlInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") run();
    });
  },
};
