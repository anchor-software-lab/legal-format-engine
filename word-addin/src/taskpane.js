/* global Office, Word */

const API_BASE = "https://localhost:8443/api";

// ── Office.js Initialization ─────────────────────────────────────────

Office.onReady((info) => {
  if (info.host === Office.HostType.Word) {
    document.getElementById("btn-validate").onclick = onValidate;
    document.getElementById("btn-format").onclick = onFormat;
    document.getElementById("btn-citations").onclick = onCitations;
    setStatus("Ready");
  }
});

// ── Helpers ──────────────────────────────────────────────────────────

function setStatus(msg) {
  document.getElementById("status-text").textContent = msg;
}

function showResults(html) {
  const section = document.getElementById("results-section");
  const content = document.getElementById("results-content");
  content.innerHTML = html;
  section.classList.remove("hidden");
}

function hideResults() {
  document.getElementById("results-section").classList.add("hidden");
}

function val(id) {
  return document.getElementById(id).value.trim();
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
      parties: [
        { name: val("plaintiff-name"), role: "plaintiff-respondent" },
        { name: val("defendant-name"), role: "defendant-appellant" },
      ],
    },
    attorney: {
      name: val("attorney-name"),
      bar_number: val("bar-number"),
      firm: val("firm") || null,
      address: val("address"),
      phone: val("phone"),
      email: val("email"),
    },
    document_title: "Brief of Defendant-Appellant",
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
  document.querySelectorAll(".btn").forEach((b) => (b.disabled = disabled));
}

// ── Actions ──────────────────────────────────────────────────────────

async function onValidate() {
  disableButtons(true);
  setStatus("Validating...");
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
  disableButtons(true);
  setStatus("Formatting...");
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
        // Replace entire document body with formatted content
        context.document.body.insertFileFromBase64(base64, Word.InsertLocation.replace);
        await context.sync();
      });
      showResults('<div class="success">Document formatted successfully.</div>');
      setStatus("Format complete");
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
  setStatus("Checking citations...");
  hideResults();

  try {
    const text = await getDocumentText();
    const resp = await apiPost("/citations", { text });
    const data = await resp.json();

    let html = `<h3>Citations Found: ${data.total_citations}</h3>`;
    html += `<div style="font-size:12px; margin:8px 0;">
      Cases: ${data.cases} | Short cites: ${data.short_cites} |
      Id.: ${data.id_references} | Statutes: ${data.statutes}
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
