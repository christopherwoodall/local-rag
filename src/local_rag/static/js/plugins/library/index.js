import { el, delegate } from "../../core/dom.js";

function isUrl(name) {
  return name.startsWith("http://") || name.startsWith("https://");
}

export default {
  id: "library",
  label: "Library",
  icon: "ti-database",
  slot: "sidebar",
  templateUrl: "/static/js/plugins/library/template.html",
  styleUrl: "/static/js/plugins/library/style.css",

  async mount({ root, state, bus, tags }) {
    const ref = (name) => root.querySelector(`[data-ref="${name}"]`);
    const docFilter = ref("docFilter");
    const modeToggle = ref("modeToggle");
    const tagChips = ref("tagChips");
    const docsContainer = ref("docsContainer");
    const sectionLabel = ref("sectionLabel");
    const addSource = ref("addSource");

    let filterText = "";

    function renderTagRail() {
      tagChips.innerHTML = "";
      Array.from(state.globalTags).forEach((tag) => {
        const active = state.activeTags.has(tag);
        const chip = tags.pill(tag);
        chip.className = active ? "tag-chip" : "tag-chip inactive";
        if (!active) chip.removeAttribute("style");
        chip.dataset.tag = tag;
        tagChips.appendChild(chip);
      });
    }

    function renderDocs() {
      const visible = state.documents.filter((d) => {
        if (!d.name.toLowerCase().includes(filterText.toLowerCase())) return false;
        if (state.activeTags.size === 0) return true;
        return Array.from(state.activeTags).every((t) => d.tags.includes(t));
      });

      sectionLabel.textContent =
        visible.length === state.documents.length
          ? "all documents"
          : `filtered (${visible.length})`;

      docsContainer.innerHTML = "";
      if (!visible.length) {
        docsContainer.appendChild(el("div", { class: "doc-empty" }, "no matching docs"));
        return;
      }

      visible.forEach((d) => {
        const item = el("div", {
          class: `doc-item ${state.currentDoc === d.name ? "active" : ""}`,
          dataset: { name: d.name },
        }, [
          el("div", { class: "doc-icon" }, [
            el("i", { class: `ti ${isUrl(d.name) ? "ti-link" : "ti-file-text"}` }),
          ]),
          el("div", { class: "doc-meta" }, [
            el("div", { class: "doc-name", title: d.name }, d.name),
            el("div", { class: "doc-date" }, `${d.chunks} chunks`),
            el("div", { class: "doc-tags" }, (d.tags || []).map((t) => tags.pill(t))),
          ]),
          el("button", { class: "doc-tag-btn", dataset: { name: d.name }, title: "edit tags" }, [
            el("i", { class: "ti ti-tag" }),
          ]),
        ]);
        docsContainer.appendChild(item);
      });
    }

    delegate(docsContainer, "click", ".doc-item", (e, item) => {
      const tagBtn = e.target.closest(".doc-tag-btn");
      if (tagBtn) {
        e.stopPropagation();
        tags.openTagEditor(tagBtn.dataset.name);
        return;
      }
      const name = item.dataset.name;
      state.setCurrentDoc(name);
      bus.emit("doc:open", name);
    });

    delegate(tagChips, "click", ".tag-chip", (e, chip) => {
      state.toggleActiveTag(chip.dataset.tag);
    });

    modeToggle.addEventListener("click", (e) => {
      const btn = e.target.closest(".mode-btn");
      if (btn) state.setMode(btn.dataset.mode);
    });

    docFilter.addEventListener("input", (e) => {
      filterText = e.target.value;
      renderDocs();
    });

    addSource.addEventListener("click", () => bus.emit("ingest:open"));

    bus.on("state:documents", () => {
      renderTagRail();
      renderDocs();
    });
    bus.on("state:filters", () => {
      renderTagRail();
      renderDocs();
    });
    bus.on("state:currentDoc", renderDocs);
    bus.on("state:mode", (mode) => {
      modeToggle.querySelectorAll(".mode-btn").forEach((b) =>
        b.classList.toggle("active", b.dataset.mode === mode)
      );
    });

    renderTagRail();
    renderDocs();
  },
};
