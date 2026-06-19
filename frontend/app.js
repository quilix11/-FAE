const API_BASE = 'https://fujikuraproject-production.up.railway.app';
let currentMachineCode = new URLSearchParams(window.location.search).get('machine') || 'G05';

// DOM Elements
const machineIdEl = document.getElementById('machine-id');
const capacityCountEl = document.getElementById('capacity-count');
const gridEl = document.getElementById('applicator-grid');
const toastEl = document.getElementById('scanner-status');

// Initialize
async function init() {
    machineIdEl.textContent = currentMachineCode;
    await fetchDashboard();
}

async function fetchDashboard() {
    try {
        const res = await fetch(`${API_BASE}/dashboard/${currentMachineCode}`);
        if(!res.ok) throw new Error('Machine not found');
        const data = await res.json();
        
        capacityCountEl.textContent = `${data.current_capacity}/${data.max_capacity}`;
        renderGrid(data.applicators);
    } catch (e) {
        gridEl.innerHTML = `<p style="color: red">Error: ${e.message}</p>`;
    }
}

function renderGrid(applicators) {
    gridEl.innerHTML = '';
    applicators.forEach(app => {
        const card = document.createElement('div');
        card.className = `card ${app.state}`;
        card.innerHTML = `
            <h3>SN: ${app.serial_number}</h3>
            <p>Status: ${app.state === 'in_use' ? 'In Press (Green)' : 'On Rack (Yellow)'}</p>
            <button class="btn btn-toggle" onclick="toggleState(${app.id}, '${app.state}')">
                Toggle Status
            </button>
        `;
        gridEl.appendChild(card);
    });
}

async function toggleState(id, currentState) {
    const newState = currentState === 'in_use' ? 'on_rack' : 'in_use';
    try {
        await fetch(`${API_BASE}/applicator/${id}/state`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_state: newState })
        });
        await fetchDashboard();
    } catch (e) {
        alert('Failed to update state');
    }
}

// Scanner Logic
let buffer = '';
let lastKeyTime = 0;

document.addEventListener('keydown', (e) => {
    const currentTime = Date.now();
    
    // Ignore non-character keys except Enter
    if (e.key.length > 1 && e.key !== 'Enter') return;

    if (currentTime - lastKeyTime > 100) {
        buffer = ''; // Reset if typing is too slow
    }
    
    if (e.key === 'Enter') {
        if (buffer.length > 3 && (currentTime - lastKeyTime) < 100) {
            e.preventDefault();
            handleScan(buffer);
            buffer = '';
        }
    } else {
        buffer += e.key;
    }
    
    lastKeyTime = currentTime;
});

async function handleScan(serialNumber) {
    toastEl.classList.remove('hidden');
    setTimeout(() => toastEl.classList.add('hidden'), 3000);
    
    try {
        const res = await fetch(`${API_BASE}/scan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                serial_number: serialNumber,
                hardware_code: currentMachineCode
            })
        });
        
        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.detail || 'Unknown error');
        }
        
        await fetchDashboard();
    } catch (e) {
        alert('Scan failed: ' + e.message);
    }
}

init();
