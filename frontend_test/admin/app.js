const API_BASE = "/api/v1";

// ── Auth guard (admin only) ──────────────────────────────
const TOKEN = localStorage.getItem("token");
const ROLE  = localStorage.getItem("role");
if (!TOKEN || ROLE !== "tech_admin") {
    window.location.replace("/");
}

function authHeaders(extra) {
    return { "Content-Type": "application/json", Authorization: `Bearer ${TOKEN}`, ...extra };
}

function authFetch(url, opts) {
    return fetch(url, { ...opts, headers: { ...authHeaders(), ...(opts && opts.headers) } });
}

const els = {
    kpiTotal: document.getElementById('kpiTotal'),
    kpiInUse: document.getElementById('kpiInUse'),
    kpiOnRack: document.getElementById('kpiOnRack'),
    kpiFull: document.getElementById('kpiFull'),
    zoneGrid: document.getElementById('zoneGrid'),
    machineGrid: document.getElementById('machineGrid'),
    applicatorTableBody: document.getElementById('applicatorTableBody'),
    searchInput: document.getElementById('searchInput'),
    refreshBtn: document.getElementById('refreshBtn'),
    clock: document.getElementById('clock'),
    toastContainer: document.getElementById('toastContainer')
};

let allApplicators = [];
let allMachines = [];
let refreshTimer;

// Utilities
function escapeHtml(str) {
    const div = document.createElement('div');
    div.innerText = str;
    return div.innerHTML;
}

function updateClock() {
    els.clock.textContent = new Date().toLocaleTimeString();
}
setInterval(updateClock, 1000);
updateClock();

function showToast(msg) {
    const t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    els.toastContainer.appendChild(t);
    setTimeout(() => t.remove(), 3000);
}

// Data Fetching
async function fetchData() {
    try {
        els.refreshBtn.textContent = 'Loading...';
        els.refreshBtn.disabled = true;

        // 1. Fetch machine list dynamically
        const machinesRes = await authFetch(`${API_BASE}/machines?_t=${Date.now()}`);
        if (!machinesRes.ok) throw new Error("Failed to fetch machines");
        const machinesList = await machinesRes.json();

        // 2. Fetch dashboard details for each machine
        const dashboardPromises = machinesList.map(m => authFetch(`${API_BASE}/dashboard/${m.hardware_code}?_t=${Date.now()}`).then(r => r.ok ? r.json() : null));
        const dashboards = (await Promise.all(dashboardPromises)).filter(Boolean);

        allMachines = dashboards;
        allApplicators = [];
        
        let stats = { total: 0, inUse: 0, onRack: 0, fullMachines: 0 };
        const zones = {};

        dashboards.forEach(db => {
            // Stats
            if (db.current_capacity >= db.max_capacity) stats.fullMachines++;
            
            // Collect applicators
            db.applicators.forEach(app => {
                app.machine_code = db.hardware_code;
                app.zone_name = db.zone_name;
                allApplicators.push(app);
                stats.total++;
                if (app.state === 'in_use') stats.inUse++;
                if (app.state === 'on_rack') stats.onRack++;
            });

            // Group by Zone
            if (!zones[db.zone_name]) {
                zones[db.zone_name] = { name: db.zone_name, current: 0, max: 0, machineCount: 0 };
            }
            zones[db.zone_name].current += db.current_capacity;
            zones[db.zone_name].max += db.max_capacity;
            zones[db.zone_name].machineCount++;
        });

        renderKPIs(stats);
        renderZones(Object.values(zones));
        renderMachines(dashboards);
        renderApplicators();

    } catch (e) {
        showToast("Error fetching data: " + e.message);
    } finally {
        els.refreshBtn.textContent = 'Refresh';
        els.refreshBtn.disabled = false;
    }
}

// Rendering
function renderKPIs(stats) {
    els.kpiTotal.textContent = stats.total;
    els.kpiInUse.textContent = stats.inUse;
    els.kpiOnRack.textContent = stats.onRack;
    els.kpiFull.textContent = stats.fullMachines;
}

function renderZones(zones) {
    els.zoneGrid.innerHTML = zones.map(z => {
        const pct = z.max > 0 ? (z.current / z.max) * 100 : 0;
        return `
        <div class="zone-card">
            <div class="zone-card__title">${escapeHtml(z.name)}</div>
            <div style="color: var(--text-light); font-size: 0.875rem">Machines: ${z.machineCount}</div>
            <div style="margin-top: 12px; display: flex; justify-content: space-between; font-size: 0.875rem;">
                <span>Capacity</span>
                <strong>${z.current}/${z.max}</strong>
            </div>
            <div class="bar-wrap"><div class="bar-fill" style="width: ${pct}%"></div></div>
        </div>`;
    }).join('');
}

function renderMachines(machines) {
    els.machineGrid.innerHTML = machines.map(m => {
        const pct = m.max_capacity > 0 ? (m.current_capacity / m.max_capacity) * 100 : 0;
        return `
        <div class="machine-card">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <div class="machine-card__title">${escapeHtml(m.hardware_code)}</div>
                    <div style="color: var(--text-light); font-size: 0.875rem">Zone: ${escapeHtml(m.zone_name)}</div>
                </div>
                <button class="btn" style="padding: 4px 8px; font-size: 0.75rem; border: 1px solid #ff4d4f; color: #ff4d4f; background: transparent;" onclick="deleteMachine(${m.id})">Delete</button>
            </div>
            <div style="margin-top: 12px; display: flex; justify-content: space-between; font-size: 0.875rem;">
                <span>Capacity</span>
                <strong>${m.current_capacity}/${m.max_capacity}</strong>
            </div>
            <div class="bar-wrap"><div class="bar-fill" style="width: ${pct}%"></div></div>
        </div>`;
    }).join('');
}

