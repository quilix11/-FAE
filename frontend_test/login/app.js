const API_BASE = "/api/v1";

// Redirect if already logged in
if (localStorage.getItem("token")) {
    const role = localStorage.getItem("role");
    if (role === "tech_admin") {
        window.location.replace("/admin/");
    } else {
        const machine = localStorage.getItem("machine") || "G01";
        window.location.replace(`/operator/?machine=${machine}`);
    }
}

async function doLogin() {
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const btn = document.getElementById("loginBtn");
    const errEl = document.getElementById("errorMsg");

    if (!username || !password) {
        showError("Введіть логін і пароль");
        return;
    }

    btn.disabled = true;
    btn.textContent = "Вхід…";
    errEl.style.display = "none";

    try {
        const body = new URLSearchParams({ username, password });
        const res = await fetch("/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body,
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Невірний логін або пароль");
        }

        const data = await res.json();
        localStorage.setItem("token", data.access_token);
        localStorage.setItem("role", data.role);
        localStorage.setItem("username", data.username);

        if (data.role === "tech_admin") {
            window.location.replace("/admin/");
        } else {
            // Operator — pick machine
            await showMachinePicker(data.access_token);
        }
    } catch (err) {
        showError(err.message);
        btn.disabled = false;
        btn.textContent = "Увійти";
    }
}

async function showMachinePicker(token) {
    const res = await fetch(`${API_BASE}/machines`, {
        headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
        window.location.replace("/operator/?machine=G01");
        return;
    }
    const machines = await res.json();
    const cuttingMachines = machines.filter(m => m.zone_name === "Cutting");

    const card = document.querySelector(".auth-card");
    card.innerHTML = `
        <h2 style="margin-bottom:20px;font-size:1.1rem">Оберіть машину</h2>
        <div class="form-group">
            <label>Машина (дільниця нарізки)</label>
            <select id="machineSelect">
                <option value="">-- Оберіть --</option>
                ${machines.map(m => `<option value="${m.hardware_code}">${m.hardware_code} (${m.zone_name})</option>`).join("")}
            </select>
        </div>
        <button class="btn btn-primary" onclick="goToMachine()">Перейти</button>
    `;
}

function goToMachine() {
    const code = document.getElementById("machineSelect").value;
    if (!code) return;
    localStorage.setItem("machine", code);
    window.location.replace(`/operator/?machine=${code}`);
}

function showError(msg) {
    const el = document.getElementById("errorMsg");
    if (!el) return;
    el.textContent = msg;
    el.style.display = "block";
}

// Allow Enter key to submit
document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && document.getElementById("loginBtn")) {
        doLogin();
    }
});
