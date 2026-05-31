export default {
  id: "ingest-pdf",
  label: "PDF",
  icon: "ti-file-type-pdf",
  slot: "ingest",
  templateUrl: "/static/js/plugins/ingest-pdf/template.html",
  styleUrl: "/static/js/plugins/ingest-pdf/style.css",

  async mount({ root, api, bus, notify, modal, tags }) {
    const ref = (name) => root.querySelector(`[data-ref="${name}"]`);
    const dropzone = ref("dropzone");
    const dropLabel = ref("dropLabel");
    const fileInput = ref("file");
    const submit = ref("submit");
    const tagsField = tags.tagInput([]);
    ref("tagsMount").appendChild(tagsField.element);

    let selected = null;

    function setFile(file) {
      selected = file;
      dropLabel.textContent = file ? file.name : "drop PDF or click to choose";
    }

    dropzone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => setFile(e.target.files[0] || null));
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      setFile(e.dataTransfer.files[0] || null);
    });

    submit.addEventListener("click", async () => {
      if (!selected) {
        notify.error("Choose a PDF first");
        return;
      }
      submit.disabled = true;
      submit.textContent = "ingesting…";
      try {
        const res = await api.ingestPdf(selected, tagsField.getTags());
        if (res.chunks) {
          notify.success(`Ingested ${res.chunks} chunks from ${selected.name}`);
          bus.emit("documents:changed");
          modal.close();
        } else {
          notify.info(res.message || "No text extracted.");
        }
      } catch (e) {
        notify.error(e.detail || e.message);
      } finally {
        submit.disabled = false;
        submit.textContent = "ingest pdf";
      }
    });
  },
};
