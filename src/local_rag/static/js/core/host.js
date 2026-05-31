import { el } from "./dom.js";

export function createHost(services) {
  const slots = {
    sidebar: document.getElementById("slot-sidebar"),
    panel: document.getElementById("slot-panel"),
    panelTabs: document.getElementById("panel-tabs"),
  };
  const loadedStyles = new Set();
  const ingestPlugins = [];

  async function loadStyle(url) {
    if (!url || loadedStyles.has(url)) return;
    loadedStyles.add(url);
    await new Promise((resolve) => {
      const link = el("link", { rel: "stylesheet", href: url });
      link.addEventListener("load", resolve);
      link.addEventListener("error", resolve);
      document.head.appendChild(link);
    });
  }

  async function loadTemplate(url) {
    if (!url) return "";
    try {
      const res = await fetch(url);
      return res.ok ? await res.text() : "";
    } catch {
      return "";
    }
  }

  function panelShow(id) {
    slots.panel.querySelectorAll(".panel-view").forEach((view) => {
      view.style.display = view.dataset.pluginId === id ? "flex" : "none";
    });
    slots.panelTabs.querySelectorAll(".panel-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.panel === id);
    });
  }

  async function register(plugin) {
    await loadStyle(plugin.styleUrl);
    const template = await loadTemplate(plugin.templateUrl);

    if (plugin.slot === "ingest") {
      ingestPlugins.push({
        id: plugin.id,
        label: plugin.label,
        icon: plugin.icon,
        render() {
          const root = el("div", { class: `plugin plugin-${plugin.id}` });
          root.innerHTML = template;
          Promise.resolve(plugin.mount({ root, ...services })).catch((e) =>
            console.error(`mount ${plugin.id} failed`, e)
          );
          return root;
        },
      });
      return;
    }

    const root = el("div", {
      class: `plugin plugin-${plugin.id}`,
      dataset: { pluginId: plugin.id },
    });
    root.innerHTML = template;

    if (plugin.slot === "sidebar") {
      slots.sidebar.appendChild(root);
    } else if (plugin.slot === "panel") {
      root.classList.add("panel-view");
      root.style.display = "none";
      slots.panel.appendChild(root);
      const tab = el("button", { class: "panel-tab", dataset: { panel: plugin.id } }, plugin.label);
      tab.addEventListener("click", () => panelShow(plugin.id));
      slots.panelTabs.appendChild(tab);
    }

    await plugin.mount({ root, ...services });
  }

  async function loadAll(urls) {
    for (const url of urls) {
      try {
        const mod = await import(url);
        const plugin = mod.default;
        if (!plugin || !plugin.id) {
          console.error("Invalid plugin module", url);
          continue;
        }
        await register(plugin);
      } catch (e) {
        console.error("Failed to load plugin", url, e);
      }
    }
    const firstTab = slots.panelTabs.querySelector(".panel-tab");
    if (firstTab) panelShow(firstTab.dataset.panel);
  }

  services.bus.on("panel:show", panelShow);

  return { loadAll, getIngestPlugins: () => ingestPlugins };
}
