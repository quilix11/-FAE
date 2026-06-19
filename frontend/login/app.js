const API_BASE = "/api";
const AUTH_BASE = "/auth";

let selectedRole = null;

async function login(identifier, password, loginType) {
    const formData = new URLSearchParams();
    formData.append("username", identifier);
    formData.append("password", password);
    formData.append("login_type", loginType);

    const res = await fetch(`${AUTH_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData.toString(),
    });

    if (!res.ok) throw new Error("Invalid credentials");
    const data = await res.json();
    localStorage.setItem("access_token", data.access_token);
    return data;
}

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

function selectRole(role) {
    selectedRole = role;
    document.getElementById("roleStep").style.display = "none";
    document.getElementById("loginStep").style.display = "block";

    const badge = document.getElementById("roleBadge");
    const title = document.getElementById("loginTitle");
    const usernameLabel = document.getElementById("usernameLabel");
    const usernameInput = document.getElementById("username");
    const machineGroup = document.getElementById("machineGroup");
    const demoText = document.getElementById("demoText");

    if (role === "admin") {
        badge.textContent = "Адміністратор";
        badge.className = "role-badge role-badge--admin";
        title.textContent = "Вхід адміністратора";
        usernameLabel.textContent = "Логін";
        usernameInput.placeholder = "Наприклад: admin";
        usernameInput.autocomplete = "username";
        machineGroup.style.display = "none";
        demoText.textContent = "admin / admin";
    } else {
        badge.textContent = "Оператор";
        badge.className = "role-badge role-badge--operator";
        title.textContent = "Вхід оператора";
        usernameLabel.textContent = "Код з бейджика";
        usernameInput.placeholder = "Наприклад: OP_001";
        usernameInput.autocomplete = "off";
        machineGroup.style.display = "block";
        demoText.textContent = "OP_001 / operator";
        loadMachines();
    }

    document.getElementById("errorMsg").style.display = "none";
    document.getElementById("username").value = "";
    document.getElementById("password").value = "";
    document.getElementById("username").focus();
}

function goBack() {
    selectedRole = null;
    document.getElementById("roleStep").style.display = "block";
    document.getElementById("loginStep").style.display = "none";
    document.getElementById("errorMsg").style.display = "none";
}

async function loadMachines() {
    const select = document.getElementById("machineSelect");
    select.innerHTML = '<option value="">Завантаження...</option>';

    try {
        const res = await fetch(`${API_BASE}/public/machines`);
        if (!res.ok) throw new Error("Failed");
        const machines = await res.json();
        select.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "— Оберіть машину —";
        select.appendChild(placeholder);

        if (machines.length === 0) {
            placeholder.textContent = "Немає машин (зверніться до адміна)";
            return;
        }
        machines.forEach((m) => {
            const opt = document.createElement("option");
            opt.value = m.hardware_code;
            opt.textContent = `${m.hardware_code} — ${m.zone_name}`;
            select.appendChild(opt);
        });
    } catch {
        select.innerHTML = '<option value="">Не вдалося завантажити машини</option>';
    }
}

async function doLogin() {
    const userVal = document.getElementById("username").value.trim();
    const passVal = document.getElementById("password").value.trim();
    const errDiv = document.getElementById("errorMsg");
    const loginBtn = document.getElementById("loginBtn");

    errDiv.style.display = "none";

    if (!userVal || !passVal) {
        errDiv.textContent = "Будь ласка, заповніть усі поля.";
        errDiv.style.display = "block";
        return;
    }

    if (selectedRole === "operator") {
        const machine = document.getElementById("machineSelect").value;
        if (!machine) {
            errDiv.textContent = "Оберіть машину.";
            errDiv.style.display = "block";
            return;
        }
    }

    loginBtn.disabled = true;
    loginBtn.textContent = "Вхід...";

    const loginType = selectedRole === "operator" ? "operator_code" : "username";

    try {
        const loginData = await login(userVal, passVal, loginType);
        const payload = parseJwt(loginData.access_token);
        const role = payload?.role?.toUpperCase() || "";

        if (selectedRole === "admin") {
            if (role !== "TECH_ADMIN" && role !== "SHIFT_LEADER") {
                localStorage.removeItem("access_token");
                throw new Error("wrong_role");
            }
            window.location.href = "/admin/";
        } else {
            if (role === "TECH_ADMIN" || role === "SHIFT_LEADER") {
                localStorage.removeItem("access_token");
                throw new Error("wrong_role");
            }
            const machine = document.getElementById("machineSelect").value;
            localStorage.setItem("operator_machine", machine);
            window.location.href = `/operator/?machine=${encodeURIComponent(machine)}`;
        }
    } catch (e) {
        if (e.message === "wrong_role") {
            errDiv.textContent = selectedRole === "admin"
                ? "Цей обліковий запис не є адміністратором."
                : "Цей обліковий запис не є оператором.";
        } else {
            errDiv.textContent = "Невірний логін або пароль.";
        }
        errDiv.style.display = "block";
        loginBtn.disabled = false;
        loginBtn.textContent = "Увійти";
    }
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && document.getElementById("loginStep").style.display !== "none") {
        doLogin();
    }
});
