// ══════════════════════════════════════════════════════════════
// common.js - Shared Logic (Loaded on Every Page)
//
// This file is included via <script> tag on every page in the app.
// It provides shared functionality that all pages need:
//   - Sidebar menu (open/close/toggle)
//   - Page navigation (routing between pages)
//   - Authentication helpers (get username, token, role, etc.)
//   - Logout functionality
//   - Text direction detection (Arabic = RTL, English = LTR)
//   - Toast notifications
//   - Role-based UI (hide menu items based on student/instructor role)
// ══════════════════════════════════════════════════════════════

// Base URL for API calls. Empty string means "same server".
// If the app were deployed separately from the API, this would be
// something like 'https://api.chatnct.com'.
let API_BASE = '';
if (localStorage.getItem('chatnct_backend') === 'php') {
    API_BASE = '../php_backend/api/proxy.php?path=';
} else {
    const isLiveServer = window.location.port && window.location.port !== '5000';
    const isLocalFile = window.location.protocol === 'file:';
    if (isLiveServer) {
        API_BASE = `https://${window.location.hostname}:5000`;
    } else if (isLocalFile) {
        API_BASE = 'https://localhost:5000';
    }
}


// ── Theme Management (Forced Dark Mode) ───────────────────────
// Light mode has been completely removed. Theme is permanently set to 'dark'.
function initTheme() {
    document.documentElement.setAttribute('data-theme', 'dark');
    localStorage.setItem('chatnct_theme', 'dark');
}

function toggleTheme() {
    // No-op: Light mode is disabled
}

function updateThemeToggleUI(theme) {
    // No-op: Light mode is disabled
}

// Apply theme BEFORE the page is rendered to prevent flash
initTheme();


// ── Sidebar Menu ───────────────────────────────────────────
// The sidebar is the navigation panel on the left side of the screen.
// On mobile, it slides in from the left with an overlay behind it.
const menuToggle = document.getElementById('menuToggle');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const sidebarClose = document.getElementById('sidebarClose');

function openSidebar() {
    if (sidebar) sidebar.classList.add('active');
    if (sidebarOverlay) sidebarOverlay.classList.add('active');
    if (menuToggle) menuToggle.classList.add('active');
    document.body.style.overflow = 'hidden';  // Prevent page scrolling when sidebar is open
}

function closeSidebar() {
    if (sidebar) sidebar.classList.remove('active');
    if (sidebarOverlay) sidebarOverlay.classList.remove('active');
    if (menuToggle) menuToggle.classList.remove('active');
    document.body.style.overflow = '';  // Re-enable page scrolling
}

// Toggle sidebar when hamburger menu button is clicked
if (menuToggle) {
    menuToggle.addEventListener('click', () => {
        sidebar && sidebar.classList.contains('active') ? closeSidebar() : openSidebar();
    });
}
// Close sidebar when X button or dark overlay is clicked
if (sidebarClose) sidebarClose.addEventListener('click', closeSidebar);
if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);


