/* notion-budget-sync frontend */

const $ = (id) => document.getElementById(id);

// State
let selectedFile = null;
let lastMapping = null;
let lastHeaders = [];
let savedDbUrls = [];
let pendingRunToken = null;      // set after dry run, cleared when inputs change
let excluded = new Set();        // txn IDs deselected in dry-run preview
let categoryOverrides = {};      // {txn_id: new_category_name}
let availableCategories = [];    // Notion category names from last run
let previewData = [];            // full preview rows from last dry run

// ── Elements ──────────────────────────────────────────────────────────────────

const dropZone    = $("drop-zone");
const fileInput   = $("file-input");
const fileSelected = $("file-selected");
const fileName    = $("file-name");
const clearFile   = $("clear-file");
const txnFolderLink = $("txn-folder-link");
const txnPicker   = $("txn-picker");
const notionUrl   = $("notion-url");
const dbSelect    = $("db-select");
const saveDbBtn   = $("save-db-btn");
const dbSaveRow   = $("db-save-row");
const dbSaveName  = $("db-save-name");
const dbSaveConfirm = $("db-save-confirm");
const dbSaveCancel  = $("db-save-cancel");
const manageDbBtn = $("manage-db-btn");
const dbModalOverlay = $("db-modal-overlay");
const dbModalBody = $("db-modal-body");
const dbModalClose = $("db-modal-close");
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
const syncLabel     = $("sync-label");
const previewHeader = $("preview-header");
const monthFilter   = $("month-filter");
const monthSelect   = $("month-select");
const settingsBtn   = $("settings-btn");
const settingsModalOverlay = $("settings-modal-overlay");
const settingsModalClose   = $("settings-modal-close");
const settingsSaveBtn      = $("settings-save-btn");
const settingsRestart      = $("settings-restart");

// ── Boot ──────────────────────────────────────────────────────────────────────

loadProfiles();
loadDbUrls();

// ── File handling ─────────────────────────────────────────────────────────────

dropZone.addEventListener("click", () => fileInput.click());
dropZone.querySelector(".browse-link:not(#txn-folder-link)").addEventListener("click", (e) => {
  e.stopPropagation();
  fileInput.click();
});

txnFolderLink.addEventListener("click", async (e) => {
  e.stopPropagation();
  if (!txnPicker.hidden) { txnPicker.hidden = true; return; }
  txnPicker.innerHTML = '<div class="txn-picker-empty">Loading…</div>';
  txnPicker.hidden = false;
  try {
    const res = await fetch("/api/transaction-files");
    const files = await res.json();
    if (!files.length) {
      txnPicker.innerHTML = '<div class="txn-picker-empty">No files in transactions/</div>';
      return;
    }
    txnPicker.innerHTML = files.map((f) =>
      `<div class="txn-picker-file" data-name="${esc(f.name)}">${esc(f.name)}</div>`
    ).join("");
    txnPicker.querySelectorAll(".txn-picker-file").forEach((el) => {
      el.addEventListener("click", async () => {
        const name = el.dataset.name;
        txnPicker.hidden = true;
        const fileRes = await fetch(`/api/transaction-files/${encodeURIComponent(name)}`);
        const blob = await fileRes.blob();
        const file = new File([blob], name, { type: blob.type });
        clearPendingRun();
        selectFile(file);
      });
    });
  } catch (err) {
    txnPicker.innerHTML = `<div class="txn-picker-empty">Error: ${esc(String(err))}</div>`;
  }
});

document.addEventListener("click", (e) => {
  if (!txnPicker.hidden && !txnPicker.contains(e.target) && e.target !== txnFolderLink) {
    txnPicker.hidden = true;
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) { clearPendingRun(); selectFile(fileInput.files[0]); }
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
  txnPicker.hidden = true;
  clearPendingRun();
  updateButtons();
  hide(results);
  hide(errorBox);
});

function selectFile(file) {
  selectedFile = file;
  fileName.textContent = file.name;
  fileSelected.hidden = false;
  dropZone.hidden = true;
  txnPicker.hidden = true;
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
  formatSelect.innerHTML = '<option value="">Auto-detect</option>';
  profiles.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.name;
    opt.textContent = p.name;
    formatSelect.appendChild(opt);
  });
  const last = localStorage.getItem("lastFormatName");
  if (last && profiles.find((p) => p.name === last)) formatSelect.value = last;
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

