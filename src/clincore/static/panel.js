const CONFIG = {
    apiBase: "http://127.0.0.1:8000",
    tenantId: "5c091694-0e5a-46a0-b1d5-01fb7655f0ab",
    apiKey: "AjT03TWidJwlMeUnaeH4GfP3WNQpEUvWVlN434kv0_w"
};

const I18N = {
    fa: {
        dashboard: "داشبورد",
        new_patient: "بیمار جدید",
        patient_list: "لیست بیماران",
        new_encounter: "ویزیت جدید",
        mcare_analysis: "MCARE",
        prescription: "نسخه",
        total_patients: "کل بیماران",
        total_encounters: "ویزیت‌ها",
        mcare_analyses: "تحلیل‌های MCARE",
        welcome_msg: "به پنل کلینیکی ClinCore خوش آمدید. سیستم فعال است.",
        first_name: "نام",
        last_name: "نام خانوادگی",
        national_id: "کد ملی",
        birth_date: "تاریخ تولد",
        gender: "جنسیت",
        phone: "تلفن",
        notes: "یادداشت",
        save: "ذخیره",
        patient_files: "پرونده بیمار",
        save_local: "ذخیره محلی (به زودی)",
        save_db: "ذخیره در پایگاه داده (به زودی)",
        search: "جستجو...",
        refresh: "بارگذاری مجدد",
        id: "شناسه",
        name: "نام",
        actions: "عملیات",
        no_patients: "بیماری ثبت نشده است.",
        patient_id: "شناسه بیمار",
        patient_id_optional: "شناسه بیمار (اختیاری)",
        encounter_date: "تاریخ ویزیت",
        chief_complaint: "شکایت اصلی",
        clinical_notes: "یادداشت بالینی",
        diagnosis: "تشخیص",
        symptom_ids: "کدهای علائم (symptom_ids)",
        analyze: "تحلیل",
        mcare_results: "نتایج تحلیل",
        new_analysis: "تحلیل جدید",
        rank: "رتبه",
        remedy: "دارو",
        raw_score: "Raw Score",
        coverage: "Coverage",
        potency: "پتانسی پیشنهادی",
        rubrics_label: "Rubrics",
        coming_soon: "به زودی فعال می‌شود",
        patient_name: "نام بیمار",
        rx_date: "تاریخ",
        dosage_notes: "دستور مصرف",
        pharmacy_version: "نسخه داروخانه",
        patient_version: "نسخه بیمار",
        copy: "کپی",
        print: "چاپ",
        telegram: "تلگرام (به زودی)",
        eitaa: "ایتا (به زودی)",
        generate_rx: "تولید نسخه",
        male: "مرد",
        female: "زن",
        other: "سایر",
        use: "انتخاب",
        error_api: "خطا در ارتباط با سرور.",
        saved: "ذخیره شد.",
        copy_done: "کپی شد.",
        enter_symptoms: "لطفاً کد علائم وارد کنید.",
        analyzing: "در حال تحلیل..."
    },
    en: {
        dashboard: "Dashboard",
        new_patient: "New Patient",
        patient_list: "Patient List",
        new_encounter: "New Encounter",
        mcare_analysis: "MCARE",
        prescription: "Prescription",
        total_patients: "Total Patients",
        total_encounters: "Encounters",
        mcare_analyses: "MCARE Analyses",
        welcome_msg: "Welcome to the ClinCore clinical panel. System is active.",
        first_name: "First Name",
        last_name: "Last Name",
        national_id: "National ID",
        birth_date: "Date of Birth",
        gender: "Gender",
        phone: "Phone",
        notes: "Notes",
        save: "Save",
        patient_files: "Patient Files",
        save_local: "Save Local (soon)",
        save_db: "Save to Database (soon)",
        search: "Search...",
        refresh: "Refresh",
        id: "ID",
        name: "Name",
        actions: "Actions",
        no_patients: "No patients registered.",
        patient_id: "Patient ID",
        patient_id_optional: "Patient ID (optional)",
        encounter_date: "Encounter Date",
        chief_complaint: "Chief Complaint",
        clinical_notes: "Clinical Notes",
        diagnosis: "Diagnosis",
        symptom_ids: "Symptom IDs",
        analyze: "Analyze",
        mcare_results: "Analysis Results",
        new_analysis: "New Analysis",
        rank: "Rank",
        remedy: "Remedy",
        raw_score: "Raw Score",
        coverage: "Coverage",
        potency: "Suggested Potency",
        rubrics_label: "Rubrics",
        coming_soon: "Coming soon",
        patient_name: "Patient Name",
        rx_date: "Date",
        dosage_notes: "Dosage Instructions",
        pharmacy_version: "Pharmacy Version",
        patient_version: "Patient Version",
        copy: "Copy",
        print: "Print",
        telegram: "Telegram (soon)",
        eitaa: "Eitaa (soon)",
        generate_rx: "Generate Prescription",
        male: "Male",
        female: "Female",
        other: "Other",
        use: "Select",
        error_api: "Server communication error.",
        saved: "Saved.",
        copy_done: "Copied.",
        enter_symptoms: "Please enter symptom codes.",
        analyzing: "Analyzing..."
    }
};

