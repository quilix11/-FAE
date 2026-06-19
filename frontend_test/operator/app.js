// ═══════════════════════════════════════════════════════════
// Operator Dashboard — app.js
// Fujikura Applicator Tracking System
// ═══════════════════════════════════════════════════════════

const API_BASE = "/api/v1";

// ── Auth guard ───────────────────────────────────────────
const TOKEN = localStorage.getItem("token");
if (!TOKEN) {
    window.location.replace("/");
}

function authHeaders() {
    return { "Content-Type": "application/json", Authorization: `Bearer ${TOKEN}` };
}

// ── Read machine code from URL param ─────────────────────
const urlParams = new URLSearchParams(window.location.search);
const MACHINE_CODE = urlParams.get("machine") || localStorage.getItem("machine") || "G01";

// ── DOM references ───────────────────────────────────────
const elMachineCode = document.getElementById("machineCode");
const elZoneName = document.getElementById("zoneName");
const elCapacityCount = document.getElementById("capacityCount");
const elCapacityFill = document.getElementById("capacityFill");
const elCardGrid = document.getElementById("cardGrid");
const elEmptyState = document.getElementById("emptyState");
const elToastContainer = document.getElementById("toastContainer");
const elManualScanInput = document.getElementById("manualScanInput");
const elManualScanBtn = document.getElementById("manualScanBtn");

// ── State ────────────────────────────────────────────────
let refreshTimer = null;

// ═════════════════════════════════════════════════════════
// Toast notifications
// ═════════════════════════════════════════════════════════

/**
 * Show a toast notification.
 * @param {string} message
 * @param {"success"|"error"|"info"} type
 * @param {number} durationMs
 */
function showToast(message, type = "success", durationMs = 3500) {
    const toast = document.createElement("div");
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    elToastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("toast--exit");
        toast.addEventListener("animationend", () => toast.remove());
    }, durationMs);
}

// ═════════════════════════════════════════════════════════
// Data fetching
// ═════════════════════════════════════════════════════════

/**
 * Fetch dashboard data and re-render.
 */
async function fetchDashboard() {
    try {
        const res = await fetch(
            `${API_BASE}/dashboard/${encodeURIComponent(MACHINE_CODE)}?_t=${Date.now()}`,
            { headers: authHeaders() }
        );

        if (!res.ok) {
            throw new Error(`Server responded with ${res.status}`);
        }

        const data = await res.json();
        renderDashboard(data);
    } catch (err) {
        console.error("[Dashboard] Fetch failed:", err);
        showToast(`Failed to load dashboard: ${err.message}`, "error");
    }
}

// ═════════════════════════════════════════════════════════
// Rendering
// ═════════════════════════════════════════════════════════

/**
 * Render the full dashboard from API data.
 * @param {object} data
 */
function renderDashboard(data) {
    // Header
    elMachineCode.textContent = data.hardware_code || MACHINE_CODE;
    elZoneName.textContent = data.zone_name || "Unknown Zone";

    // Capacity bar
    const current = data.current_capacity ?? 0;
    const max = data.max_capacity ?? 1;
    const pct = max > 0 ? Math.min((current / max) * 100, 100) : 0;

    elCapacityCount.textContent = `${current} / ${max}`;
    elCapacityFill.style.width = `${pct.toFixed(1)}%`;

    // Applicator cards
    const applicators = data.applicators || [];
    elEmptyState.hidden = applicators.length > 0;
    elCardGrid.innerHTML = "";

    applicators.forEach((app) => {
        elCardGrid.appendChild(createCard(app));
    });
}

/**
 * Build a single applicator card element.
 * @param {object} app
 * @returns {HTMLElement}
 */
function createCard(app) {
    const card = document.createElement("div");
    card.className = "card";

    const stateKey = (app.state || "on_rack").toLowerCase().replace(/\s+/g, "_");
    const isInUse = stateKey === "in_use";
    const badgeClass = isInUse ? "badge--in-use" : "badge--on-rack";
    const badgeLabel = isInUse ? "In Use" : "On Rack";

    const toggleTarget = isInUse ? "on_rack" : "in_use";
    const toggleLabel = isInUse ? "Return to Rack" : "Put In Use";
    const toggleClass = isInUse ? "card__toggle--to-rack" : "card__toggle--to-use";

    card.innerHTML = `
        <div class="card__header">
            <div>
                <div class="card__serial">${escapeHtml(app.serial_number || "—")}</div>
                <div class="card__id">ID ${app.id}</div>
            </div>
            <span class="badge ${badgeClass}">${badgeLabel}</span>
        </div>
        <button class="card__toggle ${toggleClass}"
                data-id="${app.id}"
                data-target="${toggleTarget}">
            ${toggleLabel}
        </button>
    `;

    const btn = card.querySelector(".card__toggle");
    btn.addEventListener("click", () => handleToggle(app.id, toggleTarget, btn));

    return card;
}

