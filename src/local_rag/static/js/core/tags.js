import { el } from "./dom.js";

const TAG_COLORS = [
  { bg: "#E6F1FB", border: "#185FA5", text: "#0C447C" },
  { bg: "#E1F5EE", border: "#0F6E56", text: "#085041" },
  { bg: "#FAEEDA", border: "#854F0B", text: "#633806" },
  { bg: "#EEEDFE", border: "#534AB7", text: "#3C3489" },
  { bg: "#FBEAF0", border: "#993556", text: "#72243E" },
];

export function colorFor(tag) {
  let hash = 0;
  for (let i = 0; i < tag.length; i++) hash = tag.charCodeAt(i) + ((hash << 5) - hash);
  return TAG_COLORS[Math.abs(hash) % TAG_COLORS.length];
}

export function pill(tag, { interactive = false } = {}) {
  const c = colorFor(tag);
  const node = el("span", { class: "doc-tag" }, tag);
  node.style.background = c.bg;
  node.style.border = `0.5px solid ${c.border}`;
  node.style.color = c.text;
  if (interactive) {
    node.style.padding = "3px 8px";
    node.style.fontSize = "11px";
  }
  return node;
}

/**
 * Reusable chip-based tag input.
 * Returns { element, getTags, setTags }.
 */
export function tagInput(initial = []) {
  const selected = new Set(initial);
  const chips = el("div", { class: "tag-input-chips" });
  const field = el("input", {
    class: "tag-input-field",
    type: "text",
    placeholder: "add tag + Enter…",
    maxlength: "24",
  });

  function render() {
    chips.innerHTML = "";
    selected.forEach((tag) => {
      const c = colorFor(tag);
      const chip = el("span", { class: "tag-chip-removable" }, [
        el("span", {}, tag),
        el("i", { class: "ti ti-x" }),
      ]);
      chip.style.background = c.bg;
      chip.style.border = `0.5px solid ${c.border}`;
      chip.style.color = c.text;
      chip.addEventListener("click", () => {
        selected.delete(tag);
        render();
      });
      chips.appendChild(chip);
    });
  }

  field.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const val = field.value.trim().toLowerCase();
      if (val) selected.add(val);
      field.value = "";
      render();
    }
  });

  render();
  const element = el("div", { class: "tag-input" }, [chips, field]);
  return {
    element,
    getTags: () => Array.from(selected),
    setTags: (tags) => {
      selected.clear();
      tags.forEach((t) => selected.add(t));
      render();
    },
  };
}

export function createTags({ api, state, bus, notify, modal }) {
  function openTagEditor(filename) {
    const doc = state.findDocument(filename);
    const selected = new Set(doc?.tags || []);

    const grid = el("div", { class: "tag-grid" });
    const renderGrid = () => {
      grid.innerHTML = "";
      const all = new Set([...state.globalTags, ...selected]);
      all.forEach((tag) => {
        const on = selected.has(tag);
        const c = colorFor(tag);
        const toggle = el("span", { class: `tag-toggle ${on ? "on" : "off"}` }, tag);
        if (on) {
          toggle.style.background = c.bg;
          toggle.style.borderColor = c.border;
          toggle.style.color = c.text;
        }
        toggle.addEventListener("click", () => {
          if (selected.has(tag)) selected.delete(tag);
          else selected.add(tag);
          renderGrid();
        });
        grid.appendChild(toggle);
      });
    };
    renderGrid();

    const newInput = el("input", {
      class: "new-tag-field",
      type: "text",
      placeholder: "new tag name…",
      maxlength: "24",
    });
    const addBtn = el("button", { class: "btn-add-tag" }, "+ add");
    const addTag = () => {
      const val = newInput.value.trim().toLowerCase();
      if (!val) return;
      selected.add(val);
      newInput.value = "";
      renderGrid();
    };
    addBtn.addEventListener("click", addTag);
    newInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") addTag();
    });

    const saveBtn = el("button", { class: "btn-done" }, "save");
    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      try {
        await api.updateTags(filename, Array.from(selected));
        notify.success("Tags updated");
        bus.emit("documents:changed");
        modal.close();
      } catch (e) {
        notify.error(e.detail || e.message);
        saveBtn.disabled = false;
      }
    });
    const cancelBtn = el("button", { class: "btn-cancel" }, "cancel");
    cancelBtn.addEventListener("click", () => modal.close());

    const body = el("div", {}, [
      el("div", { class: "modal-doc-name" }, filename),
      grid,
      el("div", { class: "new-tag-row" }, [newInput, addBtn]),
      el("div", { class: "modal-actions" }, [cancelBtn, saveBtn]),
    ]);

    modal.open({ title: "edit tags", body, width: 320 });
  }

  return { openTagEditor, pill, tagInput, colorFor };
}
