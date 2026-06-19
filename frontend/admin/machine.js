const API_BASE = "/api";
const TOKEN = localStorage.getItem("access_token");

const urlParams = new URLSearchParams(window.location.search);
const MACHINE_CODE = urlParams.get("machine");

if (!TOKEN) window.location.href = "/";
if (!MACHINE_CODE) window.location.href = "/admin/";

const els = {
    machineTitle: document.getElementById("machineTitle"),
    zoneName: document.getElementById("zoneName"),
    capacityCount: document.getElementById("capacityCount"),
    capacityFill: document.getElementById("capacityFill"),
    cardGrid: document.getElementById("cardGrid"),
    emptyState: document.getElementById("emptyState"),
    toastContainer: document.getElementById("toastContainer"),
    deleteMachineBtn: document.getElementById("deleteMachineBtn"),
    addApplicatorBtn: document.getElementById("addApplicatorBtn"),
    submitAddBtn: document.getElementById("submitAddBtn"),
};

let dashboardData = null;

function authHeaders() {
    return { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" };
}

function showToast(msg, isError = false) {
    const t = document.createElement("div");
    t.className = "toast";
    if (isError) t.style.background = "#dc2626";
    t.textContent = msg;
    els.toastContainer.appendChild(t);
    setTimeout(() => t.remove(), 3000);
}

async function loadDashboard() {
    try {
        const res = await fetch(`${API_BASE}/dashboard/${encodeURIComponent(MACHINE_CODE)}`, {
            headers: authHeaders(),
        });
        if (res.status === 401 || res.status === 403) {
            window.location.href = "/";
            return;
        }
        if (!res.ok) throw new Error("Машину не знайдено");
        dashboardData = await res.json();
        render(dashboardData);
    } catch (e) {
        showToast(e.message, true);
    }
}

function render(data) {
    els.machineTitle.textContent = data.hardware_code;
    els.zoneName.textContent = data.zone_name;

    const current = data.current_capacity ?? 0;
    const max = data.max_capacity ?? 1;
    const pct = max > 0 ? Math.min((current / max) * 100, 100) : 0;

    els.capacityCount.textContent = `${current} / ${max}`;
    els.capacityFill.style.width = `${pct}%`;

    const apps = data.applicators || [];
    els.cardGrid.innerHTML = "";

    for (let i = 0; i < max; i++) {
        if (i < apps.length) {
            els.cardGrid.appendChild(createAppCard(apps[i]));
        } else {
            const slot = document.createElement("div");
            slot.className = "empty-slot";
            slot.textContent = "Вільне місце";
            els.cardGrid.appendChild(slot);
        }
    }

    els.emptyState.hidden = apps.length > 0 || max > 0;
}

function createAppCard(app) {
    const card = document.createElement("div");
    card.className = "app-card";

    const stateKey = (app.state || "none").toLowerCase();
    const stateLabels = { in_use: "В пресі", on_rack: "На стійці", none: "Немає" };
    const toggleTarget = stateKey === "in_use" ? "on_rack" : "in_use";
    const toggleLabel = stateKey === "in_use" ? "На стійку" : "В прес";

    const header = document.createElement("div");
    header.className = "app-card__header";

    const info = document.createElement("div");
    const serial = document.createElement("div");
    serial.className = "app-card__serial";
    serial.textContent = app.serial_number;
    const idEl = document.createElement("div");
    idEl.className = "app-card__id";
    idEl.textContent = `ID ${app.id}`;
    info.appendChild(serial);
    info.appendChild(idEl);

    const badge = document.createElement("span");
    badge.className = `status status--${stateKey}`;
    badge.textContent = (stateLabels[stateKey] || stateKey).toUpperCase();

    header.appendChild(info);
    header.appendChild(badge);

    const actions = document.createElement("div");
    actions.className = "app-card__actions";

    if (stateKey !== "none") {
        const btnToggle = document.createElement("button");
        btnToggle.className = "btn btn-outline";
        btnToggle.textContent = toggleLabel;
        btnToggle.onclick = () => toggleState(app.id, toggleTarget);
        actions.appendChild(btnToggle);
    }

    const btnUnbind = document.createElement("button");
    btnUnbind.className = "btn btn-outline";
    btnUnbind.textContent = "Зняти з машини";
    btnUnbind.onclick = () => unbindApplicator(app.id);
    actions.appendChild(btnUnbind);

    const btnDelete = document.createElement("button");
    btnDelete.className = "btn btn-danger";
    btnDelete.textContent = "Видалити";
    btnDelete.onclick = () => deleteApplicator(app.id);
    actions.appendChild(btnDelete);

    card.appendChild(header);
    card.appendChild(actions);
    return card;
}

async function toggleState(id, newState) {
    try {
        const res = await fetch(`${API_BASE}/applicators/${id}/state`, {
            method: "PATCH",
            headers: authHeaders(),
            body: JSON.stringify({ new_state: newState }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Помилка");
        }
        showToast("Стан оновлено");
        loadDashboard();
    } catch (e) {
        showToast(e.message, true);
    }
}

async function unbindApplicator(id) {
    if (!confirm("Зняти аплікатор з машини? Він повернеться у Service (статус скинеться).")) return;
    try {
        const res = await fetch(`${API_BASE}/applicators/${id}/unbind`, {
            method: "POST",
            headers: authHeaders(),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Не вдалося зняти");
        }
        showToast("Аплікатор знято з машини");
        loadDashboard();
    } catch (e) {
        showToast(e.message, true);
    }
}

async function deleteApplicator(id) {
    if (!confirm("Видалити цей аплікатор?")) return;
    try {
        const res = await fetch(`${API_BASE}/applicators/${id}`, {
            method: "DELETE",
            headers: authHeaders(),
        });
        if (!res.ok) throw new Error("Не вдалося видалити");
        showToast("Аплікатор видалено");
        loadDashboard();
    } catch (e) {
        showToast(e.message, true);
    }
}

async function deleteMachine() {
    if (!dashboardData) return;
    const count = (dashboardData.applicators || []).length;
    const extra = count > 0 ? ` На машині ${count} аплікатор(ів) — вони будуть відв'язані.` : "";
    if (!confirm(`Видалити машину ${dashboardData.hardware_code}?${extra}`)) return;
    try {
        const res = await fetch(`${API_BASE}/machines/${dashboardData.machine_id}`, {
            method: "DELETE",
            headers: authHeaders(),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Не вдалося видалити машину");
        }
        showToast("Машину видалено");
        setTimeout(() => { window.location.href = "/admin/"; }, 800);
    } catch (e) {
        showToast(e.message, true);
    }
}

function openModal() {
    document.getElementById("addModal").style.display = "flex";
    document.getElementById("newSerial").value = "";
    document.getElementById("newSerial").focus();
}

function closeModal() {
    document.getElementById("addModal").style.display = "none";
}

async function submitAdd() {
    const serial = document.getElementById("newSerial").value.trim();
    const state = document.getElementById("newState").value;
    if (!serial) return showToast("Введіть серійний номер", true);
    if (!dashboardData) return;

    try {
        const res = await fetch(`${API_BASE}/applicators`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({
                serial_number: serial,
                machine_id: dashboardData.machine_id,
                state: state,
            }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Помилка додавання");
        }
        showToast("Аплікатор додано");
        closeModal();
        loadDashboard();
    } catch (e) {
        showToast(e.message, true);
    }
}

els.deleteMachineBtn.addEventListener("click", deleteMachine);
els.addApplicatorBtn.addEventListener("click", openModal);
els.submitAddBtn.addEventListener("click", submitAdd);

window.onclick = (e) => {
    if (e.target.classList.contains("modal")) closeModal();
};

loadDashboard();
setInterval(loadDashboard, 4000);