// ── DB URL management ─────────────────────────────────────────────────────────

async function loadDbUrls() {
  try {
    const res = await fetch("/api/db-urls");
    savedDbUrls = await res.json();
    populateDbSelect(savedDbUrls);
    populateDbModal(savedDbUrls);
  } catch (_) {}
}

function populateDbSelect(dbs) {
  dbSelect.innerHTML = '<option value="">Select saved database...</option>';
  dbs.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = d.url;
    opt.textContent = d.name;
    dbSelect.appendChild(opt);
  });
  // Restore last used URL (from localStorage or current input)
  const lastUrl = localStorage.getItem("lastDbUrl") || notionUrl.value;
  const match = dbs.find((d) => d.url === lastUrl);
  if (match) {
    dbSelect.value = lastUrl;
    notionUrl.value = lastUrl;
  } else if (lastUrl && !notionUrl.value) {
    notionUrl.value = lastUrl;
  }
}

function populateDbModal(dbs) {
  if (!dbs.length) {
    dbModalBody.innerHTML = '<p class="empty-state">No databases saved yet.</p>';
    return;
  }
  dbModalBody.innerHTML = "";
  dbs.forEach((d) => {
    const card = document.createElement("div");
    card.className = "profile-card";
    card.innerHTML = `
      <div class="profile-card-header">
        <span class="profile-name">${esc(d.name)}</span>
        <div class="profile-actions">
          <button class="delete-btn" data-name="${esc(d.name)}">Delete</button>
        </div>
      </div>
      <div class="profile-meta"><a class="db-url-link" href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.url)}</a></div>
    `;
    card.querySelector(".delete-btn").addEventListener("click", async (e) => {
      const name = e.target.dataset.name;
      if (!confirm(`Delete "${name}"?`)) return;
      await fetch(`/api/db-urls/${encodeURIComponent(name)}`, { method: "DELETE" });
      await loadDbUrls();
    });
    dbModalBody.appendChild(card);
  });
}

dbSelect.addEventListener("change", () => {
  if (dbSelect.value) {
    notionUrl.value = dbSelect.value;
    hide(dbSaveRow);
  }
  clearPendingRun();
});

notionUrl.addEventListener("input", () => {
  const match = savedDbUrls.find((d) => d.url === notionUrl.value);
  dbSelect.value = match ? match.url : "";
  clearPendingRun();
});

saveDbBtn.addEventListener("click", () => {
  if (!notionUrl.value.trim()) return;
  dbSaveRow.hidden = !dbSaveRow.hidden;
  if (!dbSaveRow.hidden) dbSaveName.focus();
});

dbSaveConfirm.addEventListener("click", async () => {
  const name = dbSaveName.value.trim();
  const url = notionUrl.value.trim();
  if (!name || !url) { dbSaveName.focus(); return; }
  const res = await fetch("/api/db-urls", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, url }),
  });
  const data = await res.json();
  if (data.ok) {
    dbSaveName.value = "";
    hide(dbSaveRow);
    await loadDbUrls();
    dbSelect.value = url;
  }
});

dbSaveCancel.addEventListener("click", () => { hide(dbSaveRow); dbSaveName.value = ""; });

manageDbBtn.addEventListener("click", () => {
  loadDbUrls();
  dbModalOverlay.hidden = false;
});

