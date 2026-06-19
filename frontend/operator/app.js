const API_BASE = "/api";
const WS_PROTOCOL = window.location.protocol === "https:" ? "wss" : "ws";
const WS_BASE = `${WS_PROTOCOL}://${window.location.host}/api/ws`;

const urlParams = new URLSearchParams(window.location.search);
const MACHINE_CODE = urlParams.get("machine") || localStorage.getItem("operator_machine");

const TOKEN = localStorage.getItem("access_token");
if (!TOKEN) window.location.href = "/";
if (!MACHINE_CODE) window.location.href = "/";

function parseJwt(token) {
    try {
        const base64Url = token.split(".")[1];
        const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
        const jsonPayload = decodeURIComponent(
            window.atob(base64).split("").map((c) =>
                "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2)
            ).join("")
        );
        return JSON.parse(jsonPayload);
    } catch {
        return null;
    }
}

const payload = parseJwt(TOKEN);
const role = payload?.role?.toUpperCase() || "";
if (role === "TECH_ADMIN" || role === "SHIFT_LEADER") {
    window.location.href = "/admin/";
}

const elMachineCode = document.getElementById("machineCode");
const elZoneName = document.getElementById("zoneName");
const elCapacityCount = document.getElementById("capacityCount");
const elCapacityFill = document.getElementById("capacityFill");
const elCardGrid = document.getElementById("cardGrid");
const elEmptyState = document.getElementById("emptyState");
const elToastContainer = document.getElementById("toastContainer");
const elManualScanInput = document.getElementById("manualScanInput");
const elManualScanBtn = document.getElementById("manualScanBtn");
const elLogoutBtn = document.getElementById("logoutBtn");

let ws = null;

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

function formatError(detail) {
    if (!detail) return "Невідома помилка";
    const msg = String(detail);
    if (msg.includes("not found") && msg.includes("Must be explicitly created")) {
        return "Аплікатор не зареєстровано. Попросіть адміна додати серійний номер.";
    }
    if (msg.includes("not attached to any zone")) {
        return "Аплікатор не прив'язано до зони. Зверніться до адміна.";
    }
    if (msg.includes("already bound")) {
        return "Аплікатор вже на іншій машині. Спочатку зніміть його в Service.";
    }
    if (msg.includes("in_use limit")) {
        return "Досягнуто ліміт активних аплікаторів у зоні. Спершу зніміть інший з преса.";
    }
    return msg;
}

async function fetchDashboard() {
    try {
        const res = await fetch(`${API_BASE}/dashboard/${encodeURIComponent(MACHINE_CODE)}`, {
            headers: { Authorization: `Bearer ${TOKEN}` },
        });
        if (res.ok) {
            renderDashboard(await res.json());
        }
    } catch {
        /* ignore polling errors */
    }
}

function initWebSocket() {
    if (ws) ws.close();
    const wsUrl = `${WS_BASE}/dashboard/${encodeURIComponent(MACHINE_CODE)}?token=${encodeURIComponent(TOKEN)}`;
    ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        renderDashboard(data);
    };
    ws.onerror = () => console.error("WebSocket error");
    ws.onclose = () => setTimeout(initWebSocket, 5000);
}

function renderDashboard(data) {
    elMachineCode.textContent = data.hardware_code || MACHINE_CODE;
    elZoneName.textContent = data.zone_name || "Невідома зона";

    const current = data.current_capacity ?? 0;
    const max = data.max_capacity ?? 1;
    const pct = max > 0 ? Math.min((current / max) * 100, 100) : 0;

    elCapacityCount.textContent = `${current} / ${max}`;
    elCapacityFill.style.width = `${pct.toFixed(1)}%`;

    const applicators = data.applicators || [];
    elEmptyState.hidden = max > 0;
    elCardGrid.innerHTML = "";

    for (let i = 0; i < max; i++) {
        if (i < applicators.length) {
            elCardGrid.appendChild(createCard(applicators[i]));
        } else {
            elCardGrid.appendChild(createEmptySlot());
        }
    }
}

function createEmptySlot() {
    const card = document.createElement("div");
    card.className = "card";
    card.style.backgroundColor = "transparent";
    card.style.border = "2px dashed var(--text-light)";
    card.style.boxShadow = "none";
    card.style.opacity = "0.6";
    const text = document.createElement("div");
    text.textContent = "Вільне місце";
    text.style.textAlign = "center";
    text.style.padding = "20px";
    card.appendChild(text);
    return card;
}

