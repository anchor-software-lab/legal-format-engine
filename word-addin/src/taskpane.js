/* global Office, Word */

const API_BASE = "https://localhost:8443/api";
const PROFILE_KEY = "lfe_attorney_profile";

// ── Office.js Initialization ─────────────────────────────────────────

Office.onReady((info) => {
  if (info.host === Office.HostType.Word) {
    initCollapsibles();
    initPartyList();
    initProfileButtons();
    initActionButtons();
    loadSavedProfile();
    setStatus("Ready");
  }
});

// ── Collapsible Sections ─────────────────────────────────────────────

function initCollapsibles() {
  document.querySelectorAll(".collapsible-header").forEach((header) => {
    header.addEventListener("click", () => {
      const section = header.closest(".collapsible");
      const bodyId = header.getAttribute("data-target");
      const body = document.getElementById(bodyId);
      section.classList.toggle("open");
      body.classList.toggle("collapsed");
    });
  });
}

// ── Dynamic Party List ───────────────────────────────────────────────

function initPartyList() {
  document.getElementById("btn-add-party").addEventListener("click", addParty);
  // Wire up existing remove buttons
  document.querySelectorAll(".btn-remove-party").forEach((btn) => {
    btn.addEventListener("click", onRemoveParty);
  });
}

function addParty() {
  const list = document.getElementById("party-list");
  const index = list.children.length;
  const row = document.createElement("div");
  row.className = "party-row";
  row.setAttribute("data-index", index);
  row.innerHTML = `
    <div class="party-row-header">
      <button class="btn-icon btn-remove-party" title="Remove party">&times;</button>
    </div>
    <div class="form-group">
      <label>Name <span class="required">*</span></label>
      <input type="text" class="party-name" placeholder="Party name"/>
      <span class="field-error party-name-error"></span>
    </div>
    <div class="form-group">
      <label>Role</label>
      <select class="party-role">
        <option value="plaintiff-respondent">Plaintiff-Respondent</option>
        <option value="defendant-appellant">Defendant-Appellant</option>
        <option value="state-respondent">State-Respondent</option>
        <option value="state-plaintiff">State-Plaintiff</option>
        <option value="petitioner">Petitioner</option>
        <option value="respondent">Respondent</option>
        <option value="appellant">Appellant</option>
      </select>
    </div>
  `;
  list.appendChild(row);
  row.querySelector(".btn-remove-party").addEventListener("click", onRemoveParty);
}

function onRemoveParty(e) {
  const row = e.target.closest(".party-row");
  const list = document.getElementById("party-list");
  // Must keep at least 2 parties
  if (list.children.length <= 2) {
    return;
  }
  row.remove();
}

function getParties() {
  const parties = [];
  document.querySelectorAll(".party-row").forEach((row) => {
    const name = row.querySelector(".party-name").value.trim();
    const role = row.querySelector(".party-role").value;
    if (name) {
      parties.push({ name, role });
    }
  });
  return parties;
}

// ── Attorney Profile Persistence ─────────────────────────────────────

function initProfileButtons() {
  document.getElementById("btn-save-profile").addEventListener("click", saveProfile);
  document.getElementById("btn-load-profile").addEventListener("click", loadSavedProfile);
  document.getElementById("btn-clear-profile").addEventListener("click", clearProfile);
}

function getProfileData() {
  return {
    attorney_name: val("attorney-name"),
    bar_number: val("bar-number"),
    firm: val("firm"),
    address: val("address"),
    phone: val("phone"),
    email: val("email"),
  };
}

function applyProfileData(data) {
  if (!data) return;
  setVal("attorney-name", data.attorney_name || "");
  setVal("bar-number", data.bar_number || "");
  setVal("firm", data.firm || "");
  setVal("address", data.address || "");
  setVal("phone", data.phone || "");
  setVal("email", data.email || "");
}

function saveProfile() {
  const data = getProfileData();
  try {
    // Try Office.js settings first (persists with document or roaming)
    if (Office.context && Office.context.roamingSettings) {
      Office.context.roamingSettings.set(PROFILE_KEY, data);
      Office.context.roamingSettings.saveAsync(() => {
        updateBadge("Saved");
        setStatus("Attorney profile saved (roaming)");
      });
    } else {
      // Fallback to localStorage for testing / non-Office environments
      localStorage.setItem(PROFILE_KEY, JSON.stringify(data));
      updateBadge("Saved");
      setStatus("Attorney profile saved");
    }
  } catch (_) {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(data));
    updateBadge("Saved");
    setStatus("Attorney profile saved (local)");
  }
}