dbModalClose.addEventListener("click", () => { dbModalOverlay.hidden = true; });
dbModalOverlay.addEventListener("click", (e) => {
  if (e.target === dbModalOverlay) dbModalOverlay.hidden = true;
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

formatSelect.addEventListener("change", clearPendingRun);

// ── Pending run helpers ───────────────────────────────────────────────────────

function clearPendingRun() {
  pendingRunToken = null;
  excluded.clear();
  categoryOverrides = {};
  previewData = [];
  syncLabel.textContent = "Sync";
  hide(monthFilter);
  monthSelect.innerHTML = '<option value="all">All months</option>';
  updateButtons();
}

// ── Sync / Dry-run ────────────────────────────────────────────────────────────

dryRunBtn.addEventListener("click", () => runSync(true));
syncBtn.addEventListener("click", () => {
  if (pendingRunToken) runSyncConfirmed();
  else runSync(false);
});

async function runSync(dryRun) {
  hide(results);
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
      errorBox.classList.remove("warn");
      show(errorBox, data.error || "An error occurred.");
      return;
    }

    lastMapping = data.mapping;
    lastHeaders = data.headers || [];

    if (dryRun && data.run_token) {
      pendingRunToken = data.run_token;
      excluded.clear();
      categoryOverrides = {};
      syncLabel.textContent = "Confirm Sync";
      updateButtons();
    } else {
      clearPendingRun();
    }

    saveLastUsed();
    renderResults(data, dryRun);

    if (data.capped) {
      errorBox.classList.add("warn");
      show(errorBox, `Run capped at ${data.new} transactions. Increase MAX_TRANSACTIONS_PER_RUN in src/config.py to process more.`);
    } else {
      errorBox.classList.remove("warn");
    }
  } catch (err) {
    show(errorBox, String(err));
  } finally {
    setLoading(false);
  }
}

async function runSyncConfirmed() {
  hide(results);
  hide(errorBox);
  setLoading(true, "Syncing...");

  try {
    const res = await fetch("/api/sync-confirmed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_token: pendingRunToken,
        excluded_ids: [...excluded],
        category_overrides: categoryOverrides,
      }),
    });
    const data = await res.json();

    if (!data.ok) {
      errorBox.classList.remove("warn");
      show(errorBox, data.error || "An error occurred.");
      return;
    }

    clearPendingRun();
    renderResults(data, false);
  } catch (err) {
    show(errorBox, String(err));
  } finally {
    setLoading(false);
  }
}

function renderResults(data, dryRun) {
  const filtered = data.read - data.normalized;
  statsEl.innerHTML = `
    <div class="stat"><span class="stat-value">${data.read}</span><span class="stat-label">Read</span></div>
    ${filtered > 0 ? `<div class="stat"><span class="stat-value warn">${filtered}</span><span class="stat-label">Filtered</span></div>` : ""}
    <div class="stat"><span class="stat-value muted">${data.skipped}</span><span class="stat-label">In Notion</span></div>
    <div class="stat"><span class="stat-value green">${data.new}</span><span class="stat-label">${dryRun ? "Would add" : "Added"}</span></div>
  `;

  if (data.is_new_format) show(savePrompt);
  else hide(savePrompt);

  if (data.preview && data.preview.length) {
    if (dryRun) {
      availableCategories = data.categories || [];
      previewData = data.preview;
      populateMonthFilter(data.preview);
    }

    previewHeader.innerHTML = (dryRun ? "<th class='check-th'></th>" : "") +
      "<th>Date</th><th>Merchant</th><th>Amount</th><th>Category</th>";

    previewBody.innerHTML = data.preview.map((row) => {
      const isExcluded = excluded.has(row.id);
      const currentCat = categoryOverrides[row.id] || row.category;
      const catCell = dryRun && availableCategories.length
        ? `<td><select class="cat-select" data-id="${esc(row.id)}">${
            availableCategories.map((c) =>
              `<option value="${esc(c)}"${c === currentCat ? " selected" : ""}>${esc(c)}</option>`
            ).join("")
          }</select></td>`
        : `<td><span class="cat-pill">${esc(row.category)}</span></td>`;

      return `<tr class="${isExcluded ? "row-excluded" : ""}" data-id="${esc(row.id || "")}">
        ${dryRun ? `<td class="check-td"><input type="checkbox" class="row-check" ${isExcluded ? "" : "checked"}></td>` : ""}
        <td>${esc(row.date)}</td>
        <td>${esc(row.merchant)}</td>
        <td class="amount-cell">$${Number(row.amount).toFixed(2)}</td>
        ${catCell}
      </tr>`;
    }).join("");

    if (dryRun) {
      previewBody.querySelectorAll(".row-check").forEach((cb) => {
        cb.addEventListener("change", (e) => {
          const tr = e.target.closest("tr");
          const id = tr.dataset.id;
          if (e.target.checked) { excluded.delete(id); tr.classList.remove("row-excluded"); }
          else { excluded.add(id); tr.classList.add("row-excluded"); }
        });
      });
      previewBody.querySelectorAll(".cat-select").forEach((sel) => {
        sel.addEventListener("change", (e) => {
          const id = e.target.dataset.id;
          const orig = data.preview.find((r) => r.id === id)?.category;
          if (e.target.value !== orig) categoryOverrides[id] = e.target.value;
          else delete categoryOverrides[id];
        });
      });
    }

    show(previewWrap);
  } else {
    hide(previewWrap);
  }

  show(results);
}

