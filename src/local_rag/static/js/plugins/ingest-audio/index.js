export default {
  id: "ingest-audio",
  label: "Audio",
  icon: "ti-microphone",
  slot: "ingest",
  templateUrl: "/static/js/plugins/ingest-audio/template.html",
  styleUrl: "/static/js/plugins/ingest-audio/style.css",

  async mount({ root, api, bus, notify, modal, tags }) {
    const ref = (name) => root.querySelector(`[data-ref="${name}"]`);
    const dropzone = ref("dropzone");
    const dropLabel = ref("dropLabel");
    const fileInput = ref("file");
    const submit = ref("submit");
    const overlay = ref("overlay");
    const tagsField = tags.tagInput([]);
    ref("tagsMount").appendChild(tagsField.element);

    let selected = null;

    function setFile(file) {
      selected = file;
      dropLabel.textContent = file ? file.name : "drop audio or click to choose";
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
        notify.error("Choose an audio file first");
        return;
      }
      submit.disabled = true;
      overlay.hidden = false;
      try {
        const res = await api.ingestAudio(selected, tagsField.getTags());
        if (res.empty) {
          notify.info("No speech detected in the audio.");
        } else if (res.chunks) {
          notify.success(`Ingested ${res.chunks} chunks from ${selected.name}`);
          bus.emit("documents:changed");
          modal.close();
        } else {
          notify.info("Nothing was ingested.");
        }
      } catch (e) {
        notify.error(e.detail || e.message);
      } finally {
        overlay.hidden = true;
        submit.disabled = false;
      }
    });
  },
};
