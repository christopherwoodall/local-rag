import { el, delegate, escapeHtml } from "../../core/dom.js";

function highlight(text, query) {
  const safe = escapeHtml(text);
  if (!query) return safe;
  const words = query.split(/\s+/).filter((w) => w.length > 3);
  let out = safe;
  words.forEach((w) => {
    const re = new RegExp(`(${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
    out = out.replace(re, '<span class="highlight">$1</span>');
  });
  return out;
}

export default {
  id: "search",
  label: "search",
  icon: "ti-search",
  slot: "panel",
  templateUrl: "/static/js/plugins/search/template.html",
  styleUrl: "/static/js/plugins/search/style.css",

  async mount({ root, api, state, bus, notify, tags }) {
    const ref = (name) => root.querySelector(`[data-ref="${name}"]`);
    const queryInput = ref("query");
    const searchBtn = ref("searchBtn");
    const limitSel = ref("limit");
    const activeFilters = ref("activeFilters");
    const results = ref("results");

    function renderActiveFilters() {
      const active = Array.from(state.activeTags);
      if (!active.length) {
        activeFilters.classList.add("hidden");
        activeFilters.innerHTML = "";
        return;
      }
      activeFilters.classList.remove("hidden");
      activeFilters.innerHTML = "";
      activeFilters.appendChild(el("span", { class: "filter-label" }, "filtering:"));
      active.forEach((tag) => {
        const chip = tags.pill(tag);
        chip.className = "active-chip";
        chip.appendChild(el("i", { class: "ti ti-x" }));
        chip.dataset.tag = tag;
        activeFilters.appendChild(chip);
      });
      const clear = el("span", { class: "clear-filters" }, "clear filters");
      clear.addEventListener("click", () => state.clearActiveTags());
      activeFilters.appendChild(clear);
    }

    delegate(activeFilters, "click", ".active-chip", (e, chip) => {
      state.toggleActiveTag(chip.dataset.tag);
    });

    function setResults(node) {
      results.innerHTML = "";
      results.appendChild(node);
    }

    function emptyState(icon, title, sub) {
      return el("div", { class: "empty-state" }, [
        el("i", { class: `ti ${icon}` }),
        el("span", { class: "empty-title" }, title),
        sub ? el("span", { class: "empty-sub" }, sub) : null,
      ]);
    }

    async function runSearch() {
      const query = queryInput.value.trim();
      if (!query) return;
      const limit = parseInt(limitSel.value, 10);

      setResults(emptyState("ti-loader", "searching knowledge base...", null));
      results.querySelector(".ti-loader")?.classList.add("spin");

      try {
        const start = performance.now();
        const items = await api.search({
          query,
          limit,
          tags: Array.from(state.activeTags),
          mode: state.mode,
        });
        const ms = Math.round(performance.now() - start);

        if (!items.length) {
          setResults(emptyState("ti-zoom-cancel", "no results found", "try broadening your query"));
          return;
        }

        results.innerHTML = "";
        const meta = el("div", { class: "results-meta" }, [
          el("span", { class: "status-dot" }),
          `${items.length} results `,
          el("span", { class: "badge badge-hybrid" }, state.mode),
          ` · ${ms}ms`,
        ]);
        results.appendChild(meta);

        items.forEach((r, i) => {
          const textNode = el("div", { class: "result-text clamped", dataset: { idx: i } });
          textNode.innerHTML = highlight(r.text, query);
          const card = el("div", { class: "result-card" }, [
            el("div", { class: "result-header" }, [
              el("span", { class: "result-source" }, [
                el("i", { class: "ti ti-file-text" }),
                r.source,
              ]),
              el("span", { class: "result-rank" }, `#${i + 1}`),
            ]),
            el("div", { class: "score-bar" }, [
              el("div", { class: "score-track" }, [
                el("div", {
                  class: "score-fill",
                  style: { width: `${Math.max(0, Math.min(100, Math.round(r.score * 100)))}%` },
                }),
              ]),
              el("span", { class: "score-val" }, r.score.toFixed(3)),
            ]),
            textNode,
            el("div", { class: "result-footer" }, [
              el("div", { class: "result-tags" }, (r.tags || []).map((t) => tags.pill(t))),
              el("span", { class: "chunk-idx" }, `chunk ${r.chunk_index}`),
            ]),
          ]);
          card.addEventListener("click", () => textNode.classList.toggle("clamped"));
          results.appendChild(card);
        });
      } catch (e) {
        notify.error(e.detail || e.message);
        setResults(emptyState("ti-alert-triangle", "search error", e.detail || e.message));
      }
    }

    searchBtn.addEventListener("click", runSearch);
    queryInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") runSearch();
    });

    bus.on("state:filters", renderActiveFilters);
    renderActiveFilters();
  },
};