function loadSavedProfile() {
  let data = null;
  try {
    if (Office.context && Office.context.roamingSettings) {
      data = Office.context.roamingSettings.get(PROFILE_KEY);
    }
  } catch (_) {
    // ignore
  }
  if (!data) {
    try {
      const raw = localStorage.getItem(PROFILE_KEY);
      if (raw) data = JSON.parse(raw);
    } catch (_) {
      // ignore
    }
  }
  if (data) {
    applyProfileData(data);
    updateBadge("Loaded");

    // Auto-collapse attorney section since it's filled
    const section = document.getElementById("section-attorney");
    const body = document.getElementById("attorney-body");
    section.classList.remove("open");
    body.classList.add("collapsed");

    setStatus("Attorney profile loaded");
  }
}

function clearProfile() {
  try {
    if (Office.context && Office.context.roamingSettings) {
      Office.context.roamingSettings.remove(PROFILE_KEY);
      Office.context.roamingSettings.saveAsync();
    }
  } catch (_) {
    // ignore
  }
  localStorage.removeItem(PROFILE_KEY);
  updateBadge("");
  setStatus("Saved attorney profile cleared");
}

function updateBadge(text) {
  document.getElementById("attorney-saved-badge").textContent = text;
}

// ── Client-Side Validation ───────────────────────────────────────────

function clearErrors() {
  document.querySelectorAll(".field-error").forEach((el) => (el.textContent = ""));
  document.querySelectorAll(".invalid").forEach((el) => el.classList.remove("invalid"));
}

function setFieldError(inputId, errorId, msg) {
  const input = document.getElementById(inputId);
  const error = document.getElementById(errorId);
  if (input) input.classList.add("invalid");
  if (error) error.textContent = msg;
}

function validateRequired() {
  clearErrors();
  let valid = true;

  // Case number
  if (!val("case-number")) {
    setFieldError("case-number", "err-case-number", "Case number is required");
    valid = false;
  }

  // At least 2 parties with names
  const parties = getParties();
  if (parties.length < 2) {
    // Mark empty party name fields
    document.querySelectorAll(".party-row").forEach((row) => {
      const input = row.querySelector(".party-name");
      const error = row.querySelector(".party-name-error");
      if (!input.value.trim()) {
        input.classList.add("invalid");
        if (error) error.textContent = "Party name is required";
        valid = false;
      }
    });
  }

  // Attorney fields
  const requiredAttorney = [
    ["attorney-name", "err-attorney-name", "Attorney name is required"],
    ["bar-number", "err-bar-number", "Bar number is required"],
    ["address", "err-address", "Address is required"],
    ["phone", "err-phone", "Phone is required"],
    ["email", "err-email", "Email is required"],
  ];

  for (const [id, errId, msg] of requiredAttorney) {
    if (!val(id)) {
      setFieldError(id, errId, msg);
      valid = false;

      // Auto-expand attorney section to show errors
      const section = document.getElementById("section-attorney");
      const body = document.getElementById("attorney-body");
      section.classList.add("open");
      body.classList.remove("collapsed");
    }
  }

  return valid;
}

// ── Helpers ──────────────────────────────────────────────────────────

function val(id) {
  return document.getElementById(id).value.trim();
}

function setVal(id, value) {
  document.getElementById(id).value = value;
}

function setStatus(msg, loading) {
  document.getElementById("status-text").textContent = msg;
  const spinner = document.getElementById("spinner");
  if (loading) {
    spinner.classList.remove("hidden");
  } else {
    spinner.classList.add("hidden");
  }
}

function showResults(html) {
  const section = document.getElementById("results-section");
  const content = document.getElementById("results-content");
  content.innerHTML = html;
  section.classList.remove("hidden");
  // Scroll to results
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}

function hideResults() {
  document.getElementById("results-section").classList.add("hidden");
}

function buildMetadata() {
  return {
    jurisdiction: "wisconsin",
    court_level: "appellate",
    document_type: "brief",
    case: {
      case_number: val("case-number"),
      court_name: val("court-name"),
      district: val("district") || null,
      county_of_origin: val("county") || null,
      judge_name: val("judge") || null,
      parties: getParties(),
    },
    attorney: {
      name: val("attorney-name"),
      bar_number: val("bar-number"),
      firm: val("firm") || null,
      address: val("address"),
      phone: val("phone"),
      email: val("email"),
    },
    document_title: val("doc-title"),
  };
}

async function getDocumentText() {
  return Word.run(async (context) => {
    const body = context.document.body;
    body.load("text");
    await context.sync();
    return body.text;
  });
}

async function apiPost(endpoint, body) {
  const resp = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp;
}

function renderIssues(issues) {
  if (!issues.length) {
    return '<div class="success">No issues found.</div>';
  }
  return issues
    .map(
      (i) =>
        `<div class="issue issue-${i.severity}">
          <strong>${i.code}</strong>: ${i.message}
        </div>`
    )
    .join("");
}

