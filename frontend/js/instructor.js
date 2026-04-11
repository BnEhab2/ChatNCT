

// ══════════════════════════════════════════════════════════════
// ChatNCT — Instructor Panel (QR Generation + Session Mgmt)
// ══════════════════════════════════════════════════════════════

if (getRole() === 'student') {
    window.location.href = 'chat.html';
}

let currentSessionCode = null;
let reportInterval = null;
let qrRefreshInterval = null;
let currentReportData = [];

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
        const response = await fetch(`${API_BASE}/api/courses`);
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
        const response = await fetch(`${API_BASE}/api/session/create`, {
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
            showNotification('Session started! ', 'success');
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

// ── Generate QR Code (Feature 2: Rotating every 5s) ───────
function generateQRCode(code) {
    // Initial render
    _renderQR(code, '', 0);
    // Start rotating QR tokens every 5 seconds
    startQRRefresh(code);
}

function _renderQR(code, token, timestamp) {
    let qrContent = `${window.location.origin}/attendance.html?code=${code}`;
    if (token) {
        qrContent += `&token=${token}&t=${timestamp}`;
    }
    qrDisplay.innerHTML = '<div id="qrWrapper" style="background:#ffffff; padding:15px; border-radius:10px; display:inline-block;"></div>';
    const qrWrapper = document.getElementById('qrWrapper');
    new QRCode(qrWrapper, {
        text: qrContent,
        width: 250,
        height: 250,
        colorDark: "#000000",
        colorLight: "#ffffff",
        correctLevel: QRCode.CorrectLevel.L
    });
}

function startQRRefresh(code) {
    stopQRRefresh();
    _fetchAndRenderQR(code);
    qrRefreshInterval = setInterval(() => _fetchAndRenderQR(code), 5000);
}

function stopQRRefresh() {
    if (qrRefreshInterval) {
        clearInterval(qrRefreshInterval);
        qrRefreshInterval = null;
    }
}

async function _fetchAndRenderQR(code) {
    try {
        const res = await fetch(`${API_BASE}/api/session/${code}/qr-token`);
        const data = await res.json();
        if (data.status === 'success' && data.token) {
            _renderQR(code, data.token, data.timestamp);
        } else if (data.code === 'SESSION_CLOSED' || data.code === 'SESSION_EXPIRED') {
            // Session ended — stop refreshing and notify
            stopQRRefresh();
            showNotification('Session has ended. QR code is no longer valid.', 'error');
        }
    } catch (err) {
        console.warn('QR token refresh failed (will retry):', err);
    }
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
        await fetch(`${API_BASE}/api/session/${currentSessionCode}/close`, { method: 'POST' });
        showNotification('Session closed ', 'success');
    } catch (err) {
        console.error('Close session error:', err);
    }

    // Reset UI
    stopReportPolling();
    stopQRRefresh();
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
        showNotification('QR Code downloaded! ', 'success');
    }
});

// ── Download CSV ───────────────────────────────────────────
const downloadCsvBtn = document.getElementById('downloadCsvBtn');
if (downloadCsvBtn) {
    downloadCsvBtn.addEventListener('click', () => {
        if (!currentReportData || currentReportData.length === 0) {
            return showNotification('No attendance data available to export.', 'error');
        }
        
        // Add UTF-8 BOM for Excel to properly display Arabic/special chars
        let csvContent = "\uFEFF"; 
        csvContent += "Index,Student ID,Student Name,Time,Status\n";
        
        currentReportData.forEach((record, index) => {
            const studentId = record.student_code || record.student_id;
            const studentName = record.student_name ? `"${record.student_name}"` : "—";
            const time = record.time || record.timestamp || record.created_at || "—";
            // Strip commas from time and name to prevent CSV breaks just in case
            const safeTime = `"${time.replace(/"/g, '""')}"`;
            
            csvContent += `${index + 1},${studentId},${studentName},${safeTime},Present\n`;
        });
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", `attendance_report_${currentSessionCode}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showNotification('CSV Report downloaded! ', 'success');
    });
}

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
        const response = await fetch(`${API_BASE}/api/session/${currentSessionCode}/report`);
        const data = await response.json();

        if (data.attendance && data.attendance.length > 0) {
            currentReportData = data.attendance;
            attendanceTable.style.display = 'block';
            attendanceBody.innerHTML = '';
            data.attendance.forEach((record, index) => {
                const row = document.createElement('tr');
                const studentId = record.student_code || record.student_id;
                const timeStr = record.time || record.timestamp || record.created_at || '—';
                row.innerHTML = `
                    <td>${index + 1}</td>
                    <td>${studentId}</td>
                    <td>${record.student_name || '—'}</td>
                    <td>${timeStr}</td>
                    <td><span style="color:#22c55e;"></span></td>
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
