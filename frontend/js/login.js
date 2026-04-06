// ══════════════════════════════════════════════════════════════
// ChatNCT — Login Page Logic
// ══════════════════════════════════════════════════════════════

const scrollContainer = document.getElementById('scrollContainer');
const morphLogo = document.getElementById('morphLogo');
const introTagline = document.getElementById('introTagline');
const scrollIndicator = document.getElementById('scrollIndicator');
const robotContainer = document.getElementById('robotContainer');
const welcomeText = document.getElementById('welcomeText');
const loginCard = document.getElementById('loginCard');
const sectionIntro = document.getElementById('section-intro');
const sectionLogin = document.getElementById('section-login');

let currentSection = 0, scrollTimeout, rafId = null;

// ── Scroll & Morph Logic ───────────────────────────────────
function updateMorphOnScroll() {
    const scrollTop = scrollContainer.scrollTop;
    const windowHeight = window.innerHeight;
    const progress = Math.min(Math.max(scrollTop / windowHeight, 0), 1);
    let endLeft = 12, endScale = 0.85;
    if (window.innerWidth <= 480) { endLeft = 20; endScale = 0.88; }
    else if (window.innerWidth <= 768) { endLeft = 15; endScale = 0.32; }
    const startTop = 50, endTop = 8, startLeft = 50, startScale = 1;
    const currentTop = startTop - (progress * (startTop - endTop));
    const currentLeft = startLeft - (progress * (startLeft - endLeft));
    const currentScale = startScale - (progress * (startScale - endScale));
    const currentOpacity = 1 - (progress * 0.3);
    const currentGlow = 30 - (progress * 20);
    morphLogo.style.top = `${currentTop}%`;
    morphLogo.style.left = `${currentLeft}%`;
    morphLogo.style.transform = `translate(-50%, -50%) scale(${currentScale})`;
    morphLogo.style.opacity = currentOpacity;
    morphLogo.style.filter = `drop-shadow(0 0 ${currentGlow}px rgba(124,102,227,${0.8 - progress * 0.3}))`;
    if (introTagline) introTagline.style.opacity = 1 - progress;
    const fadeStart = 0.5;
    [robotContainer, welcomeText, loginCard].forEach(el => {
        if (el) {
            const opacity = progress > fadeStart ? (progress - fadeStart) * 2 : 0;
            el.style.opacity = opacity;
            el.classList.toggle('visible', progress > 0.8);
        }
    });
    if (scrollIndicator) {
        if (progress >= 0.5) { scrollIndicator.style.opacity = '0'; scrollIndicator.style.pointerEvents = 'none'; }
        else { scrollIndicator.style.opacity = '1'; scrollIndicator.style.pointerEvents = 'auto'; }
    }
    currentSection = progress > 0.5 ? 1 : 0;
}

function handleScroll() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(() => { updateMorphOnScroll(); rafId = null; });
}
scrollContainer.addEventListener('scroll', handleScroll, { passive: true });
scrollContainer.addEventListener('wheel', (e) => {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
        const scrollTop = scrollContainer.scrollTop;
        const windowHeight = window.innerHeight;
        if (e.deltaY > 0 && scrollTop < windowHeight * 0.5) navigateToSection(1);
        else if (e.deltaY < 0 && scrollTop > windowHeight * 0.5) navigateToSection(0);
    }, 50);
}, { passive: true });

let touchStartY = 0, touchEndY = 0;
scrollContainer.addEventListener('touchstart', (e) => { touchStartY = e.touches[0].clientY; }, { passive: true });
scrollContainer.addEventListener('touchend', (e) => {
    touchEndY = e.changedTouches[0].clientY;
    const swipeDistance = touchStartY - touchEndY;
    if (swipeDistance > 100 && currentSection === 0) navigateToSection(1);
    else if (swipeDistance < -100 && currentSection === 1) navigateToSection(0);
}, { passive: true });

function navigateToSection(sectionIndex) {
    currentSection = sectionIndex;
    if (currentSection === 1) { document.body.classList.add('scrolled'); sectionLogin.scrollIntoView({ behavior: 'smooth' }); }
    else { document.body.classList.remove('scrolled'); sectionIntro.scrollIntoView({ behavior: 'smooth' }); }
}
scrollIndicator?.addEventListener('click', () => navigateToSection(1));

// ── Login Logic (API-based) ────────────────────────────────
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const btn = document.getElementById('submitBtn');
    const errorMsg = document.getElementById('errorMessage');
    const originalText = btn.innerText;

    btn.innerText = 'Signing in...';
    btn.disabled = true;
    errorMsg.textContent = '';

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();

        if (data.status === 'success') {
            localStorage.setItem('chatnct_username', data.username);
            localStorage.setItem('chatnct_is_admin', data.is_admin ? 'true' : 'false');
            localStorage.setItem('chatnct_role', data.role || 'student');

            const role = (data.role || 'student').toLowerCase();
            showNotification(data.is_admin ? 'Welcome, Admin! 🎯' : `Welcome back, ${data.username}!`);

            setTimeout(() => {
                if (role === 'instructor' || role === 'admin') {
                    localStorage.setItem('chatnct_skip_dashboard', 'true');
                    window.location.href = 'instructor.html';
                } else {
                    localStorage.removeItem('chatnct_skip_dashboard');
                    window.location.href = 'chat.html';
                }
            }, 800);
        } else {
            errorMsg.textContent = data.message || 'Login failed. Please try again.';
        }
    } catch (err) {
        console.error('Login error:', err);
        errorMsg.textContent = 'Connection error. Make sure the server is running.';
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
});

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

// ── Init ───────────────────────────────────────────────────
setTimeout(() => {
    if (scrollIndicator && currentSection === 0) {
        scrollIndicator.style.animation = 'fadeInUp 0.5s ease';
    }
}, 3000);
updateMorphOnScroll();

// Mouse follow effect (desktop)
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

// Keyboard navigation
document.addEventListener('keydown', (e) => {
    const scrollTop = scrollContainer.scrollTop;
    const windowHeight = window.innerHeight;
    if (e.key === 'ArrowDown' && scrollTop < windowHeight * 0.5) navigateToSection(1);
    else if (e.key === 'ArrowUp' && scrollTop > windowHeight * 0.5) navigateToSection(0);
});
