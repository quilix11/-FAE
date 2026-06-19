const API_BASE = "/api";

const TOKEN = localStorage.getItem("access_token");
if (!TOKEN) {
    window.location.href = "/";
}

function authHeaders() {
    return {
        "Authorization": `Bearer ${TOKEN}`,
        "Content-Type": "application/json"
    };
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

        const machinesRes = await fetch(`${API_BASE}/machines?_t=${Date.now()}`, {
            headers: authHeaders()
        });
        if (!machinesRes.ok) throw new Error("Failed to fetch machines");
        const machinesList = await machinesRes.json();

        const dashboardPromises = machinesList.map(m => fetch(`${API_BASE}/dashboard/${m.hardware_code}?_t=${Date.now()}`, { headers: authHeaders() }).then(r => r.ok ? r.json() : null));
        const dashboards = (await Promise.all(dashboardPromises)).filter(Boolean);

        allMachines = dashboards;

        let stats = { total: 0, inUse: 0, onRack: 0, fullMachines: 0 };
        const zones = {};

        dashboards.forEach(db => {
            if (db.current_capacity >= db.max_capacity) stats.fullMachines++;

            if (!zones[db.zone_name]) {
                zones[db.zone_name] = { name: db.zone_name, current: 0, max: 0, machineCount: 0 };
            }
            zones[db.zone_name].current += db.current_capacity;
            zones[db.zone_name].max += db.max_capacity;
            zones[db.zone_name].machineCount++;
        });

        // Full inventory (includes unattached + blocked applicators, which are not on any machine dashboard)
        const appsRes = await fetch(`${API_BASE}/applicators?_t=${Date.now()}`, { headers: authHeaders() });
        allApplicators = appsRes.ok ? await appsRes.json() : [];
        stats.total = allApplicators.length;
        stats.inUse = allApplicators.filter(a => a.state === 'in_use').length;
        stats.onRack = allApplicators.filter(a => a.state === 'on_rack').length;

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
    els.zoneGrid.innerHTML = '';
    zones.forEach(z => {
        const pct = z.max > 0 ? (z.current / z.max) * 100 : 0;
        
        const card = document.createElement('div');
        card.className = 'zone-card';

        const title = document.createElement('div');
        title.className = 'zone-card__title';
        title.textContent = z.name;

        const subtitle = document.createElement('div');
        subtitle.style.color = 'var(--text-light)';
        subtitle.style.fontSize = '0.875rem';
        subtitle.textContent = `Machines: ${z.machineCount}`;

        const flex = document.createElement('div');
        flex.style.marginTop = '12px';
        flex.style.display = 'flex';
        flex.style.justifyContent = 'space-between';
        flex.style.fontSize = '0.875rem';
        
        const span = document.createElement('span');
        span.textContent = 'Capacity';
        const strong = document.createElement('strong');
        strong.textContent = `${z.current}/${z.max}`;
        flex.appendChild(span);
        flex.appendChild(strong);

        const barWrap = document.createElement('div');
        barWrap.className = 'bar-wrap';
        const barFill = document.createElement('div');
        barFill.className = 'bar-fill';
        barFill.style.width = `${pct}%`;
        barWrap.appendChild(barFill);

        card.appendChild(title);
        card.appendChild(subtitle);
        card.appendChild(flex);
        card.appendChild(barWrap);
        
        els.zoneGrid.appendChild(card);
    });
}

function renderMachines(machines) {
    els.machineGrid.innerHTML = '';
    machines.forEach(m => {
        const pct = m.max_capacity > 0 ? (m.current_capacity / m.max_capacity) * 100 : 0;
        
        const card = document.createElement('div');
        card.className = 'machine-card';

        const headerFlex = document.createElement('div');
        headerFlex.style.display = 'flex';
        headerFlex.style.justifyContent = 'space-between';
        headerFlex.style.alignItems = 'start';

        const infoDiv = document.createElement('div');
        const title = document.createElement('div');
        title.className = 'machine-card__title';
        title.textContent = m.hardware_code;
        const subtitle = document.createElement('div');
        subtitle.style.color = 'var(--text-light)';
        subtitle.style.fontSize = '0.875rem';
        subtitle.textContent = `Zone: ${m.zone_name}`;
        
        infoDiv.appendChild(title);
        infoDiv.appendChild(subtitle);

        const btn = document.createElement('button');
        btn.className = 'btn';
        btn.style.padding = '4px 8px';
        btn.style.fontSize = '0.75rem';
        btn.style.border = 'none';
        btn.style.color = '#EE5D50';
        btn.style.background = '#FCE8E6';
        btn.textContent = 'Delete';
        btn.onclick = () => deleteMachine(m.id);

        headerFlex.appendChild(infoDiv);
        headerFlex.appendChild(btn);

        const capFlex = document.createElement('div');
        capFlex.style.marginTop = '12px';
        capFlex.style.display = 'flex';
        capFlex.style.justifyContent = 'space-between';
        capFlex.style.fontSize = '0.875rem';

        const span = document.createElement('span');
        span.textContent = 'Capacity';
        const strong = document.createElement('strong');
        strong.textContent = `${m.current_capacity}/${m.max_capacity}`;
        
        capFlex.appendChild(span);
        capFlex.appendChild(strong);

        const barWrap = document.createElement('div');
        barWrap.className = 'bar-wrap';
        const barFill = document.createElement('div');
        barFill.className = 'bar-fill';
        barFill.style.width = `${pct}%`;
        barWrap.appendChild(barFill);

        card.appendChild(headerFlex);
        card.appendChild(capFlex);
        card.appendChild(barWrap);

        // Make card clickable to open machine management
        card.style.cursor = 'pointer';
        card.onclick = (e) => {
            if (e.target.tagName === 'BUTTON') return;
            window.location.href = `/admin/machine.html?machine=${encodeURIComponent(m.hardware_code)}`;
        };

        els.machineGrid.appendChild(card);
    });
}

