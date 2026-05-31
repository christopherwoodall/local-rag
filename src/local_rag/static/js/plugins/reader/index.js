import { el, renderMarkdown } from "../../core/dom.js";

export default {
  id: "reader",
  label: "reader",
  icon: "ti-file-text",
  slot: "panel",
  templateUrl: "/static/js/plugins/reader/template.html",
  styleUrl: "/static/js/plugins/reader/style.css",

  async mount({ root, api, state, bus, notify, tags }) {
    const ref = (name) => root.querySelector(`[data-ref="${name}"]`);
    const empty = ref("empty");
    const content = ref("content");
    const title = ref("title");
    const tagRow = ref("tagRow");
    const body = ref("body");
    const media = ref("media");
    const download = ref("download");
    let currentName = null;

    function renderSpectrogram(container, spec) {
      const width = 512;
      const height = 64;
      const canvas = el("canvas", { class: "spectrogram", width, height });
      container.appendChild(canvas);
      const ctx = canvas.getContext("2d");
      const n = spec.length;
      let min = Infinity;
      let max = -Infinity;
      for (const v of spec) {
        if (v < min) min = v;
        if (v > max) max = v;
      }
      const range = max - min || 1;
      const colWidth = width / n;
      ctx.strokeStyle =
        getComputedStyle(document.documentElement)
          .getPropertyValue("--color-text-secondary")
          .trim() || "#888";
      ctx.lineWidth = Math.max(1, colWidth * 0.6);
      for (let i = 0; i < n; i++) {
        const barH = ((spec[i] - min) / range) * (height - 2) + 1;
        const x = i * colWidth + colWidth / 2;
        ctx.beginPath();
        ctx.moveTo(x, height);
        ctx.lineTo(x, height - barH);
        ctx.stroke();
      }
    }

    function renderMedia(name, data) {
      media.innerHTML = "";
      const isUrl = data.source_type === "url";
      download.style.display = isUrl ? "none" : "";
      if (!isUrl) download.href = api.fileUrl(name);
      if (data.source_type === "audio") {
        media.appendChild(
          el("audio", { class: "reader-audio", controls: true, src: api.fileUrl(name) })
        );
        if (Array.isArray(data.spectrogram) && data.spectrogram.length) {
          renderSpectrogram(media, data.spectrogram);
        }
      }
    }

    function renderTagRow() {
      tagRow.innerHTML = "";
      const doc = state.findDocument(currentName);
      (doc?.tags || []).forEach((t) => tagRow.appendChild(tags.pill(t, { interactive: true })));
      const add = el("span", { class: "reader-tag-add" }, [
        el("i", { class: "ti ti-plus" }),
        "tag",
      ]);
      add.addEventListener("click", () => tags.openTagEditor(currentName));
      tagRow.appendChild(add);
    }

    async function open(name) {
      currentName = name;
      empty.style.display = "none";
      content.style.display = "flex";
      title.textContent = name;
      body.textContent = "loading…";
      media.innerHTML = "";
      bus.emit("panel:show", "reader");
      renderTagRow();
      try {
        const data = await api.getDocument(name);
        if (currentName !== name) return;
        renderMedia(name, data);
        body.innerHTML = renderMarkdown(data.content || "");
      } catch (e) {
        media.innerHTML = "";
        body.innerHTML = "";
        body.appendChild(el("i", {}, e.status === 404 ? "Document not found." : e.detail || e.message));
      }
    }

    function close() {
      currentName = null;
      content.style.display = "none";
      empty.style.display = "flex";
      state.setCurrentDoc(null);
      bus.emit("panel:show", "search");
    }

    ref("editTags").addEventListener("click", () => currentName && tags.openTagEditor(currentName));
    ref("copy").addEventListener("click", () => {
      navigator.clipboard.writeText(body.innerText).then(
        () => notify.success("Copied"),
        () => notify.error("Copy failed")
      );
    });
    ref("del").addEventListener("click", async () => {
      if (!currentName) return;
      if (!window.confirm("Delete this source? This cannot be undone.")) return;
      const name = currentName;
      try {
        await api.deleteDocument(name);
        notify.success(`Deleted ${name}`);
        bus.emit("documents:changed");
        close();
      } catch (e) {
        notify.error(e.detail || e.message);
      }
    });
    ref("close").addEventListener("click", close);

    bus.on("doc:open", open);
    bus.on("state:documents", () => {
      if (currentName) renderTagRow();
    });
  },
};