const NAV_SECTION_KEYS = ["dashboard", "new_patient", "patient_list", "new_encounter", "mcare_analysis", "prescription"];

let currentLang = "fa";

function t(key) {
    return (I18N[currentLang] && I18N[currentLang][key]) ? I18N[currentLang][key] : key;
}

function safeText(val) {
    return String(val == null ? "" : val);
}

function el(id) {
    return document.getElementById(id);
}

function setMsg(elId, text, type) {
    const node = el(elId);
    if (!node) return;
    node.textContent = text;
    node.className = "form-msg" + (type ? " " + type : "");
}

function applyLang() {
    document.documentElement.lang = currentLang;
    document.body.classList.remove("rtl", "ltr");
    document.body.classList.add(currentLang === "fa" ? "rtl" : "ltr");
    const langBtn = el("lang-toggle");
    if (langBtn) langBtn.textContent = currentLang === "fa" ? "EN" : "FA";

    document.querySelectorAll("[data-i18n]").forEach(function(node) {
        const key = node.getAttribute("data-i18n");
        if (key && I18N[currentLang][key] !== undefined) {
            node.textContent = I18N[currentLang][key];
        }
    });

    document.querySelectorAll("[data-i18n-placeholder]").forEach(function(node) {
        const key = node.getAttribute("data-i18n-placeholder");
        if (key && I18N[currentLang][key] !== undefined) {
            node.placeholder = I18N[currentLang][key];
        }
    });

    document.querySelectorAll(".nav-link").forEach(function(link, i) {
        const key = NAV_SECTION_KEYS[i];
        const span = link.querySelector("span[data-i18n]");
        if (span && key && I18N[currentLang][key] !== undefined) {
            span.textContent = I18N[currentLang][key];
        }
    });
}

function navigateTo(sectionName) {
    document.querySelectorAll(".panel-section").forEach(function(s) {
        s.classList.remove("active");
    });
    document.querySelectorAll(".nav-link").forEach(function(l) {
        l.classList.remove("active");
    });
    const target = el("section-" + sectionName);
    if (target) target.classList.add("active");
    const activeLink = document.querySelector(".nav-link[data-section='" + sectionName + "']");
    if (activeLink) activeLink.classList.add("active");

    if (sectionName === "patient-list") loadPatients();
    if (sectionName === "dashboard") loadDashboard();
}

function patientHeaders() {
    return {
        "Content-Type": "application/json",
        "X-API-Key": CONFIG.apiKey,
        "X-Tenant-Id": CONFIG.tenantId
    };
}

function mcareHeaders() {
    return {
        "Content-Type": "application/json",
        "X-API-Key": CONFIG.apiKey,
        "X-Tenant-Id": CONFIG.tenantId
    };
}

function loadDashboard() {
    fetch(CONFIG.apiBase + "/patients", { headers: patientHeaders() })
        .then(function(r) { return r.ok ? r.json() : null; })
        .then(function(data) {
            if (!data) return;
            const count = data.total != null ? data.total : (Array.isArray(data) ? data.length : (Array.isArray(data.patients) ? data.patients.length : "—"));
            const node = el("stat-patients");
            if (node) node.textContent = safeText(count);
        })
        .catch(function() {});

    fetch(CONFIG.apiBase + "/encounters", { headers: patientHeaders() })
        .then(function(r) { return r.ok ? r.json() : null; })
        .then(function(data) {
            if (!data) return;
            const count = Array.isArray(data) ? data.length : (data.total != null ? data.total : "—");
            const node = el("stat-encounters");
            if (node) node.textContent = safeText(count);
        })
        .catch(function() {});
}

