// Frontend plugin manifest — the single drop-in point for new UI plugins.
// Add a plugin by creating its folder (index.js + optional template.html/style.css)
// and listing its entry module URL here.
export const PLUGINS = [
  "/static/js/plugins/library/index.js",
  "/static/js/plugins/search/index.js",
  "/static/js/plugins/reader/index.js",
  "/static/js/plugins/ingest-pdf/index.js",
  "/static/js/plugins/ingest-url/index.js",
  "/static/js/plugins/ingest-audio/index.js",
];