function renderApplicators() {
    const query = els.searchInput.value.toLowerCase();
    const filtered = allApplicators.filter(a => 
        a.serial_number.toLowerCase().includes(query) || 
        (a.machine_code && a.machine_code.toLowerCase().includes(query)) ||
        (a.zone_name && a.zone_name.toLowerCase().includes(query))
    );

    els.applicatorTableBody.innerHTML = '';
    filtered.forEach(app => {
        let actionTarget = 'on_rack';
        let actionLabel = 'Put on Rack';
        if (app.state === 'in_use') {
            actionTarget = 'on_rack';
            actionLabel = 'Move to Rack';
        } else if (app.state === 'on_rack') {
            actionTarget = 'in_use';
            actionLabel = 'Put in Use';
        }

        const tr = document.createElement('tr');

        const tdId = document.createElement('td');
        tdId.textContent = app.id;

        const tdSerial = document.createElement('td');
        const strongSerial = document.createElement('strong');
        strongSerial.textContent = app.serial_number;
        tdSerial.appendChild(strongSerial);

        const tdMachine = document.createElement('td');
        tdMachine.textContent = app.machine_code || '—';

        const tdZone = document.createElement('td');
        tdZone.textContent = app.zone_name || '—';

        const tdState = document.createElement('td');
        const spanState = document.createElement('span');
        spanState.className = `status status--${app.state}`;
        spanState.textContent = app.state.replace('_', ' ').toUpperCase();
        tdState.appendChild(spanState);

        const tdActions = document.createElement('td');
        const flexActions = document.createElement('div');
        flexActions.style.display = 'flex';
        flexActions.style.gap = '8px';

        const btnState = document.createElement('button');
        btnState.className = 'btn btn-outline';
        btnState.style.padding = '6px 12px';
        btnState.style.fontSize = '0.75rem';
        btnState.textContent = actionLabel;
        btnState.onclick = () => toggleState(app.id, actionTarget);

        const btnUnbind = document.createElement('button');
        btnUnbind.className = 'btn btn-outline';
        btnUnbind.style.padding = '6px 12px';
        btnUnbind.style.fontSize = '0.75rem';
        btnUnbind.textContent = 'Зняти з машини';
        btnUnbind.onclick = () => unbindApplicator(app.id);

        const btnHistory = document.createElement('button');
        btnHistory.className = 'btn btn-outline';
        btnHistory.style.padding = '6px 12px';
        btnHistory.style.fontSize = '0.75rem';
        btnHistory.textContent = 'Історія';
        btnHistory.onclick = () => openApplicatorHistory(app.id, app.serial_number);

        const btnBlock = document.createElement('button');
        btnBlock.className = 'btn';
        btnBlock.style.border = 'none';
        btnBlock.style.color = '#92400e';
        btnBlock.style.background = '#fef3c7';
        btnBlock.style.padding = '6px 12px';
        btnBlock.style.fontSize = '0.75rem';
        btnBlock.textContent = 'Заблокувати';
        btnBlock.onclick = () => blockApplicator(app.id);

        const btnDelete = document.createElement('button');
        btnDelete.className = 'btn';
        btnDelete.style.border = 'none';
        btnDelete.style.color = '#EE5D50';
        btnDelete.style.background = '#FCE8E6';
        btnDelete.style.padding = '6px 12px';
        btnDelete.textContent = 'Delete';
        btnDelete.onclick = () => deleteApplicator(app.id);

        flexActions.appendChild(btnState);
        if (app.machine_code) flexActions.appendChild(btnUnbind);
        flexActions.appendChild(btnHistory);
        flexActions.appendChild(btnBlock);
        flexActions.appendChild(btnDelete);
        tdActions.appendChild(flexActions);

        tr.appendChild(tdId);
        tr.appendChild(tdSerial);
        tr.appendChild(tdMachine);
        tr.appendChild(tdZone);
        tr.appendChild(tdState);
        tr.appendChild(tdActions);

        els.applicatorTableBody.appendChild(tr);
    });
}

