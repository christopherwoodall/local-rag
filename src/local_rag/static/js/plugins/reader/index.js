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
    let currentName = null;

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
      bus.emit("panel:show", "reader");
      renderTagRow();
      try {
        const data = await api.getDocument(name);
        body.innerHTML = renderMarkdown(data.content || "");
      } catch (e) {
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
    ref("close").addEventListener("click", close);

    bus.on("doc:open", open);
    bus.on("state:documents", () => {
      if (currentName) renderTagRow();
    });
  },
};
