// ══════════════════════════════════════════════════════════════
// login.js - Login Page Logic
//
// This file handles:
//   1. The animated intro-to-login scroll transition (logo morph effect)
//   2. Login form submission (sends credentials to the server API)
//   3. Storing user session data after successful login
//   4. Redirecting users to the dashboard
//
// The login page has TWO sections:
//   Section 0 (Intro): Shows the big animated logo
//   Section 1 (Login): Shows the login form with robot character
// Scrolling/swiping transitions between them smoothly.
// ══════════════════════════════════════════════════════════════

// API base URL (empty = same server)
const API_BASE = '';

// ── DOM Element References ─────────────────────────────────
// Grab references to all the elements we'll animate and interact with
const scrollContainer = document.getElementById('scrollContainer');
const morphLogo = document.getElementById('morphLogo');
const introTagline = document.getElementById('introTagline');
const scrollIndicator = document.getElementById('scrollIndicator');
const robotContainer = document.getElementById('robotContainer');
const welcomeText = document.getElementById('welcomeText');
const loginCard = document.getElementById('loginCard');
const sectionIntro = document.getElementById('section-intro');
const sectionLogin = document.getElementById('section-login');

// Track which section is currently visible (0 = intro, 1 = login)
let currentSection = 0, scrollTimeout, rafId = null;


// ══════════════════════════════════════════════════════════════
// SCROLL ANIMATION (Logo Morph Effect)
//
// As the user scrolls from the intro to the login section,
// the logo smoothly moves from center to top-left and shrinks.
// The robot and login form fade in as the user scrolls down.
// ══════════════════════════════════════════════════════════════

function updateMorphOnScroll() {
    const scrollTop = scrollContainer.scrollTop;
    const windowHeight = window.innerHeight;

    // Calculate scroll progress: 0.0 (top) to 1.0 (fully scrolled)
    const progress = Math.min(Math.max(scrollTop / windowHeight, 0), 1);

    // Adjust end position based on screen size (responsive)
    let endLeft = 12, endScale = 0.85;
    if (window.innerWidth <= 480) { endLeft = 20; endScale = 0.88; }
    else if (window.innerWidth <= 768) { endLeft = 15; endScale = 0.32; }

    // Interpolate logo position/scale from start to end based on progress
    const startTop = 50, endTop = 8, startLeft = 50, startScale = 1;
    const currentTop = startTop - (progress * (startTop - endTop));
    const currentLeft = startLeft - (progress * (startLeft - endLeft));
    const currentScale = startScale - (progress * (startScale - endScale));
    const currentOpacity = 1 - (progress * 0.3);
    const currentGlow = 30 - (progress * 20);

    // Apply the calculated values to the logo element
    morphLogo.style.top = `${currentTop}%`;
    morphLogo.style.left = `${currentLeft}%`;
    morphLogo.style.transform = `translate(-50%, -50%) scale(${currentScale})`;
    morphLogo.style.opacity = currentOpacity;
    morphLogo.style.filter = `drop-shadow(0 0 ${currentGlow}px rgba(124,102,227,${0.8 - progress * 0.3}))`;

    // Fade out the intro tagline as user scrolls
    if (introTagline) introTagline.style.opacity = 1 - progress;

    // Fade in the login elements (robot, welcome text, login card)
    // They start appearing after 50% scroll progress
    const fadeStart = 0.5;
    [robotContainer, welcomeText, loginCard].forEach(el => {
        if (el) {
            const opacity = progress > fadeStart ? (progress - fadeStart) * 2 : 0;
            el.style.opacity = opacity;
            el.classList.toggle('visible', progress > 0.8);
        }
    });

    // Hide the scroll indicator arrow once past 50%
    if (scrollIndicator) {
        if (progress >= 0.5) { scrollIndicator.style.opacity = '0'; scrollIndicator.style.pointerEvents = 'none'; }
        else { scrollIndicator.style.opacity = '1'; scrollIndicator.style.pointerEvents = 'auto'; }
    }

    currentSection = progress > 0.5 ? 1 : 0;
}


// ── Scroll Event Handlers ──────────────────────────────────
// Use requestAnimationFrame for smooth 60fps scroll animations
function handleScroll() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(() => { updateMorphOnScroll(); rafId = null; });
}
scrollContainer.addEventListener('scroll', handleScroll, { passive: true });

// Mouse wheel: snap to next/previous section
scrollContainer.addEventListener('wheel', (e) => {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
        const scrollTop = scrollContainer.scrollTop;
        const windowHeight = window.innerHeight;
        if (e.deltaY > 0 && scrollTop < windowHeight * 0.5) navigateToSection(1);      // Scroll down -> go to login
        else if (e.deltaY < 0 && scrollTop > windowHeight * 0.5) navigateToSection(0);  // Scroll up -> go to intro
    }, 50);
}, { passive: true });

// Touch swipe support (mobile)
let touchStartY = 0, touchEndY = 0;
scrollContainer.addEventListener('touchstart', (e) => { touchStartY = e.touches[0].clientY; }, { passive: true });
scrollContainer.addEventListener('touchend', (e) => {
    touchEndY = e.changedTouches[0].clientY;
    const swipeDistance = touchStartY - touchEndY;
    if (swipeDistance > 100 && currentSection === 0) navigateToSection(1);       // Swipe up -> login
    else if (swipeDistance < -100 && currentSection === 1) navigateToSection(0); // Swipe down -> intro
}, { passive: true });

