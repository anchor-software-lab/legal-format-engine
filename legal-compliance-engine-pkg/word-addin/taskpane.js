/* Legal Format Engine - Word Add-in JavaScript */

const API_BASE = "https://localhost:8443";
let pendingFormat = false;

// ─── Office.js Init ───

Office.onReady(function (info) {
    if (info.host === Office.HostType.Word) {
        loadAttorneyProfile();
        loadLetterheads();
        setStatus("Ready");
    }
});

// ─── Section Toggle ───

function toggleSection(id) {
    var el = document.getElementById(id);
    el.classList.toggle("expanded");
}

// ─── Parties ───

function addParty() {
    var list = document.getElementById("partyList");
    var idx = list.children.length;
    var row = document.createElement("div");
    row.className = "party-row";
    row.dataset.index = idx;
    row.innerHTML =
        '<input type="text" class="party-name" placeholder="Party name" />' +
        '<select class="party-role">' +
        '<option value="plaintiff">Plaintiff</option>' +
        '<option value="defendant">Defendant</option>' +
        '<option value="appellant">Appellant</option>' +
        '<option value="respondent">Respondent</option>' +
        '</select>' +
        '<input type="text" class="party-designation" placeholder="Role" />' +
        '<button class="btn-remove" onclick="this.parentElement.remove()">×</button>';
    list.appendChild(row);
}

// ─── Attorney Profile ───

function saveAttorneyProfile() {
    var profile = {
        name: document.getElementById("attorneyName").value,
        bar_number: document.getElementById("barNumber").value,
        firm: document.getElementById("firm").value,
        address: document.getElementById("address").value,
        phone: document.getElementById("phone").value,
        email: document.getElementById("email").value,
    };
    try {
        if (Office.context && Office.context.roamingSettings) {
            Office.context.roamingSettings.set("attorneyProfile", JSON.stringify(profile));
            Office.context.roamingSettings.saveAsync();
        }
    } catch (e) {
        localStorage.setItem("attorneyProfile", JSON.stringify(profile));
    }
    document.getElementById("attorney-badge").classList.remove("hidden");
    setStatus("Attorney profile saved");
}

function loadAttorneyProfile() {
    var data = null;
    try {
        if (Office.context && Office.context.roamingSettings) {
            data = Office.context.roamingSettings.get("attorneyProfile");
        }
    } catch (e) {
        data = localStorage.getItem("attorneyProfile");
    }
    if (data) {
        var profile = typeof data === "string" ? JSON.parse(data) : data;
        document.getElementById("attorneyName").value = profile.name || "";
        document.getElementById("barNumber").value = profile.bar_number || "";
        document.getElementById("firm").value = profile.firm || "";
        document.getElementById("address").value = profile.address || "";
        document.getElementById("phone").value = profile.phone || "";
        document.getElementById("email").value = profile.email || "";
        document.getElementById("attorney-badge").classList.remove("hidden");
    }
}

// ─── Validation ───

function validateRequiredFields() {
    var valid = true;
    var fields = [
        { id: "caseNumber", label: "Case Number" },
        { id: "attorneyName", label: "Attorney Name" },
    ];
    fields.forEach(function (f) {
        var el = document.getElementById(f.id);
        var val = el.value.trim();
        el.classList.remove("error");
        var errEl = el.parentElement.querySelector(".error-msg");
        if (errEl) errEl.remove();
        if (!val) {
            el.classList.add("error");
            var msg = document.createElement("div");
            msg.className = "error-msg";
            msg.textContent = f.label + " is required";
            el.parentElement.appendChild(msg);
            valid = false;
            // Expand parent section
            var sec = el.closest(".collapsible");
            if (sec) sec.classList.add("expanded");
        }
    });
    if (!valid) setStatus("Please fill in required fields");
    return valid;
}

// ─── Build Request Data ───

function buildMetadata() {
    var parties = [];
    var rows = document.querySelectorAll(".party-row");
    rows.forEach(function (row) {
        var name = row.querySelector(".party-name").value.trim();
        var role = row.querySelector(".party-role").value;
        var desig = row.querySelector(".party-designation").value.trim();
        if (name) parties.push({ name: name, role: role, designation: desig || null });
    });

    return {
        case_number: document.getElementById("caseNumber").value.trim(),
        case_name: parties.length >= 2
            ? parties[0].name + " v. " + parties[1].name
            : "",
        district: document.getElementById("district").value,
        county: document.getElementById("county").value.trim(),
        judge: document.getElementById("judge").value.trim(),
        document_title: document.getElementById("docType").value,
        parties: parties,
        attorney: {
            name: document.getElementById("attorneyName").value.trim(),
            bar_number: document.getElementById("barNumber").value.trim(),
            firm: document.getElementById("firm").value.trim(),
            address: document.getElementById("address").value.trim(),
            phone: document.getElementById("phone").value.trim(),
            email: document.getElementById("email").value.trim(),
        },
        word_count: parseInt(document.getElementById("wordCount").value) || null,
        insert_missing: document.getElementById("insertMissing").checked,
        letterhead_id: document.getElementById("letterheadSelect").value || null,
    };
}

// ─── Actions ───

function onFormat() {
    if (!validateRequiredFields()) return;
    document.getElementById("confirmDialog").classList.remove("hidden");
}

