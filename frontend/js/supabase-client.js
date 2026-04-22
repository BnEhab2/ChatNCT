// ══════════════════════════════════════════════════════════════
// supabase-client.js - Supabase Auth Module
//
// This file initializes the Supabase client and provides
// all authentication-related functions used across the app:
//
//   1. signIn(email, password)     — Login with email/password
//   2. signUp(email, password, metadata) — Register new user
//   3. signOut()                   — Logout and clear session
//   4. getSession()               — Get current auth session
//   5. getProfile()               — Fetch user profile from DB
//   6. onAuthChange(callback)     — Listen for session changes
//   7. requireAuth()              — Guard: redirect if not logged in
//
// The Supabase client uses the project's anon key for
// client-side operations. All auth state is managed by
// Supabase's built-in session handling (stored in localStorage).
// ══════════════════════════════════════════════════════════════

// ── Supabase Configuration ─────────────────────────────────
// These values come from the Supabase dashboard → Settings → API
const SUPABASE_URL = 'https://jfuplykfnihebjlsbfen.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpmdXBseWtmbmloZWJqbHNiZmVuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYyNzU4NjUsImV4cCI6MjA5MTg1MTg2NX0.QK2S_U49RuCmXOlP2MtmXExxw2wApCGMRAhYaCaz_7E';

// ── Initialize Supabase Client ─────────────────────────────
// supabase-js is loaded via CDN in the HTML files
var _supabase = null;
try {
    if (typeof window !== 'undefined' && window.supabase && typeof window.supabase.createClient === 'function') {
        _supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
        console.log("Supabase Client: Initialized successfully.");
    } else {
        console.error("Supabase CDN failed to load. window.supabase =", typeof window !== 'undefined' ? window.supabase : 'N/A');
    }
} catch (e) {
    console.error("Supabase Client: Error during initialization:", e);
}


// ══════════════════════════════════════════════════════════════
// SIGN IN
//
// Authenticates a user with email + password via Supabase Auth.
// On success, checks the user's profile status:
//   - "pending" → sign out immediately + return pending status
//   - "active"  → return session + profile data
// ══════════════════════════════════════════════════════════════

async function authSignIn(email, password) {
    if (!_supabase) {
        return { success: false, error: 'تعذر الاتصال بـ Supabase. يرجى التحقق من اتصال الإنترنت أو تعطيل مانع الإعلانات.' };
    }

    const { data, error } = await _supabase.auth.signInWithPassword({
        email,
        password,
    });

    if (error) {
        return { success: false, error: error.message };
    }

    // Fetch user profile to get role and name
    const profile = await fetchProfile(data.user.id);

    if (!profile) {
        await _supabase.auth.signOut();
        return { success: false, error: 'لم يتم العثور على ملفك الشخصي. تواصل مع الإدارة.' };
    }

    if (profile.status === 'blocked') {
        await _supabase.auth.signOut();
        return { success: false, error: 'تم حظر حسابك. تواصل مع الإدارة.' };
    }

    // Store essential data in localStorage for quick access
    localStorage.setItem('chatnct_username', profile.name);
    localStorage.setItem('chatnct_role', profile.role);
    localStorage.setItem('chatnct_user_id', profile.student_code || data.user.id);
    localStorage.setItem('chatnct_is_admin', profile.role === 'admin' ? 'true' : 'false');

    return {
        success: true,
        user: data.user,
        session: data.session,
        profile,
    };
}


// ══════════════════════════════════════════════════════════════
// SIGN UP (Registration)
//
// Creates a new user account in Supabase Auth. A database
// trigger will automatically create a profile row with
// status='active'. The user can log in right away.
// ══════════════════════════════════════════════════════════════

async function authSignUp(email, password, metadata = {}) {
    if (!_supabase) {
        return { success: false, error: 'Supabase not initialized.' };
    }
    const { data, error } = await _supabase.auth.signUp({
        email,
        password,
        options: {
            data: {
                name: metadata.name || '',
                role: metadata.role || 'student',
                student_code: metadata.student_code || '',
            },
        },
    });

    if (error) {
        return { success: false, error: error.message };
    }

    return {
        success: true,
        user: data.user,
        session: data.session,
        message: 'تم إنشاء حسابك بنجاح!',
    };
}