// ── Month filter ──────────────────────────────────────────────────────────────

function populateMonthFilter(preview) {
  // Extract unique months sorted chronologically
  const seen = new Map(); // "YYYY-MM" -> label
  preview.forEach((row) => {
    const [y, m] = row.date.split("-");
    const key = `${y}-${m}`;
    if (!seen.has(key)) {
      const label = new Date(y, m - 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
      seen.set(key, label);
    }
  });

  if (seen.size <= 1) return; // only one month — no need to show the filter

  monthSelect.innerHTML = '<option value="all">All months</option>';
  [...seen.entries()].sort().forEach(([key, label]) => {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = label;
    monthSelect.appendChild(opt);
  });
  show(monthFilter);
}

function applyMonthFilter(selectedKey) {
  // Reset excluded to only month-based exclusions, preserving nothing else
  excluded.clear();
  if (selectedKey !== "all") {
    previewData.forEach((row) => {
      const [y, m] = row.date.split("-");
      if (`${y}-${m}` !== selectedKey) excluded.add(row.id);
    });
  }

  // Sync checkboxes and row styles to match
  previewBody.querySelectorAll("tr[data-id]").forEach((tr) => {
    const isExcluded = excluded.has(tr.dataset.id);
    tr.classList.toggle("row-excluded", isExcluded);
    const cb = tr.querySelector(".row-check");
    if (cb) cb.checked = !isExcluded;
  });
}

monthSelect.addEventListener("change", () => applyMonthFilter(monthSelect.value));

// ── Settings ──────────────────────────────────────────────────────────────────

settingsBtn.addEventListener("click", openSettings);
settingsModalClose.addEventListener("click", () => { settingsModalOverlay.hidden = true; });
settingsModalOverlay.addEventListener("click", (e) => {
  if (e.target === settingsModalOverlay) settingsModalOverlay.hidden = true;
});

async function openSettings() {
  hide(settingsRestart);
  $("settings-anthropic").value = "";
  $("settings-openai").value = "";
  $("settings-notion").value = "";
  settingsModalOverlay.hidden = false;

  try {
    const res = await fetch("/api/settings");
    const s = await res.json();

    const fields = [
      ["anthropic", "ANTHROPIC_API_KEY"],
      ["openai",    "OPENAI_API_KEY"],
      ["notion",    "NOTION_TOKEN"],
    ];
    fields.forEach(([id, key]) => {
      const hint = $(`hint-${id}`);
      const info = s[key] || {};
      if (info.set && info.hint) {
        hint.textContent = `Currently set: ${info.hint}  — leave blank to keep`;
      } else if (info.set) {
        hint.textContent = "Currently set — leave blank to keep";
      } else {
        hint.textContent = "Not set";
      }
    });

    $("settings-llm").checked = !!s["LLM_CATEGORIZATION"];
  } catch (_) {}
}

settingsSaveBtn.addEventListener("click", async () => {
  const payload = {
    ANTHROPIC_API_KEY: $("settings-anthropic").value,
    OPENAI_API_KEY:    $("settings-openai").value,
    NOTION_TOKEN:      $("settings-notion").value,
    LLM_CATEGORIZATION: $("settings-llm").checked,
  };

  settingsSaveBtn.disabled = true;
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.ok) {
      if (data.restart_required) show(settingsRestart);
      // Refresh hints
      openSettings();
    }
  } finally {
    settingsSaveBtn.disabled = false;
  }
});

function saveLastUsed() {
  if (notionUrl.value) localStorage.setItem("lastDbUrl", notionUrl.value);
  if (formatSelect.value) localStorage.setItem("lastFormatName", formatSelect.value);
  else localStorage.removeItem("lastFormatName");
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function updateButtons() {
  dryRunBtn.disabled = !selectedFile;
  syncBtn.disabled = !pendingRunToken;
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