function hideConfirm() {
    document.getElementById("confirmDialog").classList.add("hidden");
}

function confirmFormat() {
    hideConfirm();
    setStatus("Formatting...", true);

    Word.run(function (context) {
        var body = context.document.body;
        body.load("text");
        return context.sync().then(function () {
            var text = body.text;
            var meta = buildMetadata();

            var payload = {
                text: text,
                jurisdiction: "wisconsin",
                document_type: "appellate_brief",
                document_title: meta.document_title,
                case_name: meta.case_name,
                case_number: meta.case_number,
                district: meta.district,
                county: meta.county,
                judge: meta.judge,
                parties: meta.parties,
                attorney: meta.attorney,
                word_count: meta.word_count,
                insert_missing: meta.insert_missing,
                letterhead_id: meta.letterhead_id,
                output_format: "docx",
            };

            return fetch(API_BASE + "/api/format", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
        }).then(function (resp) {
            return resp.json();
        }).then(function (data) {
            if (data.docx_base64) {
                return Word.run(function (ctx) {
                    ctx.document.body.insertFileFromBase64(data.docx_base64, "Replace");
                    return ctx.sync();
                });
            }
        }).then(function () {
            setStatus("Document formatted successfully");
        });
    }).catch(function (err) {
        setStatus("Error: " + err.message);
    });
}

function onValidate() {
    setStatus("Validating...", true);
    Word.run(function (context) {
        var body = context.document.body;
        body.load("text");
        return context.sync().then(function () {
            return fetch(API_BASE + "/api/validate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: body.text,
                    jurisdiction: "wisconsin",
                    document_type: "appellate_brief",
                }),
            });
        }).then(function (r) { return r.json(); })
        .then(function (data) {
            showResults(data.issues || []);
            setStatus(data.count + " issue(s) found");
        });
    }).catch(function (err) { setStatus("Error: " + err.message); });
}

function onCitations() {
    setStatus("Checking citations...", true);
    Word.run(function (context) {
        var body = context.document.body;
        body.load("text");
        return context.sync().then(function () {
            return fetch(API_BASE + "/api/citations", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: body.text }),
            });
        }).then(function (r) { return r.json(); })
        .then(function (data) {
            showResults(data.issues || []);
            setStatus(data.citation_count + " citations, " + (data.issues || []).length + " issues");
        });
    }).catch(function (err) { setStatus("Error: " + err.message); });
}

// ─── Results Display ───

function showResults(issues) {
    var container = document.getElementById("results");
    var list = document.getElementById("resultsList");
    list.innerHTML = "";
    if (issues.length === 0) {
        list.innerHTML = '<div class="issue-card info">No issues found</div>';
    } else {
        issues.forEach(function (issue) {
            var card = document.createElement("div");
            card.className = "issue-card " + (issue.severity || "info");
            card.innerHTML =
                '<div class="issue-code">' + (issue.code || "") + '</div>' +
                '<div>' + (issue.message || "") + '</div>';
            list.appendChild(card);
        });
    }
    container.classList.remove("hidden");
}

// ─── Status Bar ───

function setStatus(text, loading) {
    document.getElementById("statusText").textContent = text;
    var spinner = document.getElementById("spinner");
    if (loading) spinner.classList.remove("hidden");
    else spinner.classList.add("hidden");
}

// ─── Letterhead ───

function loadLetterheads() {
    fetch(API_BASE + "/api/letterheads")
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var sel = document.getElementById("letterheadSelect");
            sel.innerHTML = '<option value="">None</option>';
            (data || []).forEach(function (lh) {
                var opt = document.createElement("option");
                opt.value = lh.id;
                opt.textContent = lh.name;
                sel.appendChild(opt);
            });
        })
        .catch(function () { /* server may not be running yet */ });
}

function showLetterheadEditor() {
    document.getElementById("letterheadEditor").classList.remove("hidden");
    if (document.getElementById("letterheadLines").children.length === 0) {
        addLetterheadLine();
    }
}

function addLetterheadLine() {
    var container = document.getElementById("letterheadLines");
    var row = document.createElement("div");
    row.className = "letterhead-line";
    row.innerHTML =
        '<input type="text" placeholder="Text" />' +
        '<select><option value="left">L</option><option value="center">C</option><option value="right">R</option></select>' +
        '<label><input type="checkbox" class="lh-bold" /> B</label>' +
        '<button class="btn-remove" onclick="this.parentElement.remove()">×</button>';
    container.appendChild(row);
}

function saveLetterhead() {
    var name = document.getElementById("letterheadName").value.trim();
    if (!name) { setStatus("Letterhead name required"); return; }

    var lines = [];
    document.querySelectorAll("#letterheadLines .letterhead-line").forEach(function (row) {
        var text = row.querySelector("input[type=text]").value;
        var align = row.querySelector("select").value;
        var bold = row.querySelector(".lh-bold").checked;
        if (text) lines.push({ text: text, alignment: align, bold: bold, font_size_pt: 10 });
    });

    fetch(API_BASE + "/api/letterheads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name, lines: lines }),
    })
    .then(function (r) { return r.json(); })
    .then(function () {
        loadLetterheads();
        document.getElementById("letterheadEditor").classList.add("hidden");
        setStatus("Letterhead saved");
    })
    .catch(function (err) { setStatus("Error: " + err.message); });
}
