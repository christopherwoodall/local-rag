import { el } from "./dom.js";

const ICONS = {
  success: "ti-circle-check",
  error: "ti-alert-triangle",
  info: "ti-info-circle",
};

export function createNotify(root) {
  function toast(message, type = "info", timeout = 3500) {
    const node = el("div", { class: `toast toast-${type}` }, [
      el("i", { class: `ti ${ICONS[type] || ICONS.info}` }),
      el("span", { class: "toast-msg" }, message),
    ]);
    root.appendChild(node);
    requestAnimationFrame(() => node.classList.add("show"));
    const remove = () => {
      node.classList.remove("show");
      setTimeout(() => node.remove(), 200);
    };
    if (timeout) setTimeout(remove, timeout);
    node.addEventListener("click", remove);
    return remove;
  }

  return {
    toast,
    success: (m, t) => toast(m, "success", t),
    error: (m, t) => toast(m, "error", t),
    info: (m, t) => toast(m, "info", t),
  };
}