// Actions
async function toggleState(id, newState) {
    try {
        const res = await fetch(`${API_BASE}/applicators/${id}/state`, {
            method: 'PATCH',
            headers: authHeaders(),
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

async function blockApplicator(id) {
    const reason = prompt("Причина блокування (напр. брак, поломка):");
    if (reason === null) return;
    if (!reason.trim()) return showToast("Вкажіть причину блокування.");
    try {
        const res = await fetch(`${API_BASE}/applicators/${id}/block`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ reason: reason.trim() })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed');
        }
        showToast("Аплікатор заблоковано");
        fetchData();
        loadBlocked();
    } catch (e) { showToast("Помилка: " + e.message); }
}

async function loadBlocked() {
    try {
        const res = await fetch(`${API_BASE}/applicators/blocked?_t=${Date.now()}`, { headers: authHeaders() });
        if (!res.ok) throw new Error("Failed");
        renderBlocked(await res.json());
    } catch (e) {
        showToast("Не вдалося завантажити заблоковані: " + e.message);
    }
}

function renderBlocked(items) {
    const body = document.getElementById('blockedTableBody');
    body.innerHTML = '';
    if (!items.length) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 6;
        td.style.color = 'var(--text-light)';
        td.textContent = 'Немає заблокованих аплікаторів';
        tr.appendChild(td);
        body.appendChild(tr);
        return;
    }
    items.forEach(it => {
        const tr = document.createElement('tr');
        const tdId = document.createElement('td');
        tdId.textContent = it.id;
        const tdSerial = document.createElement('td');
        const strong = document.createElement('strong');
        strong.textContent = it.serial_number;
        tdSerial.appendChild(strong);
        const tdReason = document.createElement('td');
        tdReason.textContent = it.reason || '—';
        const tdWhen = document.createElement('td');
        tdWhen.textContent = it.blocked_at ? new Date(it.blocked_at).toLocaleString() : '—';
        const tdBy = document.createElement('td');
        tdBy.textContent = it.blocked_by || '—';
        const tdActions = document.createElement('td');
        const btn = document.createElement('button');
        btn.className = 'btn btn-outline';
        btn.style.padding = '6px 12px';
        btn.style.fontSize = '0.75rem';
        btn.textContent = 'Розблокувати';
        btn.onclick = () => unblockApplicator(it.id);
        tdActions.appendChild(btn);
        tr.append(tdId, tdSerial, tdReason, tdWhen, tdBy, tdActions);
        body.appendChild(tr);
    });
}

async function unblockApplicator(id) {
    if (!confirm("Розблокувати аплікатор? Він повернеться у Service.")) return;
    try {
        const res = await fetch(`${API_BASE}/applicators/${id}/unblock`, {
            method: 'POST',
            headers: authHeaders()
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed');
        }
        showToast("Аплікатор розблоковано");
        loadBlocked();
        fetchData();
    } catch (e) { showToast("Помилка: " + e.message); }
}

async function unbindApplicator(id) {
    if (!confirm("Зняти аплікатор з машини? Він повернеться у Service (статус скинеться).")) return;
    try {
        const res = await fetch(`${API_BASE}/applicators/${id}/unbind`, {
            method: 'POST',
            headers: authHeaders()
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed');
        }
        showToast("Аплікатор знято з машини");
        fetchData();
    } catch (e) { showToast("Помилка: " + e.message); }
}

async function deleteApplicator(id) {
    if (!confirm("Are you sure you want to delete this applicator?")) return;
    try {
        const res = await fetch(`${API_BASE}/applicators/${id}`, { 
            method: 'DELETE',
            headers: authHeaders()
        });
        if (!res.ok) throw new Error("Failed to delete applicator");
        showToast("Applicator deleted");
        fetchData();
    } catch (e) { showToast(e.message); }
}

async function deleteMachine(id) {
    if (!confirm("Видалити цю машину? Прив'язані аплікатори будуть відв'язані автоматично.")) return;
    try {
        const res = await fetch(`${API_BASE}/machines/${id}`, {
            method: 'DELETE',
            headers: authHeaders()
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Не вдалося видалити машину");
        }
        showToast("Машину видалено");
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
        const res = await fetch(`${API_BASE}/zones`, { headers: authHeaders() });
        if (res.ok) {
            const zones = await res.json();
            const select = document.getElementById('newMachineZone');
            select.innerHTML = '';
            const defaultOpt = document.createElement('option');
            defaultOpt.value = "";
            defaultOpt.textContent = "Select a zone...";
            select.appendChild(defaultOpt);

            zones.forEach(z => {
                const opt = document.createElement('option');
                opt.value = z.id;
                opt.textContent = z.name;
                select.appendChild(opt);
            });
        }
    } catch (e) { console.error("Failed to load zones"); }
}
async function openApplicatorModal() {
    document.getElementById('applicatorModal').style.display = 'flex';
    const select = document.getElementById('newAppMachine');
    select.innerHTML = '';
    const noneOpt = document.createElement('option');
    noneOpt.value = '';
    noneOpt.textContent = "— Без машини —";
    select.appendChild(noneOpt);
    try {
        const res = await fetch(`${API_BASE}/machines`, { headers: authHeaders() });
        if (res.ok) {
            const machines = await res.json();
            machines.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.id;
                opt.textContent = `${m.hardware_code} (${m.zone_name})`;
                select.appendChild(opt);
            });
        }
    } catch (e) { console.error("Failed to load machines"); }
}
function openUserModal() {
    document.getElementById('newUserName').value = '';
    document.getElementById('newUserPassword').value = '';
    document.getElementById('newUserOperatorCode').value = '';
    document.getElementById('newUserRole').value = 'Operator';
    onUserRoleChange();
    document.getElementById('userModal').style.display = 'flex';
}
function onUserRoleChange() {
    const role = document.getElementById('newUserRole').value;
    // operator_code only applies to operators (they log in by badge code)
    document.getElementById('operatorCodeGroup').style.display = role === 'Operator' ? 'block' : 'none';
}
function closeModals() {
    document.getElementById('machineModal').style.display = 'none';
    document.getElementById('applicatorModal').style.display = 'none';
    document.getElementById('userModal').style.display = 'none';
    document.getElementById('historyModal').style.display = 'none';
}

// History
function fmtTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString();
}

function renderMovementRows(tbody, items, withSerial) {
    tbody.innerHTML = '';
    if (!items.length) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = withSerial ? 5 : 4;
        td.style.color = 'var(--text-light)';
        td.textContent = 'Немає записів';
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }
    items.forEach(m => {
        const tr = document.createElement('tr');
        const cells = [fmtTime(m.timestamp)];
        if (withSerial) cells.push(m.serial_number || '—');
        cells.push(m.from_location, m.to_location, m.user || '—');
        cells.forEach(text => {
            const td = document.createElement('td');
            td.textContent = text;
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

async function loadHistory() {
    try {
        const res = await fetch(`${API_BASE}/movements?limit=100&_t=${Date.now()}`, { headers: authHeaders() });
        if (!res.ok) throw new Error("Failed");
        renderMovementRows(document.getElementById('historyTableBody'), await res.json(), true);
    } catch (e) {
        showToast("Не вдалося завантажити історію: " + e.message);
    }
}

async function openApplicatorHistory(id, serial) {
    document.getElementById('historyModalTitle').textContent = `Історія: ${serial}`;
    const body = document.getElementById('historyModalBody');
    body.innerHTML = '';
    document.getElementById('historyModal').style.display = 'flex';
    try {
        const res = await fetch(`${API_BASE}/applicators/${id}/history?_t=${Date.now()}`, { headers: authHeaders() });
        if (!res.ok) throw new Error("Failed");
        renderMovementRows(body, await res.json(), false);
    } catch (e) {
        showToast("Не вдалося завантажити історію: " + e.message);
    }
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
        const res = await fetch(`${API_BASE}/machines`, {
            method: 'POST',
            headers: authHeaders(),
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
        const res = await fetch(`${API_BASE}/applicators`, {
            method: 'POST',
            headers: authHeaders(),
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

async function submitUser() {
    const username = document.getElementById('newUserName').value.trim();
    const password = document.getElementById('newUserPassword').value;
    const role = document.getElementById('newUserRole').value;
    const operatorCodeRaw = document.getElementById('newUserOperatorCode').value.trim();

    if (!username || !password) return showToast("Вкажіть логін і пароль.");
    if (role === 'Operator' && !operatorCodeRaw) {
        return showToast("Для оператора потрібен код з бейджика.");
    }

    const body = {
        username: username,
        password: password,
        role: role,
        operator_code: role === 'Operator' ? operatorCodeRaw : null
    };

    try {
        const res = await fetch(`${API_BASE}/users`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify(body)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed');
        }
        showToast("Оператора створено");
        closeModals();
    } catch (e) {
        showToast("Помилка створення: " + e.message);
    }
}

// Init
document.getElementById('logoutBtn').addEventListener('click', () => {
    localStorage.removeItem('access_token');
    window.location.href = '/';
});

fetchData();
loadBlocked();
loadHistory();
refreshTimer = setInterval(() => { fetchData(); loadBlocked(); loadHistory(); }, 10000);