// Smooth-scroll to a section
function navigateToSection(sectionIndex) {
    currentSection = sectionIndex;
    if (currentSection === 1) { document.body.classList.add('scrolled'); sectionLogin.scrollIntoView({ behavior: 'smooth' }); }
    else { document.body.classList.remove('scrolled'); sectionIntro.scrollIntoView({ behavior: 'smooth' }); }
}
scrollIndicator?.addEventListener('click', () => navigateToSection(1));


// ══════════════════════════════════════════════════════════════
// LOGIN FORM SUBMISSION
//
// When the user submits their email and password:
// 1. Send credentials to /api/auth/login
// 2. If successful, store the auth token + user info in localStorage
// 3. Redirect to the dashboard
// ══════════════════════════════════════════════════════════════

document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();  // Prevent default form submission (page reload)

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const btn = document.getElementById('submitBtn');
    const errorMsg = document.getElementById('errorMessage');
    const originalText = btn.innerText;

    // Show loading state
    btn.innerText = 'Signing in...';
    btn.disabled = true;
    errorMsg.textContent = '';

    try {
        // Send login request to the server
        const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();

        if (data.status === 'success') {
            // Save all user data to browser's localStorage
            // This data persists even after closing the browser tab
            localStorage.setItem('chatnct_username', data.username);
            localStorage.setItem('chatnct_is_admin', data.is_admin ? 'true' : 'false');
            localStorage.setItem('chatnct_role', data.role || 'student');
            localStorage.setItem('chatnct_access_token', data.access_token);
            if (data.refresh_token) localStorage.setItem('chatnct_refresh_token', data.refresh_token);
            if (data.user_id) localStorage.setItem('chatnct_user_id', data.user_id);

            // Show welcome notification
            const role = (data.role || 'student').toLowerCase();
            showNotification(data.is_admin ? 'Welcome, Admin! ' : `Welcome back, ${data.username}!`);

            // Redirect to dashboard after a brief delay (so notification is seen)
            setTimeout(() => {
                if (role === 'instructor' || role === 'admin') {
                    localStorage.setItem('chatnct_skip_dashboard', 'true');
                    window.location.href = 'dashboard.html';
                } else {
                    localStorage.removeItem('chatnct_skip_dashboard');
                    window.location.href = 'dashboard.html';
                }
            }, 800);
        } else {
            // Show error message from server
            errorMsg.textContent = data.message || 'Login failed. Please try again.';
        }
    } catch (err) {
        console.error('Login error:', err);
        errorMsg.textContent = 'Connection error to: ' + (API_BASE || 'localhost') + '. Make sure the server is running.';
    } finally {
        // Reset button state regardless of success/failure
        btn.innerText = originalText;
        btn.disabled = false;
    }
});


// ── Login Page Notification ────────────────────────────────
// Separate from common.js notification since login page loads before common.js
function showNotification(text) {
    const message = document.createElement('div');
    message.setAttribute('role', 'alert');
    message.style.cssText = `
        position:fixed; top:20px; left:50%; transform:translateX(-50%);
        background:#5c4eb3; color:white; padding:12px 24px;
        border-radius:12px; font-weight:bold;
        box-shadow:0 10px 20px rgba(0,0,0,0.3); z-index:10001;
        animation:fadeInUp 0.4s ease; max-width:90vw;
    `;
    message.innerText = text;
    document.body.appendChild(message);
    setTimeout(() => {
        message.style.opacity = '0';
        message.style.transition = 'opacity 0.5s';
        setTimeout(() => message.remove(), 500);
    }, 3000);
}


// ── Page Initialization ────────────────────────────────────

// Show scroll indicator with animation after 3 seconds
setTimeout(() => {
    if (scrollIndicator && currentSection === 0) {
        scrollIndicator.style.animation = 'fadeInUp 0.5s ease';
    }
}, 3000);

// Run morph calculation on page load
updateMorphOnScroll();

// Robot follows mouse cursor on desktop (3D tilt effect)
if (window.matchMedia("(min-width: 901px)").matches) {
    document.addEventListener('mousemove', (e) => {
        const robot = document.querySelector('.robot-container');
        if (robot && currentSection === 1) {
            const xAxis = (window.innerWidth / 2 - e.pageX) / 50;
            const yAxis = (window.innerHeight / 2 - e.pageY) / 50;
            robot.style.transform = `rotateY(${xAxis}deg) rotateX(${yAxis}deg)`;
        }
    });
}

// Arrow keys navigate between sections
document.addEventListener('keydown', (e) => {
    const scrollTop = scrollContainer.scrollTop;
    const windowHeight = window.innerHeight;
    if (e.key === 'ArrowDown' && scrollTop < windowHeight * 0.5) navigateToSection(1);
    else if (e.key === 'ArrowUp' && scrollTop > windowHeight * 0.5) navigateToSection(0);
});