// ── Page Navigation ────────────────────────────────────────
// Maps friendly page names to actual file paths.
// Used by sidebar menu items: onclick="navigateTo('chat')"
function navigateTo(page) {
    const routes = {
        'dashboard': 'dashboard.html',
        'newchat': 'chat.html',
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


// ── Authentication Helpers ─────────────────────────────────
// After login, user data is stored in localStorage (browser storage).
// These functions retrieve that stored data for use across pages.

function getUsername() {
    return localStorage.getItem('chatnct_username') || 'Guest';
}

function getAccessToken() {
    return localStorage.getItem('chatnct_access_token') || '';
}

function getUserId() {
    // User ID is the student's university ID (e.g. "20240471")
    return localStorage.getItem('chatnct_user_id') || getUsername();
}

function isAdmin() {
    return localStorage.getItem('chatnct_is_admin') === 'true';
}

function getRole() {
    // Returns "student", "instructor", or "admin"
    return (localStorage.getItem('chatnct_role') || 'student').toLowerCase();
}

function getAuthHeaders() {
    // Build HTTP headers with the auth token for API requests.
    // The token is sent as a Bearer token in the Authorization header,
    // which is the standard way to authenticate API calls.
    const headers = { 'Content-Type': 'application/json' };
    const token = getAccessToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
}

function checkAuth() {
    // Verify the user is logged in. If not, redirect to login page.
    // First check localStorage (fast), Supabase session is verified by requireAuth() on page load
    const username = localStorage.getItem('chatnct_username');
    const role = localStorage.getItem('chatnct_role');
    if (!username || !role) {
        logout();
        return false;
    }
    return true;
}

function logout() {
    // Clear all stored user data and sign out from Supabase
    if (typeof authSignOut === 'function') {
        authSignOut(); // This clears localStorage + redirects
    } else {
        // Fallback if supabase-client.js hasn't loaded yet
        localStorage.removeItem('chatnct_username');
        localStorage.removeItem('chatnct_is_admin');
        localStorage.removeItem('chatnct_role');
        localStorage.removeItem('chatnct_skip_dashboard');
        localStorage.removeItem('chatnct_access_token');
        localStorage.removeItem('chatnct_refresh_token');
        localStorage.removeItem('chatnct_user_id');
        localStorage.removeItem('chatnct_backend');
        window.location.href = 'index.html';
    }
}


// ── RTL/LTR Text Direction Detection ───────────────────────
// Arabic text reads right-to-left (RTL), English reads left-to-right (LTR).
// This function checks the first meaningful character to determine direction,
// so the UI can align text properly.
function detectDirection(text) {
    // Strip markdown characters to find the first "real" letter
    const stripped = text.replace(/[#*_`~>\-\d.\s\[\]()!]/g, '');
    const firstChar = stripped.charAt(0);
    // Check if the character is in the Arabic Unicode range
    const arabicRegex = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
    return arabicRegex.test(firstChar) ? 'rtl' : 'ltr';
}


// ── Toast Notifications ────────────────────────────────────
// Shows a temporary message at the top of the screen that auto-fades.
// Usage: showNotification('Saved!', 'success')
function showNotification(text, type = 'info') {
    const colors = { info: '#7c66e3', success: '#10b981', error: '#ef4444' };
    const msg = document.createElement('div');
    msg.className = 'notification';
    msg.setAttribute('role', 'alert');
    msg.style.background = colors[type] || colors.info;
    msg.innerText = text;
    document.body.appendChild(msg);
    // Remove after 3 seconds with a fade-out animation
    setTimeout(() => {
        msg.style.opacity = '0';
        msg.style.transition = 'opacity 0.5s';
        setTimeout(() => msg.remove(), 500);
    }, 3000);
}


// ── Sidebar User Display ───────────────────────────────────
// Shows the logged-in user's name and initial in the sidebar footer.
function initSidebarUser() {
    const username = getUsername();
    const avatarEl = document.getElementById('userAvatar');
    const nameEl = document.getElementById('userNameDisplay');
    if (avatarEl) avatarEl.textContent = username.charAt(0).toUpperCase();
    if (nameEl) nameEl.textContent = username;
}


// ── Keyboard Shortcuts ─────────────────────────────────────
// Close sidebar when Escape key is pressed
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar && sidebar.classList.contains('active')) {
        closeSidebar();
    }
});


// ── Role-Based Navigation ──────────────────────────────────
// Hides sidebar menu items and dashboard cards that the current user
// shouldn't see based on their role (student/instructor/admin).
// Uses data-role="student" and data-card-role="instructor,admin" HTML attributes.
function initRoleBasedNav() {
    const role = getRole();
    // Hide sidebar items that don't match user's role
    document.querySelectorAll('[data-role]').forEach(el => {
        const allowedRoles = el.dataset.role.split(',').map(r => r.trim());
        if (!allowedRoles.includes(role) && !allowedRoles.includes('all')) {
            el.style.display = 'none';
        }
    });
    // Hide dashboard quick-action cards that don't match user's role
    document.querySelectorAll('[data-card-role]').forEach(el => {
        const allowedRoles = el.dataset.cardRole.split(',').map(r => r.trim());
        if (!allowedRoles.includes(role) && !allowedRoles.includes('all')) {
            el.style.display = 'none';
        }
    });
}


// ── Logo → Dashboard ───────────────────────────────────────
function initLogoNavigation() {
    document.querySelectorAll('.header-logo, .sidebar-logo').forEach(logo => {
        logo.style.cursor = 'pointer';
        logo.setAttribute('role', 'link');
        logo.setAttribute('aria-label', 'Go to Dashboard');
        logo.addEventListener('click', () => {
            closeSidebar();
            if (!window.location.pathname.endsWith('dashboard.html')) {
                navigateTo('dashboard');
            }
        });
    });
}


// ── Initialize on Page Load ────────────────────────────────
// These functions run automatically when any page finishes loading.
document.addEventListener('DOMContentLoaded', () => {
    initSidebarUser();      // Show username in sidebar
    initRoleBasedNav();     // Hide/show menu items based on role
    initLogoNavigation();   // Logo click → dashboard
    updateThemeToggleUI(localStorage.getItem('chatnct_theme') || 'dark'); // Sync toggle button icon
    loadGlobalChatHistory(); // Load chat history in sidebar (all pages)
});


// ── Global Chat History (Sidebar — All Pages) ──────────────
// Loads recent chat sessions into the sidebar on every page,
// so users can always see and resume past conversations.

// Inject CSS for chat history items (needed on pages that don't have chat.css)
(function injectChatHistoryStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .chat-history-section { padding: 0 8px; margin-top: 4px; }
        .chat-history-header {
            display: flex; align-items: center; gap: 8px; padding: 8px 12px;
            color: var(--text-tertiary); font-size: 11px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 1px;
        }
        .chat-history-item {
            display: flex; align-items: center; justify-content: space-between;
            padding: 10px 12px; color: var(--text-secondary); cursor: pointer;
            border-radius: 10px; transition: all 0.2s ease; font-size: 13px;
            margin-bottom: 2px; font-weight: 500;
        }
        .chat-history-item:hover { background: var(--accent-muted); color: var(--text-primary); }
        .chat-history-title {
            flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
            cursor: pointer;
        }
        .chat-history-actions { display: flex; gap: 4px; opacity: 0; transition: opacity 0.2s; }
        .chat-history-item:hover .chat-history-actions { opacity: 1; }
        .chat-history-btn {
            width: 26px; height: 26px; border: none; border-radius: 8px;
            background: var(--accent-muted); color: var(--text-secondary); cursor: pointer;
            display: flex; align-items: center; justify-content: center; font-size: 11px;
            transition: all 0.2s;
        }
        .chat-history-btn:hover { background: var(--accent); color: white; }
        .chat-history-btn.delete:hover { background: var(--error-muted); color: var(--error); }
    `;
    document.head.appendChild(style);
})();

async function loadGlobalChatHistory() {
    const container = document.getElementById('chatHistoryList');
    if (!container) return; // No sidebar on this page

    const token = getAccessToken();
    if (!token) return; // Not logged in

    try {
        const res = await fetch(`${API_BASE}/api/chat/sessions?per_page=10`, {
            headers: getAuthHeaders(),
        });
        const data = await res.json();
        if (data.status === 'success') {
            renderGlobalSessionList(data.sessions, container);
        }
    } catch (e) {
        console.error('Load global chat history error:', e);
    }
}

function renderGlobalSessionList(sessions, container) {
    container.innerHTML = '';
    const isOnChatPage = window.location.pathname.endsWith('chat.html');

    sessions.forEach(s => {
        const item = document.createElement('div');
        item.className = 'chat-history-item';
        item.dataset.sessionId = s.id;

        if (isOnChatPage) {
            // On chat page: use the existing chat.js functions (resumeSession, etc.)
            item.innerHTML = `
                <span class="chat-history-title" onclick="resumeSession('${s.id}')">${s.title}</span>
                <div class="chat-history-actions">
                    <button class="chat-history-btn" onclick="renameSession('${s.id}')" title="Rename">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="chat-history-btn delete" onclick="deleteSession('${s.id}')" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
        } else {
            // On other pages: clicking navigates to chat.html with the session
            item.innerHTML = `
                <span class="chat-history-title">${s.title}</span>
            `;
            item.addEventListener('click', () => {
                window.location.href = `chat.html?session=${s.id}`;
            });
        }
        container.appendChild(item);
    });

    if (sessions.length === 0) {
        container.innerHTML = '<div style="padding: 8px 12px; color: var(--text-tertiary); font-size: 12px;">No chats yet</div>';
    }
}