function renderApplicators() {
    const query = els.searchInput.value.toLowerCase();
    const filtered = allApplicators.filter(a => a.serial_number.toLowerCase().includes(query));

    els.applicatorTableBody.innerHTML = filtered.map(app => {
        let actionTarget = 'on_rack';
        let actionLabel = 'Put on Rack';
        if (app.state === 'in_use') {
            actionTarget = 'on_rack';
            actionLabel = 'Move to Rack';
        } else if (app.state === 'on_rack') {
            actionTarget = 'in_use';
            actionLabel = 'Put in Use';
        }

        return `
        <tr>
            <td>${app.id}</td>
            <td><strong>${escapeHtml(app.serial_number)}</strong></td>
            <td>${escapeHtml(app.machine_code)}</td>
            <td>${escapeHtml(app.zone_name)}</td>
            <td><span class="status status--${app.state}">${app.state.replace('_', ' ').toUpperCase()}</span></td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <button class="btn" style="border: 1px solid var(--border); padding: 4px 8px; font-size: 0.75rem;" 
                            onclick="toggleState(${app.id}, '${actionTarget}')">
                        ${actionLabel}
                    </button>
                    <button class="btn" style="border: 1px solid #ff4d4f; color: #ff4d4f; padding: 4px 8px; font-size: 0.75rem; background: transparent;" 
                            onclick="deleteApplicator(${app.id})">
                        Delete
                    </button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

// Actions
async function toggleState(id, newState) {
    try {
        const res = await authFetch(`${API_BASE}/applicators/${id}/state`, {
            method: 'PATCH',
            body: JSON.stringify({ new_state: newState })
        });
        if (!res.ok) {
            const err = await res.json().catch(()=>({}));
            throw new Error(err.detail || 'Failed');
        }
        showToast("State updated successfully");
        fetchData();
    } catch (e) {
        showToast("Error updating state: " + e.message);
    }
}

async function deleteApplicator(id) {
    if (!confirm("Are you sure you want to delete this applicator?")) return;
    try {
        const res = await authFetch(`${API_BASE}/applicators/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error("Failed to delete applicator");
        showToast("Applicator deleted");
        fetchData();
    } catch (e) { showToast(e.message); }
}

async function deleteMachine(id) {
    if (!confirm("Are you sure you want to delete this machine? This might fail if applicators are attached.")) return;
    try {
        const res = await authFetch(`${API_BASE}/machines/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error("Failed to delete machine. Remove attached applicators first.");
        showToast("Machine deleted");
        fetchData();
    } catch (e) { showToast(e.message); }
}

// Events
els.refreshBtn.addEventListener('click', fetchData);
els.searchInput.addEventListener('input', renderApplicators);

// Modals
async function openMachineModal() {
    document.getElementById('machineModal').style.display = 'flex';
    try {
        const res = await authFetch(`${API_BASE}/zones`);
        if (res.ok) {
            const zones = await res.json();
            const select = document.getElementById('newMachineZone');
            select.innerHTML = '<option value="">Select a zone...</option>';
            zones.forEach(z => {
                select.innerHTML += `<option value="${z.id}">${z.name}</option>`;
            });
        }
    } catch (e) { console.error("Failed to load zones"); }
}
function openApplicatorModal() {
    document.getElementById('applicatorModal').style.display = 'flex';
}
function closeModals() {
    document.getElementById('machineModal').style.display = 'none';
    document.getElementById('applicatorModal').style.display = 'none';
}

// Close modals when clicking outside
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        closeModals();
    }
}

async function submitMachine() {
    const code = document.getElementById('newMachineCode').value;
    const zoneId = parseInt(document.getElementById('newMachineZone').value);
    if (!code || isNaN(zoneId)) return showToast("Please fill all fields and select a zone.");

    try {
        const res = await authFetch(`${API_BASE}/machines`, {
            method: 'POST',
            body: JSON.stringify({ hardware_code: code, zone_id: zoneId })
        });
        if (!res.ok) {
            const err = await res.json().catch(()=>({}));
            throw new Error(err.detail || 'Failed');
        }
        showToast("Machine added successfully");
        closeModals();
        fetchData();
    } catch (e) {
        showToast("Error adding machine: " + e.message);
    }
}

async function submitApplicator() {
    const serial = document.getElementById('newAppSerial').value;
    const mIdRaw = document.getElementById('newAppMachine').value;
    const mId = mIdRaw ? parseInt(mIdRaw) : null;
    const state = document.getElementById('newAppState').value;
    if (!serial) return showToast("Please enter serial number.");

    try {
        const res = await authFetch(`${API_BASE}/applicators`, {
            method: 'POST',
            body: JSON.stringify({ serial_number: serial, machine_id: mId, state: state })
        });
        if (!res.ok) {
            const err = await res.json().catch(()=>({}));
            throw new Error(err.detail || 'Failed');
        }
        showToast("Applicator added successfully");
        closeModals();
        fetchData();
    } catch (e) {
        showToast("Error adding applicator: " + e.message);
    }
}

// Init
fetchData();
refreshTimer = setInterval(fetchData, 10000);