/**
 * Simple HTML escaper.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

// ═════════════════════════════════════════════════════════
// State toggle
// ═════════════════════════════════════════════════════════

/**
 * Toggle an applicator's state via PATCH.
 * @param {number|string} applicatorId
 * @param {string} newState
 * @param {HTMLButtonElement} btn
 */
async function handleToggle(applicatorId, newState, btn) {
    btn.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/applicators/${applicatorId}/state`, {
            method: "PATCH",
            headers: authHeaders(),
            body: JSON.stringify({ new_state: newState }),
        });

        if (!res.ok) {
            const errBody = await res.json().catch(() => ({}));
            throw new Error(errBody.detail || `Status ${res.status}`);
        }

        const label = newState === "in_use" ? "In Use" : "On Rack";
        showToast(`Applicator set to ${label}`, "success");

        // Refresh immediately to reflect the change
        await fetchDashboard();
    } catch (err) {
        console.error("[Toggle] Error:", err);
        showToast(`Toggle failed: ${err.message}`, "error");
        btn.disabled = false;
    }
}

// ═════════════════════════════════════════════════════════
// HID Barcode Scanner
// ═════════════════════════════════════════════════════════

(() => {
    let buffer = "";
    let firstKeyTime = 0;

    /**
     * HID scanners emit rapid keydown events followed by Enter.
     * We buffer characters and check timing to distinguish scanner
     * input from manual typing.
     */
    document.addEventListener("keydown", (e) => {
        // Ignore keystrokes typed into form fields — only the global
        // HID scanner stream should feed this buffer.
        const tag = e.target.tagName;
        if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") {
            return;
        }

        const now = performance.now();

        if (e.key === "Enter") {
            const elapsed = now - firstKeyTime;

            // Scanner heuristic: full barcode arrives in < 100 ms
            if (buffer.length > 0 && elapsed < 100) {
                handleScan(buffer);
            }

            buffer = "";
            firstKeyTime = 0;
            return;
        }

        // Only collect printable single characters
        if (e.key.length === 1) {
            if (buffer.length === 0) {
                firstKeyTime = now;
            }
            buffer += e.key;
        }
    });

    if (elManualScanBtn) {
        elManualScanBtn.addEventListener("click", () => {
            const val = elManualScanInput.value.trim();
            if (val) {
                handleScan(val);
                elManualScanInput.value = "";
            }
        });
        elManualScanInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                const val = elManualScanInput.value.trim();
                if (val) {
                    handleScan(val);
                    elManualScanInput.value = "";
                }
                // Stop the global scanner listener from firing
                e.stopPropagation();
            }
        });
    }
})();

/**
 * Submit scanned barcode to the backend.
 * @param {string} serialNumber
 */
async function handleScan(serialNumber) {
    showToast(`Scanned: ${serialNumber}`, "info");

    try {
        const res = await fetch(`${API_BASE}/scan`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({
                serial_number: serialNumber,
                hardware_code: MACHINE_CODE,
            }),
        });

        if (!res.ok) {
            const errBody = await res.json().catch(() => ({}));
            throw new Error(errBody.detail || `Status ${res.status}`);
        }

        const body = await res.json();
        if (body.warning) {
            showToast(body.warning, "info");
        }
        showToast("Аплікатор успішно прикріплено", "success");
        await fetchDashboard();
    } catch (err) {
        console.error("[Scan] Error:", err);
        showToast(`Scan failed: ${err.message}`, "error");
    }
}

// ═════════════════════════════════════════════════════════
// Auto-refresh
// ═════════════════════════════════════════════════════════

function startAutoRefresh(intervalMs = 5000) {
    stopAutoRefresh();
    refreshTimer = setInterval(fetchDashboard, intervalMs);
}

function stopAutoRefresh() {
    if (refreshTimer !== null) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

// ═════════════════════════════════════════════════════════
// Initialise
// ═════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
    elMachineCode.textContent = MACHINE_CODE;
    fetchDashboard();
    startAutoRefresh();
});
