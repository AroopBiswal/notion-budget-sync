/* notion-budget-sync frontend */

const $ = (id) => document.getElementById(id);

// State
let selectedFile = null;
let lastMapping = null;
let lastHeaders = [];

// ── Elements ──────────────────────────────────────────────────────────────────

const dropZone    = $("drop-zone");
const fileInput   = $("file-input");
const fileSelected = $("file-selected");
const fileName    = $("file-name");
const clearFile   = $("clear-file");
const notionUrl   = $("notion-url");
const formatSelect = $("format-select");
const manageBtn   = $("manage-btn");
const dryRunBtn   = $("dry-run-btn");
const syncBtn     = $("sync-btn");
const loading     = $("loading");
const loadingText = $("loading-text");
const results     = $("results");
const statsEl     = $("stats");
const previewWrap = $("preview-wrap");
const previewBody = $("preview-body");
const savePrompt  = $("save-prompt");
const saveName    = $("save-name");
const saveBtn     = $("save-btn");
const saveHint    = $("save-hint");
const errorBox    = $("error-box");
const modalOverlay = $("modal-overlay");
const modalBody   = $("modal-body");
const modalClose  = $("modal-close");

// ── Boot ──────────────────────────────────────────────────────────────────────

loadProfiles();

// ── File handling ─────────────────────────────────────────────────────────────

dropZone.addEventListener("click", () => fileInput.click());
dropZone.querySelector(".browse-link").addEventListener("click", (e) => {
  e.stopPropagation();
  fileInput.click();
});

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) selectFile(fileInput.files[0]);
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  if (e.dataTransfer.files[0]) selectFile(e.dataTransfer.files[0]);
});

clearFile.addEventListener("click", () => {
  selectedFile = null;
  fileInput.value = "";
  fileSelected.hidden = true;
  dropZone.hidden = false;
  updateButtons();
  hide(results);
  hide(savePrompt);
  hide(errorBox);
});

function selectFile(file) {
  selectedFile = file;
  fileName.textContent = file.name;
  fileSelected.hidden = false;
  dropZone.hidden = true;
  updateButtons();
}

// ── Profiles ──────────────────────────────────────────────────────────────────

async function loadProfiles() {
  try {
    const res = await fetch("/api/profiles");
    const profiles = await res.json();
    populateSelect(profiles);
    populateModal(profiles);
  } catch (_) {}
}

function populateSelect(profiles) {
  // Keep the Auto-detect option, rebuild the rest
  formatSelect.innerHTML = '<option value="">Auto-detect</option>';
  profiles.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.name;
    opt.textContent = p.name;
    formatSelect.appendChild(opt);
  });
}

function populateModal(profiles) {
  if (!profiles.length) {
    modalBody.innerHTML = '<p class="empty-state">No profiles saved yet.</p>';
    return;
  }
  modalBody.innerHTML = "";
  profiles.forEach((p) => {
    const card = document.createElement("div");
    card.className = "profile-card";
    const preview = (p.headers_preview || []).slice(0, 4).join(", ");
    card.innerHTML = `
      <div class="profile-card-header">
        <span class="profile-name">${esc(p.name)}</span>
        <div class="profile-actions">
          <button class="delete-btn" data-name="${esc(p.name)}">Delete</button>
        </div>
      </div>
      <div class="profile-meta">
        Date: ${esc(p.date_col || "?")} &nbsp; Merchant: ${esc(p.merchant_col || "?")} &nbsp; Amount: ${esc(p.amount_col || "?")}
        <br>Headers: ${esc(preview)}${p.headers_preview && p.headers_preview.length > 4 ? " ..." : ""}
      </div>
    `;
    card.querySelector(".delete-btn").addEventListener("click", async (e) => {
      const name = e.target.dataset.name;
      if (!confirm(`Delete profile "${name}"?`)) return;
      await fetch(`/api/profiles/${encodeURIComponent(name)}`, { method: "DELETE" });
      await loadProfiles();
    });
    modalBody.appendChild(card);
  });
}

manageBtn.addEventListener("click", () => {
  loadProfiles();
  modalOverlay.hidden = false;
});

modalClose.addEventListener("click", () => { modalOverlay.hidden = true; });
modalOverlay.addEventListener("click", (e) => {
  if (e.target === modalOverlay) modalOverlay.hidden = true;
});

// ── Save prompt ───────────────────────────────────────────────────────────────

saveBtn.addEventListener("click", async () => {
  const name = saveName.value.trim();
  if (!name) { saveName.focus(); return; }

  const res = await fetch("/api/profiles/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, mapping: lastMapping, headers: lastHeaders }),
  });
  const data = await res.json();
  if (data.ok) {
    saveHint.textContent = `Saved as "${data.saved_as}"`;
    saveName.value = "";
    await loadProfiles();
    formatSelect.value = data.saved_as;
    setTimeout(() => { hide(savePrompt); saveHint.textContent = ""; }, 2500);
  }
});

// ── Sync / Dry-run ────────────────────────────────────────────────────────────

dryRunBtn.addEventListener("click", () => runSync(true));
syncBtn.addEventListener("click", () => runSync(false));

async function runSync(dryRun) {
  hide(results);
  hide(savePrompt);
  hide(errorBox);

  const url = notionUrl.value.trim();
  if (!url) { show(errorBox, "Enter a Notion database URL."); notionUrl.focus(); return; }
  if (!selectedFile) return;

  const form = new FormData();
  form.append("file", selectedFile);
  form.append("notion_url", url);
  form.append("dry_run", dryRun ? "true" : "false");
  if (formatSelect.value) form.append("format_name", formatSelect.value);

  setLoading(true, dryRun ? "Previewing..." : "Syncing...");

  try {
    const res = await fetch("/api/sync", { method: "POST", body: form });
    const data = await res.json();

    if (!data.ok) {
      show(errorBox, data.error || "An error occurred.");
      return;
    }

    lastMapping = data.mapping;
    lastHeaders = [];
    renderResults(data, dryRun);

    if (data.is_new_format) {
      show(savePrompt);
    }
  } catch (err) {
    show(errorBox, String(err));
  } finally {
    setLoading(false);
  }
}

function renderResults(data, dryRun) {
  statsEl.innerHTML = `
    <div class="stat"><span class="stat-value">${data.read}</span><span class="stat-label">Read</span></div>
    <div class="stat"><span class="stat-value green">${data.new}</span><span class="stat-label">${dryRun ? "Would add" : "Added"}</span></div>
    <div class="stat"><span class="stat-value muted">${data.skipped}</span><span class="stat-label">Skipped</span></div>
  `;

  if (data.preview && data.preview.length) {
    previewBody.innerHTML = data.preview.map((row) => `
      <tr>
        <td>${esc(row.date)}</td>
        <td>${esc(row.merchant)}</td>
        <td class="amount-cell">$${Number(row.amount).toFixed(2)}</td>
        <td><span class="cat-pill">${esc(row.category)}</span></td>
      </tr>
    `).join("");
    show(previewWrap);
  } else {
    hide(previewWrap);
  }

  show(results);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function updateButtons() {
  const ready = !!selectedFile;
  dryRunBtn.disabled = !ready;
  syncBtn.disabled = !ready;
}

function setLoading(on, msg = "") {
  loading.hidden = !on;
  loadingText.textContent = msg;
  dryRunBtn.disabled = on;
  syncBtn.disabled = on;
  if (!on) updateButtons();
}

function show(el, text) {
  el.hidden = false;
  if (text !== undefined) el.textContent = text;
}

function hide(el) { el.hidden = true; }

function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