function createCard(app) {
    const card = document.createElement("div");
    card.className = "card";

    const stateKey = (app.state || "on_rack").toLowerCase().replace(/\s+/g, "_");
    const isInUse = stateKey === "in_use";
    const badgeLabel = isInUse ? "В пресі" : "На стійці";
    const toggleTarget = isInUse ? "on_rack" : "in_use";
    const toggleLabel = isInUse ? "На стійку" : "В прес";

    const header = document.createElement("div");
    header.className = "card__header";

    const info = document.createElement("div");
    const serial = document.createElement("div");
    serial.className = "card__serial";
    serial.textContent = app.serial_number || "—";
    const idElem = document.createElement("div");
    idElem.className = "card__id";
    idElem.textContent = `ID ${app.id}`;

    info.appendChild(serial);
    info.appendChild(idElem);

    const badge = document.createElement("span");
    badge.className = `status status--${stateKey}`;
    badge.textContent = badgeLabel;

    header.appendChild(info);
    header.appendChild(badge);

    const btn = document.createElement("button");
    btn.className = "btn btn-outline";
    btn.style.marginTop = "16px";
    btn.style.width = "100%";
    btn.textContent = toggleLabel;
    btn.addEventListener("click", () => handleToggle(app.id, toggleTarget, btn));

    const unbindBtn = document.createElement("button");
    unbindBtn.className = "btn btn-outline";
    unbindBtn.style.marginTop = "8px";
    unbindBtn.style.width = "100%";
    unbindBtn.textContent = "Зняти з машини";
    unbindBtn.addEventListener("click", () => handleUnbind(app.id, unbindBtn));

    card.appendChild(header);
    card.appendChild(btn);
    card.appendChild(unbindBtn);
    return card;
}

async function handleUnbind(applicatorId, btn) {
    if (!confirm("Зняти аплікатор з машини? Він повернеться у Service.")) return;
    btn.disabled = true;
    try {
        const res = await fetch(`${API_BASE}/applicators/${applicatorId}/unbind`, {
            method: "POST",
            headers: { Authorization: `Bearer ${TOKEN}` },
        });
        if (!res.ok) {
            const errBody = await res.json().catch(() => ({}));
            throw new Error(formatError(errBody.detail) || `Помилка ${res.status}`);
        }
        showToast("Аплікатор знято з машини", "success");
        await fetchDashboard();
    } catch (err) {
        showToast(`Помилка: ${err.message}`, "error");
        btn.disabled = false;
    }
}

async function handleToggle(applicatorId, newState, btn) {
    btn.disabled = true;
    try {
        const res = await fetch(`${API_BASE}/applicators/${applicatorId}/state`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${TOKEN}`,
            },
            body: JSON.stringify({ new_state: newState }),
        });
        if (!res.ok) {
            const errBody = await res.json().catch(() => ({}));
            throw new Error(formatError(errBody.detail) || `Помилка ${res.status}`);
        }
        const label = newState === "in_use" ? "В пресі" : "На стійці";
        showToast(`Стан: ${label}`, "success");
        await fetchDashboard();
    } catch (err) {
        showToast(`Помилка: ${err.message}`, "error");
        btn.disabled = false;
    }
}

(() => {
    let buffer = "";
    let firstKeyTime = 0;

    document.addEventListener("keydown", (e) => {
        if (document.activeElement === elManualScanInput) return;

        const now = performance.now();
        if (e.key === "Enter") {
            const elapsed = now - firstKeyTime;
            if (buffer.length > 0 && elapsed < 500) {
                handleScan(buffer);
            }
            buffer = "";
            firstKeyTime = 0;
            return;
        }
        if (e.key.length === 1) {
            if (buffer.length === 0) firstKeyTime = now;
            buffer += e.key;
        }
    });

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
            e.stopPropagation();
        }
    });
})();

async function handleScan(serialNumber) {
    showToast(`Сканування: ${serialNumber}`, "info");
    try {
        const res = await fetch(`${API_BASE}/scan`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${TOKEN}`,
            },
            body: JSON.stringify({
                serial_number: serialNumber,
                hardware_code: MACHINE_CODE,
            }),
        });
        if (!res.ok) {
            const errBody = await res.json().catch(() => ({}));
            throw new Error(formatError(errBody.detail) || `Помилка ${res.status}`);
        }
        showToast("Сканування успішне", "success");
        await fetchDashboard();
    } catch (err) {
        showToast(`Помилка: ${err.message}`, "error");
    }
}

elLogoutBtn.addEventListener("click", () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("operator_machine");
    window.location.href = "/";
});

document.addEventListener("DOMContentLoaded", () => {
    elMachineCode.textContent = MACHINE_CODE;
    localStorage.setItem("operator_machine", MACHINE_CODE);
    fetchDashboard();
    initWebSocket();
    setInterval(fetchDashboard, 4000);
});