function loadPatients() {
    fetch(CONFIG.apiBase + "/patients", { headers: patientHeaders() })
        .then(function(r) {
            if (!r.ok) throw new Error(r.status);
            return r.json();
        })
        .then(function(data) {
            const list = Array.isArray(data) ? data : (Array.isArray(data.patients) ? data.patients : (Array.isArray(data.items) ? data.items : []));
            renderPatientTable(list);
        })
        .catch(function() {
            const tbody = el("patient-tbody");
            if (tbody) { while (tbody.firstChild) tbody.removeChild(tbody.firstChild); }
            const empty = el("patient-list-empty");
            if (empty) {
                empty.style.display = "flex";
                const span = empty.querySelector("span");
                if (span) span.textContent = t("error_api");
            }
        });
}

function renderPatientTable(patients) {
    const tbody = el("patient-tbody");
    const emptyEl = el("patient-list-empty");
    if (!tbody) return;
    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
    if (!patients.length) {
        if (emptyEl) {
            emptyEl.style.display = "flex";
            const span = emptyEl.querySelector("span");
            if (span) span.textContent = t("no_patients");
        }
        return;
    }
    if (emptyEl) emptyEl.style.display = "none";
    patients.forEach(function(p, idx) {
        p._seq = idx + 1;
        const tr = document.createElement("tr");
        ["patient_no", "full_name", "national_id", "phone"].forEach(function(field) {
            const td = document.createElement("td");
            td.textContent = safeText(p[field]);
            tr.appendChild(td);
        });
        const tdAct = document.createElement("td");
        const btn = document.createElement("button");
        btn.className = "btn-use-remedy";
        btn.textContent = t("use");
        btn.addEventListener("click", function() { prefillEncounter(p); });
        tdAct.appendChild(btn);
        tr.appendChild(tdAct);
        tbody.appendChild(tr);
    });
}

function prefillEncounter(patient) {
    navigateTo("new-encounter");
    // UUID → hidden field for API
    const uuidField = document.getElementById("encounter-pid-uuid");
    if (uuidField) uuidField.value = safeText(patient.id);
    // Display ID → visible read-only field
    const displayField = document.getElementById("encounter-pid-display");
    if (displayField) {
        const serial = patient.serial_number || patient.display_id || patient._seq || null;
        displayField.value = serial
            ? "P-" + String(serial).padStart(4, "0")
            : safeText(patient.id);
    }
    const nameDisplay = el("encounter-patient-name");
    if (nameDisplay) nameDisplay.textContent = safeText(patient.full_name || patient.id);
    // ذخیره برای استفاده در MCARE و نسخه
    window._currentPatient = patient;
}

function setupPatientSearch() {
    const searchInput = el("patient-search");
    if (!searchInput) return;
    searchInput.addEventListener("input", function() {
        const q = searchInput.value.toLowerCase();
        const rows = document.querySelectorAll("#patient-tbody tr");
        rows.forEach(function(row) {
            row.style.display = row.textContent.toLowerCase().includes(q) ? "" : "none";
        });
    });
}

function setupNewPatient() {
    const form = el("form-new-patient");
    if (!form) return;
    form.addEventListener("submit", function(e) {
        e.preventDefault();
        const fd = new FormData(form);
        const body = {};
        fd.forEach(function(v, k) { body[k] = v; });
        body["full_name"] = ((body["first_name"] || "") + " " + (body["last_name"] || "")).trim();
        delete body["first_name"];
        delete body["last_name"];
        setMsg("new-patient-msg", "...", "");
        fetch(CONFIG.apiBase + "/patients", {
            method: "POST",
            headers: patientHeaders(),
            body: JSON.stringify(body)
        })
        .then(function(r) {
            if (r.ok) return r.json().then(function() {
                setMsg("new-patient-msg", t("saved"), "success");
                form.reset();
            });
            return r.json().then(function(err) {
                setMsg("new-patient-msg", safeText(err.detail || r.status), "error");
            }).catch(function() {
                setMsg("new-patient-msg", safeText(r.status), "error");
            });
        })
        .catch(function() { setMsg("new-patient-msg", t("error_api"), "error"); });
    });
}