function renderSections(sections) {
  if (!sections.length) return "";
  const items = sections
    .map((s) => {
      const cls = s.is_generated ? ' class="generated"' : "";
      const tag = s.is_generated ? " (generated)" : "";
      return `<li${cls}>${"&nbsp;".repeat((s.level - 1) * 4)}${s.heading}${tag}</li>`;
    })
    .join("");
  return `<h3>Sections</h3><ul class="section-list">${items}</ul>`;
}

function disableButtons(disabled) {
  document.querySelectorAll("#actions-section .btn").forEach((b) => (b.disabled = disabled));
}

// ── Confirmation Dialog ──────────────────────────────────────────────

function showConfirmDialog() {
  return new Promise((resolve) => {
    const overlay = document.getElementById("confirm-overlay");
    overlay.classList.remove("hidden");

    const onOk = () => {
      overlay.classList.add("hidden");
      cleanup();
      resolve(true);
    };
    const onCancel = () => {
      overlay.classList.add("hidden");
      cleanup();
      resolve(false);
    };
    const cleanup = () => {
      document.getElementById("btn-confirm-ok").removeEventListener("click", onOk);
      document.getElementById("btn-confirm-cancel").removeEventListener("click", onCancel);
    };

    document.getElementById("btn-confirm-ok").addEventListener("click", onOk);
    document.getElementById("btn-confirm-cancel").addEventListener("click", onCancel);
  });
}

// ── Action Buttons ───────────────────────────────────────────────────

function initActionButtons() {
  document.getElementById("btn-validate").addEventListener("click", onValidate);
  document.getElementById("btn-format").addEventListener("click", onFormat);
  document.getElementById("btn-citations").addEventListener("click", onCitations);
}

async function onValidate() {
  if (!validateRequired()) {
    setStatus("Please fill in required fields");
    return;
  }

  disableButtons(true);
  setStatus("Validating...", true);
  hideResults();

  try {
    const text = await getDocumentText();
    const resp = await apiPost("/validate", {
      text,
      metadata: buildMetadata(),
      variant: val("variant") || null,
    });
    const data = await resp.json();

    let html = `<h3>${data.valid ? "Valid" : `${data.issue_count} Issue(s)`}</h3>`;
    html += renderIssues(data.issues);
    html += renderSections(data.sections);
    showResults(html);
    setStatus(data.valid ? "Validation passed" : `${data.issue_count} issue(s) found`);
  } catch (err) {
    showResults(`<div class="issue issue-error">${err.message}</div>`);
    setStatus("Validation failed");
  } finally {
    disableButtons(false);
  }
}

async function onFormat() {
  if (!validateRequired()) {
    setStatus("Please fill in required fields");
    return;
  }

  // Show confirmation dialog
  const confirmed = await showConfirmDialog();
  if (!confirmed) {
    setStatus("Format cancelled");
    return;
  }

  disableButtons(true);
  setStatus("Formatting...", true);
  hideResults();

  try {
    const text = await getDocumentText();
    const variant = val("variant") || null;
    const wordCount = val("word-count") ? parseInt(val("word-count")) : null;
    const insertMissing = document.getElementById("insert-missing").checked;

    const resp = await apiPost("/format", {
      text,
      metadata: buildMetadata(),
      variant,
      word_count: wordCount,
      insert_missing: insertMissing,
      output_format: "docx",
    });

    // Download the DOCX and insert into Word
    const blob = await resp.blob();
    const reader = new FileReader();
    reader.onload = async () => {
      const base64 = reader.result.split(",")[1];
      await Word.run(async (context) => {
        context.document.body.insertFileFromBase64(base64, Word.InsertLocation.replace);
        await context.sync();
      });
      showResults('<div class="success">Document formatted successfully.</div>');
      setStatus("Format complete");
    };
    reader.onerror = () => {
      showResults('<div class="issue issue-error">Failed to read formatted document.</div>');
      setStatus("Format failed");
    };
    reader.readAsDataURL(blob);
  } catch (err) {
    showResults(`<div class="issue issue-error">${err.message}</div>`);
    setStatus("Format failed");
  } finally {
    disableButtons(false);
  }
}

async function onCitations() {
  disableButtons(true);
  setStatus("Checking citations...", true);
  hideResults();

  try {
    const text = await getDocumentText();
    const resp = await apiPost("/citations", { text });
    const data = await resp.json();

    let html = `<h3>Citations Found: ${data.total_citations}</h3>`;
    html += `<div style="font-size:11px; margin:6px 0; color:#605e5c;">
      Cases: ${data.cases} &middot; Short cites: ${data.short_cites} &middot;
      Id.: ${data.id_references} &middot; Statutes: ${data.statutes}
    </div>`;
    html += renderIssues(data.issues);
    showResults(html);
    setStatus(`${data.total_citations} citations, ${data.issues.length} issue(s)`);
  } catch (err) {
    showResults(`<div class="issue issue-error">${err.message}</div>`);
    setStatus("Citation check failed");
  } finally {
    disableButtons(false);
  }
}
