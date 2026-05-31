import { el } from "./dom.js";

export function createModal(root) {
  let active = null;

  function close() {
    if (!active) return;
    active.remove();
    active = null;
  }

  /**
   * open({ title, body, tabs, width })
   * - body: a DOM node, OR
   * - tabs: [{ id, label, icon, render() -> node }] rendered as a tabbed modal.
   */
  function open({ title = "", body = null, tabs = null, width = 420 } = {}) {
    close();

    const content = el("div", { class: "modal-body" });
    const modal = el("div", { class: "modal", style: { width: `${width}px` } }, [
      el("div", { class: "modal-head" }, [
        el("div", { class: "modal-title" }, title),
        el("button", {
          class: "btn-icon modal-close",
          title: "close",
          onClick: close,
          innerHTML: '<i class="ti ti-x"></i>',
        }),
      ]),
      content,
    ]);
    const backdrop = el("div", { class: "modal-backdrop" }, [modal]);
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) close();
    });

    if (tabs && tabs.length) {
      const tabBar = el("div", { class: "modal-tabs" });
      const panes = el("div", { class: "modal-panes" });
      const rendered = new Map();

      const activate = (tab) => {
        tabBar.querySelectorAll(".modal-tab").forEach((b) =>
          b.classList.toggle("active", b.dataset.id === tab.id)
        );
        panes.innerHTML = "";
        if (!rendered.has(tab.id)) rendered.set(tab.id, tab.render());
        panes.appendChild(rendered.get(tab.id));
      };

      tabs.forEach((tab) => {
        const btn = el("button", { class: "modal-tab", dataset: { id: tab.id } }, [
          tab.icon ? el("i", { class: `ti ${tab.icon}` }) : null,
          el("span", {}, tab.label),
        ]);
        btn.addEventListener("click", () => activate(tab));
        tabBar.appendChild(btn);
      });

      content.appendChild(tabBar);
      content.appendChild(panes);
      activate(tabs[0]);
    } else if (body) {
      content.appendChild(body);
    }

    root.appendChild(backdrop);
    active = backdrop;
    return { close };
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });

  return { open, close };
}