function setupNewEncounter() {
    const form = el("form-new-encounter");
    if (!form) return;
    const today = new Date().toISOString().split("T")[0];
    const dateField = form.querySelector("[name='encounter_date']");
    if (dateField && !dateField.value) dateField.value = today;

    form.addEventListener("submit", function(e) {
        e.preventDefault();
        const fd = new FormData(form);
        const body = {};
        fd.forEach(function(v, k) { body[k] = v; });
        setMsg("new-encounter-msg", "...", "");
        fetch(CONFIG.apiBase + "/encounters", {
            method: "POST",
            headers: patientHeaders(),
            body: JSON.stringify(body)
        })
        .then(function(r) {
            if (r.ok) return r.json().then(function() {
                setMsg("new-encounter-msg", t("saved"), "success");
                form.reset();
                if (dateField) dateField.value = today;
            });
            return r.json().then(function(err) {
                setMsg("new-encounter-msg", safeText(err.detail || r.status), "error");
            }).catch(function() {
                setMsg("new-encounter-msg", safeText(r.status), "error");
            });
        })
        .catch(function() { setMsg("new-encounter-msg", t("error_api"), "error"); });
    });
}

function suggestPotency(score, coverage) {
    if (score >= 1.8 && coverage >= 0.9) return "200C \u062A\u06A9 \u062F\u0632";
    if (score >= 1.4 && coverage >= 0.7) return "30C \u0647\u0631 12 \u0633\u0627\u0639\u062A";
    if (score >= 1.0) return "12C \u0631\u0648\u0632\u0627\u0646\u0647";
    return "6C \u0631\u0648\u0632\u0627\u0646\u0647";
}

function setupMcare() {
    const form = el("form-mcare");
    const resetBtn = el("btn-mcare-reset");
    if (!form) return;

    form.addEventListener("submit", function(e) {
        e.preventDefault();
        const narrativeEl = form.querySelector("[name='symptom_ids']");
        const narrative = narrativeEl ? narrativeEl.value.trim() : "";
        if (!narrative) {
            setMsg("mcare-msg", t("enter_symptoms"), "error");
            return;
        }
        const payload = { narrative: narrative };
        const patientId = form.querySelector("[name='patient_id']") ? form.querySelector("[name='patient_id']").value.trim() : "";
        if (patientId) payload.patient_id = patientId;
        setMsg("mcare-msg", t("analyzing"), "");
        fetch(CONFIG.apiBase + "/mcare/auto", {
            method: "POST",
            headers: mcareHeaders(),
            body: JSON.stringify(payload)
        })
        .then(function(r) {
            if (r.ok) return r.json().then(function(data) {
                setMsg("mcare-msg", "", "");
                renderMcareResult(data);
            });
            return r.json().then(function(err) {
                setMsg("mcare-msg", safeText(err.detail || r.status), "error");
            }).catch(function() {
                setMsg("mcare-msg", safeText(r.status), "error");
            });
        })
        .catch(function() { setMsg("mcare-msg", t("error_api"), "error"); });
    });

    if (resetBtn) {
        resetBtn.addEventListener("click", function() {
            el("mcare-result-wrap").style.display = "none";
            el("mcare-form-wrap").style.display = "block";
            form.reset();
            setMsg("mcare-msg", "", "");
        });
    }
}

