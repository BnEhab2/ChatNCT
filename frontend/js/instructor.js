// ══════════════════════════════════════════════════════════════
// ChatNCT — Instructor Panel (QR Generation + Session Mgmt)
// ══════════════════════════════════════════════════════════════

let currentSessionCode = null;
let reportInterval = null;

const courseSelect = document.getElementById('courseSelect');
const startBtn = document.getElementById('startSessionBtn');
const closeBtn = document.getElementById('closeSessionBtn');
const downloadBtn = document.getElementById('downloadQrBtn');
const qrDisplay = document.getElementById('qrDisplay');
const sessionInfo = document.getElementById('sessionInfo');
const attendanceTable = document.getElementById('attendanceTable');
const attendanceBody = document.getElementById('attendanceBody');
const sessionStatus = document.getElementById('sessionStatus');

// ── Load Courses ───────────────────────────────────────────
async function loadCourses() {
    try {
        const response = await fetch('/api/courses');
        const data = await response.json();
        if (Array.isArray(data)) {
            data.forEach(course => {
                const option = document.createElement('option');
                option.value = course.course_id || course.id;
                const cName = course.course_name || course.name;
                const codePrint = course.course_code ? `${course.course_code} — ` : "";
                option.textContent = `${codePrint}${cName}`;
                courseSelect.appendChild(option);
            });
        } else if (data.courses) {
            data.courses.forEach(course => {
                const option = document.createElement('option');
                option.value = course.course_id || course.id;
                const cName = course.course_name || course.name;
                const codePrint = course.course_code ? `${course.course_code} — ` : "";
                option.textContent = `${codePrint}${cName}`;
                courseSelect.appendChild(option);
            });
        }
    } catch (err) {
        console.error('Failed to load courses:', err);
        showNotification('Cannot load courses — is the attendance server running?', 'error');
    }
}

// ── Start Session ──────────────────────────────────────────
startBtn.addEventListener('click', async () => {
    const courseId = courseSelect.value;
    if (!courseId) {
        showNotification('Please select a course first', 'error');
        return;
    }

    startBtn.disabled = true;
    startBtn.textContent = 'Creating...';

    try {
        const response = await fetch('/api/session/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ course_id: courseId })
        });
        const data = await response.json();

        if (data.code || data.session_code) {
            currentSessionCode = data.code || data.session_code;
            showSessionActive(currentSessionCode, courseSelect.options[courseSelect.selectedIndex].text);
            generateQRCode(currentSessionCode);
            startReportPolling();
            showNotification('Session started! 🎉', 'success');
        } else {
            showNotification(data.message || 'Failed to create session', 'error');
        }
    } catch (err) {
        console.error('Create session error:', err);
        showNotification('Connection error', 'error');
    } finally {
        startBtn.disabled = false;
        startBtn.textContent = 'Start Session';
    }
});

// ── Generate QR Code ───────────────────────────────────────
function generateQRCode(code) {
    // Use the attendance URL as QR content
    const qrContent = `${window.location.origin}/attendance.html?code=${code}`;

    qrDisplay.innerHTML = '';
    new QRCode(qrDisplay, {
        text: qrContent,
        width: 280,
        height: 280,
        colorDark: "#1a173a",
        colorLight: "#e0d8fe",
        correctLevel: QRCode.CorrectLevel.H
    });
}

// ── Show Session Active ────────────────────────────────────
function showSessionActive(code, courseName) {
    sessionInfo.style.display = 'block';
    sessionStatus.innerHTML = `
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:10px;">
            <span style="width:10px; height:10px; border-radius:50%; background:#22c55e; box-shadow:0 0 8px #22c55e;"></span>
            <strong style="color:#22c55e;">Session Active</strong>
        </div>
        <p style="color:#ddd8fd; font-size:14px;">Course: ${courseName}</p>
        <p style="color:#b0a9ff; font-size:20px; font-weight:700; letter-spacing:3px; margin:10px 0;">Code: ${code}</p>
    `;
    closeBtn.style.display = 'flex';
    downloadBtn.style.display = 'flex';
    courseSelect.disabled = true;
    startBtn.style.display = 'none';
}

// ── Close Session ──────────────────────────────────────────
closeBtn.addEventListener('click', async () => {
    if (!currentSessionCode) return;

    closeBtn.disabled = true;
    try {
        await fetch(`/api/session/${currentSessionCode}/close`, { method: 'POST' });
        showNotification('Session closed ✅', 'success');
    } catch (err) {
        console.error('Close session error:', err);
    }

    // Reset UI
    stopReportPolling();
    currentSessionCode = null;
    sessionInfo.style.display = 'none';
    qrDisplay.innerHTML = '<div class="qr-placeholder-icon"><i class="fas fa-qrcode"></i><p>QR will appear here</p></div>';
    closeBtn.style.display = 'none';
    downloadBtn.style.display = 'none';
    courseSelect.disabled = false;
    startBtn.style.display = 'flex';
    attendanceTable.style.display = 'none';
    closeBtn.disabled = false;
});

// ── Download QR ────────────────────────────────────────────
downloadBtn.addEventListener('click', () => {
    const canvas = qrDisplay.querySelector('canvas');
    if (canvas) {
        const link = document.createElement('a');
        link.download = `attendance-qr-${currentSessionCode}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
        showNotification('QR Code downloaded! 📥', 'success');
    }
});

// ── Live Report Polling ────────────────────────────────────
function startReportPolling() {
    fetchReport();
    reportInterval = setInterval(fetchReport, 5000);
}

function stopReportPolling() {
    if (reportInterval) {
        clearInterval(reportInterval);
        reportInterval = null;
    }
}

async function fetchReport() {
    if (!currentSessionCode) return;
    try {
        const response = await fetch(`/api/session/${currentSessionCode}/report`);
        const data = await response.json();

        if (data.attendance && data.attendance.length > 0) {
            attendanceTable.style.display = 'block';
            attendanceBody.innerHTML = '';
            data.attendance.forEach((record, index) => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${index + 1}</td>
                    <td>${record.student_id}</td>
                    <td>${record.student_name || '—'}</td>
                    <td>${record.time || record.timestamp || '—'}</td>
                    <td><span style="color:#22c55e;">✅</span></td>
                `;
                attendanceBody.appendChild(row);
            });

            // Update counter
            const counter = document.getElementById('attendanceCount');
            if (counter) counter.textContent = data.attendance.length;
        }
    } catch (err) {
        console.error('Report fetch error:', err);
    }
}

// ── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', loadCourses);