// ══════════════════════════════════════════════════════════════
// SIGN OUT
//
// Logs out the user, clears all localStorage data, and
// redirects to the login page.
// ══════════════════════════════════════════════════════════════

async function authSignOut() {
    if (_supabase) {
        await _supabase.auth.signOut();
    }
    // Clear all stored user data
    localStorage.removeItem('chatnct_username');
    localStorage.removeItem('chatnct_is_admin');
    localStorage.removeItem('chatnct_role');
    localStorage.removeItem('chatnct_skip_dashboard');
    localStorage.removeItem('chatnct_access_token');
    localStorage.removeItem('chatnct_refresh_token');
    localStorage.removeItem('chatnct_user_id');
    window.location.href = 'index.html';
}


// ══════════════════════════════════════════════════════════════
// FETCH PROFILE
//
// Gets the user's profile from the `profiles` table.
// This contains role, status, name, and student_code.
// ══════════════════════════════════════════════════════════════

async function fetchProfile(userId) {
    if (!_supabase) return null;
    const { data, error } = await _supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .single();

    if (error) {
        console.error('Error fetching profile:', error.message);
        return null;
    }
    return data;
}


// ══════════════════════════════════════════════════════════════
// GET CURRENT SESSION
//
// Returns the current Supabase auth session (access token,
// user data, etc.) or null if not logged in.
// ══════════════════════════════════════════════════════════════

async function getAuthSession() {
    if (!_supabase) return null;
    const { data: { session } } = await _supabase.auth.getSession();
    return session;
}


// ══════════════════════════════════════════════════════════════
// AUTH STATE LISTENER
//
// Listens for changes in auth state (login, logout, token
// refresh, etc.) and fires a callback. Used to auto-redirect
// when the session expires.
// ══════════════════════════════════════════════════════════════

function onAuthStateChange(callback) {
    if (!_supabase) {
        console.warn('Supabase not initialized, cannot attach auth listener.');
        return;
    }
    _supabase.auth.onAuthStateChange((event, session) => {
        callback(event, session);
    });
}


// ══════════════════════════════════════════════════════════════
// AUTH GUARD
//
// Call this at the top of any protected page. If no active
// session exists, redirects to the login page immediately.
// If session exists, syncs localStorage with profile data.
// ══════════════════════════════════════════════════════════════

async function requireAuth() {
    const session = await getAuthSession();
    if (!session) {
        window.location.href = 'index.html';
        return null;
    }

    // Sync profile data to localStorage
    const profile = await fetchProfile(session.user.id);
    if (profile) {
        localStorage.setItem('chatnct_username', profile.name);
        localStorage.setItem('chatnct_role', profile.role);
        localStorage.setItem('chatnct_user_id', profile.student_code || session.user.id);
        localStorage.setItem('chatnct_is_admin', profile.role === 'admin' ? 'true' : 'false');
    }

    return { session, profile };
}


// ══════════════════════════════════════════════════════════════
// ROLE-BASED REDIRECT
//
// After login, redirect user to the appropriate page based
// on their role in the profiles table.
// ══════════════════════════════════════════════════════════════

function redirectByRole(role) {
    if (role === 'admin' || role === 'instructor') {
        localStorage.setItem('chatnct_skip_dashboard', 'true');
        window.location.href = 'dashboard.html';
    } else {
        localStorage.removeItem('chatnct_skip_dashboard');
        window.location.href = 'dashboard.html';
    }
}


// ══════════════════════════════════════════════════════════════
// AUTH STATE WATCHER (Auto-redirect on session expiry)
//
// This runs on every page to detect when the session
// is lost (e.g., token expired, user signed out in another tab).
// ══════════════════════════════════════════════════════════════

onAuthStateChange((event, session) => {
    if (event === 'SIGNED_OUT') {
        // Don't redirect if already on login/register page
        const currentPage = window.location.pathname.split('/').pop();
        if (currentPage !== 'index.html' && currentPage !== '') {
            window.location.href = 'index.html';
        }
    }
});

console.log("Supabase Client: Fully loaded. authSignIn =", typeof authSignIn);