function renderMcareResult(data) {
    const results = Array.isArray(data.results) ? data.results : [];
    const rubrics = Array.isArray(data.rubrics) ? data.rubrics : [];

    const rubricsEl = el("mcare-rubrics");
    if (rubricsEl) {
        rubricsEl.textContent = rubrics.length ? rubrics.join(" \u2502 ") : "\u2014";
    }

    const tbody = el("mcare-result-tbody");
    if (!tbody) return;
    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);

    results.forEach(function(item) {
        const score = parseFloat(item.mcare_score) || 0;
        const cov = parseFloat(item.coverage) || 0;
        const potency = suggestPotency(score, cov);

        const tr = document.createElement("tr");

        const tdRank = document.createElement("td");
        tdRank.textContent = safeText(item.rank);
        tr.appendChild(tdRank);

        const tdRemedy = document.createElement("td");
        const strong = document.createElement("strong");
        strong.textContent = safeText(item.remedy);
        tdRemedy.appendChild(strong);
        tr.appendChild(tdRemedy);

        const tdScore = document.createElement("td");
        tdScore.className = "score-val";
        tdScore.textContent = score.toFixed(3);
        tr.appendChild(tdScore);

        const tdRaw = document.createElement("td");
        tdRaw.textContent = safeText(item.raw_score);
        tr.appendChild(tdRaw);

        const tdCov = document.createElement("td");
        tdCov.textContent = (cov * 100).toFixed(1) + "%";
        tr.appendChild(tdCov);

        const tdPot = document.createElement("td");
        const badge = document.createElement("span");
        badge.className = "potency-badge";
        badge.textContent = potency;
        tdPot.appendChild(badge);
        tr.appendChild(tdPot);

        const tdAct = document.createElement("td");
        const btn = document.createElement("button");
        btn.className = "btn-use-remedy";
        btn.textContent = t("use");
        btn.addEventListener("click", function() {
            const rxRemedyEl = el("rx-remedy");
            const rxPotencyEl = el("rx-potency");
            if (rxRemedyEl) rxRemedyEl.value = safeText(item.remedy);
            if (rxPotencyEl) rxPotencyEl.value = potency;
            const rxNameEl = el("rx-patient-name");
            if (rxNameEl && window._currentPatient) {
                rxNameEl.value = safeText(window._currentPatient.full_name || "");
            }
            const rxDosageEl = el("rx-dosage");
            if (rxDosageEl && !rxDosageEl.value.trim()) {
                rxDosageEl.value = "طبق دستور پزشک";
            }
            navigateTo("prescription");
        });
        tdAct.appendChild(btn);
        tr.appendChild(tdAct);

        tbody.appendChild(tr);
    });

    el("mcare-form-wrap").style.display = "none";
    el("mcare-result-wrap").style.display = "block";
}

function copyToClipboard(text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).catch(function() { fallbackCopy(text); });
    } else {
        fallbackCopy(text);
    }
}

function fallbackCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.cssText = "position:fixed;top:0;left:0;opacity:0;pointer-events:none";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try { document.execCommand("copy"); } catch (_) {}
    document.body.removeChild(ta);
}

function printContent(text, title, isRtl) {
    const dir = isRtl ? "rtl" : "ltr";
    const win = window.open("", "_blank", "width=640,height=800");
    if (!win) return;
    const esc = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    win.document.write(
        "<!DOCTYPE html><html lang='" + (isRtl ? "fa" : "en") + "'>" +
        "<head><meta charset='UTF-8'>" +
        "<link rel='preconnect' href='https://fonts.googleapis.com'>" +
        "<link href='https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700&display=swap' rel='stylesheet'>" +
        "<title>" + title + "</title>" +
        "<style>" +
        "body{font-family:'Vazirmatn',sans-serif;direction:" + dir + ";padding:40px;color:#0f172a;font-size:14px;line-height:1.8}" +
        "h2{font-size:18px;margin-bottom:24px;padding-bottom:12px;border-bottom:2px solid #1d4ed8;color:#1d4ed8}" +
        "pre{white-space:pre-wrap;font-family:inherit;font-size:14px}" +
        "@media print{body{padding:20px}}" +
        "</style></head><body>" +
        "<h2>" + title + "</h2>" +
        "<pre>" + esc + "</pre>" +
        "</body></html>"
    );
    win.document.close();
    win.focus();
    setTimeout(function() { win.print(); }, 400);
}

