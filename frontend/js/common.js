// ══════════════════════════════════════════════════════════════
// ChatNCT — Common JavaScript (Shared Logic)
// ══════════════════════════════════════════════════════════════

// ── Sidebar ────────────────────────────────────────────────
const menuToggle = document.getElementById('menuToggle');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const sidebarClose = document.getElementById('sidebarClose');

function openSidebar() {
    if (sidebar) sidebar.classList.add('active');
    if (sidebarOverlay) sidebarOverlay.classList.add('active');
    if (menuToggle) menuToggle.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeSidebar() {
    if (sidebar) sidebar.classList.remove('active');
    if (sidebarOverlay) sidebarOverlay.classList.remove('active');
    if (menuToggle) menuToggle.classList.remove('active');
    document.body.style.overflow = '';
}

if (menuToggle) {
    menuToggle.addEventListener('click', () => {
        sidebar && sidebar.classList.contains('active') ? closeSidebar() : openSidebar();
    });
}
if (sidebarClose) sidebarClose.addEventListener('click', closeSidebar);
if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);

// ── Navigation ─────────────────────────────────────────────
function navigateTo(page) {
    const routes = {
        'dashboard': 'chat.html',
        'newchat': 'chat.html?view=chat',
        'chat': 'chat.html?view=chat',
        'attendance': 'attendance.html',
        'instructor': 'instructor.html',
        'prompt': 'prompt.html',
        'login': 'index.html',
    };
    const url = routes[page] || page;
    if (url) window.location.href = url;
    closeSidebar();
}

// ── Auth Helpers ───────────────────────────────────────────
function getUsername() {
    return localStorage.getItem('chatnct_username') || 'Guest';
}

function isAdmin() {
    return localStorage.getItem('chatnct_is_admin') === 'true';
}

function getRole() {
    return (localStorage.getItem('chatnct_role') || 'student').toLowerCase();
}

function checkAuth() {
    const username = localStorage.getItem('chatnct_username');
    if (!username) {
        window.location.href = 'index.html';
        return false;
    }
    return true;
}

function logout() {
    localStorage.removeItem('chatnct_username');
    localStorage.removeItem('chatnct_is_admin');
    localStorage.removeItem('chatnct_role');
    localStorage.removeItem('chatnct_skip_dashboard');
    window.location.href = 'index.html';
}

// ── RTL/LTR Detection ──────────────────────────────────────
function detectDirection(text) {
    const stripped = text.replace(/[#*_`~>\-\d.\s\[\]()!]/g, '');
    const firstChar = stripped.charAt(0);
    const arabicRegex = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
    return arabicRegex.test(firstChar) ? 'rtl' : 'ltr';
}

// ── Notifications ──────────────────────────────────────────
function showNotification(text, type = 'info') {
    const colors = { info: '#5c4eb3', success: '#22c55e', error: '#ef4444' };
    const msg = document.createElement('div');
    msg.className = 'notification';
    msg.setAttribute('role', 'alert');
    msg.style.background = colors[type] || colors.info;
    msg.innerText = text;
    document.body.appendChild(msg);
    setTimeout(() => {
        msg.style.opacity = '0';
        msg.style.transition = 'opacity 0.5s';
        setTimeout(() => msg.remove(), 500);
    }, 3000);
}

// ── Sidebar User Display ───────────────────────────────────
function initSidebarUser() {
    const username = getUsername();
    const avatarEl = document.getElementById('userAvatar');
    const nameEl = document.getElementById('userNameDisplay');
    if (avatarEl) avatarEl.textContent = username.charAt(0).toUpperCase();
    if (nameEl) nameEl.textContent = username;
}

// ── Escape Key Handler ─────────────────────────────────────
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar && sidebar.classList.contains('active')) {
        closeSidebar();
    }
});

// ── Role-Based Navigation ─────────────────────────────────
function initRoleBasedNav() {
    const role = getRole();
    // Hide sidebar items based on data-role attribute
    document.querySelectorAll('[data-role]').forEach(el => {
        const allowedRoles = el.dataset.role.split(',').map(r => r.trim());
        if (!allowedRoles.includes(role) && !allowedRoles.includes('all')) {
            el.style.display = 'none';
        }
    });
    // Hide dashboard quick-action cards based on data-card-role
    document.querySelectorAll('[data-card-role]').forEach(el => {
        const allowedRoles = el.dataset.cardRole.split(',').map(r => r.trim());
        if (!allowedRoles.includes(role) && !allowedRoles.includes('all')) {
            el.style.display = 'none';
        }
    });
}

// ── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initSidebarUser();
    initRoleBasedNav();
});