function setupPrescription() {
    const today = new Date().toISOString().split("T")[0];
    const rxDateEl = el("rx-date");
    if (rxDateEl && !rxDateEl.value) rxDateEl.value = today;
    const rxNameEl = el("rx-patient-name");
    if (rxNameEl && !rxNameEl.value && window._currentPatient) {
        rxNameEl.value = safeText(window._currentPatient.full_name || "");
    }
    const rxDosageEl = el("rx-dosage");
    if (rxDosageEl && !rxDosageEl.value.trim()) {
        rxDosageEl.value = "طبق دستور پزشک";
    }

    const genBtn = el("btn-generate-rx");
    if (genBtn) {
        genBtn.addEventListener("click", function() {
            const name = (el("rx-patient-name") ? el("rx-patient-name").value.trim() : "") || "—";
            const date = (el("rx-date") ? el("rx-date").value : "") || today;
            const remedy = (el("rx-remedy") ? el("rx-remedy").value.trim() : "") || "—";
            const potency = (el("rx-potency") ? el("rx-potency").value.trim() : "") || "—";
            const dosage = (el("rx-dosage") ? el("rx-dosage").value.trim() : "") || "";

            const pharmacyEl = el("rx-pharmacy");
            const patientEl = el("rx-patient");

            if (pharmacyEl) {
                pharmacyEl.value =
                    "\u0628\u06CC\u0645\u0627\u0631: " + name + "\n" +
                    "\u062A\u0627\u0631\u06CC\u062E: " + date + "\n" +
                    "Rx:\n" +
                    "  " + remedy + " " + potency + "\n" +
                    (dosage ? "  \u062F\u0633\u062A\u0648\u0631: " + dosage + "\n" : "") +
                    "\n\u0627\u0645\u0636\u0627\u06CC \u067E\u0632\u0634\u06A9";
            }

            if (patientEl) {
                patientEl.value =
                    "\u0646\u0627\u0645 \u0628\u06CC\u0645\u0627\u0631: " + name + "\n" +
                    "\u062A\u0627\u0631\u06CC\u062E: " + date + "\n\n" +
                    "\u062F\u0627\u0631\u0648: " + remedy + "\n" +
                    "\u067E\u062A\u0627\u0646\u0633\u06CC: " + potency + "\n" +
                    (dosage ? "\u062F\u0633\u062A\u0648\u0631 \u0645\u0635\u0631\u0641: " + dosage + "\n" : "") +
                    "\n\u0644\u0637\u0641\u0627\u064B \u0637\u0628\u0642 \u062F\u0633\u062A\u0648\u0631 \u067E\u0632\u0634\u06A9 \u0645\u0635\u0631\u0641 \u0641\u0631\u0645\u0627\u06CC\u06CC\u062F.";
            }
        });
    }

    const btnCopyPharmacy = el("btn-copy-pharmacy");
    if (btnCopyPharmacy) {
        btnCopyPharmacy.addEventListener("click", function() {
            const ta = el("rx-pharmacy");
            if (ta) copyToClipboard(ta.value);
        });
    }

    const btnCopyPatient = el("btn-copy-patient");
    if (btnCopyPatient) {
        btnCopyPatient.addEventListener("click", function() {
            const ta = el("rx-patient");
            if (ta) copyToClipboard(ta.value);
        });
    }

    const btnPrintPharmacy = el("btn-print-pharmacy");
    if (btnPrintPharmacy) {
        btnPrintPharmacy.addEventListener("click", function() {
            const ta = el("rx-pharmacy");
            if (ta) printContent(ta.value, t("pharmacy_version"), currentLang === "fa");
        });
    }

    const btnPrintPatient = el("btn-print-patient");
    if (btnPrintPatient) {
        btnPrintPatient.addEventListener("click", function() {
            const ta = el("rx-patient");
            if (ta) printContent(ta.value, t("patient_version"), currentLang === "fa");
        });
    }
}

function init() {
    applyLang();

    document.querySelectorAll(".nav-link").forEach(function(link) {
        link.addEventListener("click", function(e) {
            e.preventDefault();
            navigateTo(link.getAttribute("data-section"));
        });
    });

    const langBtn = el("lang-toggle");
    if (langBtn) {
        langBtn.addEventListener("click", function() {
            currentLang = currentLang === "fa" ? "en" : "fa";
            applyLang();
        });
    }

    const refreshBtn = el("btn-refresh-patients");
    if (refreshBtn) refreshBtn.addEventListener("click", loadPatients);

    setupPatientSearch();
    setupNewPatient();
    setupNewEncounter();
    setupMcare();
    setupPrescription();
    loadDashboard();
}

document.addEventListener("DOMContentLoaded", init);
