// ══════════════════════════════════════════════════════════════
// instructor.js - Instructor Panel Logic
//
// This page is only accessible to instructors and admins.
// It provides tools for managing attendance sessions:
//
//   1. START SESSION: Create a new attendance session for a course.
//      This generates a unique session code and QR code.
//
//   2. QR CODE GENERATION: A QR code is displayed that students scan
//      with their phones. The QR code automatically refreshes every
//      5 seconds with a new one-time token (prevents screenshots).
//
//   3. LIVE ATTENDANCE REPORT: Shows a real-time table of students
//      who have successfully verified their identity and marked
//      attendance. Updates every 5 seconds.
//
//   4. EXPORT: Download the QR code as an image, or export the
//      attendance report as a CSV file.
//
//   5. CLOSE SESSION: End the attendance session so no more
//      students can mark attendance.
// ══════════════════════════════════════════════════════════════

// ── Access Control ─────────────────────────────────────────
// Students shouldn't be on this page - redirect them to chat
if (getRole() === 'student') {
    window.location.href = 'chat.html';
}

// ── State Variables ────────────────────────────────────────
let currentSessionCode = null;    // The active session's unique code (e.g. "A7B3X9")
let reportInterval = null;        // Timer ID for polling attendance report
let qrRefreshInterval = null;     // Timer ID for rotating QR tokens
let currentReportData = [];       // Stores latest report data for CSV export

// ── DOM Element References ─────────────────────────────────
const courseSelect = document.getElementById('courseSelect');
const startBtn = document.getElementById('startSessionBtn');
const closeBtn = document.getElementById('closeSessionBtn');
const downloadBtn = document.getElementById('downloadQrBtn');
const qrDisplay = document.getElementById('qrDisplay');
const sessionInfo = document.getElementById('sessionInfo');
const attendanceTable = document.getElementById('attendanceTable');
const attendanceBody = document.getElementById('attendanceBody');
const sessionStatus = document.getElementById('sessionStatus');


// ══════════════════════════════════════════════════════════════
// LOAD COURSES
//
// Fetches the list of courses from the server and populates
// the dropdown menu. The instructor picks a course before
// starting an attendance session.
// ══════════════════════════════════════════════════════════════

async function loadCourses() {
    try {
        const response = await fetch(`${API_BASE}/api/courses`);
        const data = await response.json();

        // The API might return courses as an array or inside an object
        const courses = Array.isArray(data) ? data : (data.courses || []);

        courses.forEach(course => {
            const option = document.createElement('option');
            option.value = course.course_id || course.id;
            const cName = course.course_name || course.name;
            const codePrint = course.course_code ? `${course.course_code} — ` : "";
            option.textContent = `${codePrint}${cName}`;
            courseSelect.appendChild(option);
        });
    } catch (err) {
        console.error('Failed to load courses:', err);
        showNotification('Cannot load courses - is the attendance server running?', 'error');
    }
}


// ══════════════════════════════════════════════════════════════
// START ATTENDANCE SESSION
//
// Creates a new session on the server for the selected course.
// The server returns a unique session code, which is used to
// generate a QR code that students scan.
// ══════════════════════════════════════════════════════════════

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
            startReportPolling();       // Start live attendance updates
            showNotification('Session started!', 'success');
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


// ══════════════════════════════════════════════════════════════
// QR CODE GENERATION (Rotating Tokens)
//
// The QR code contains a URL like:
//   https://localhost:5000/attendance.html?code=A7B3X9&token=abc123&t=1234567
//
// The token changes every 5 seconds to prevent:
//   - Screenshots being shared (old token = invalid)
//   - Re-scanning from a saved photo
//
// Students scan the QR code, which opens the attendance page
// with the session code and token pre-filled.
// ══════════════════════════════════════════════════════════════

function generateQRCode(code) {
    _renderQR(code, '', 0);          // Show QR immediately (no token yet)
    startQRRefresh(code);            // Start rotating tokens every 5 seconds
}

function _renderQR(code, token, timestamp) {
    // Build the URL that will be encoded in the QR code
    let qrContent = `${window.location.origin}/attendance.html?code=${code}`;
    if (token) {
        qrContent += `&token=${token}&t=${timestamp}`;
    }

    // Create a white background container and generate the QR code
    qrDisplay.innerHTML = '<div id="qrWrapper" style="background:#ffffff; padding:15px; border-radius:10px; display:inline-block;"></div>';
    const qrWrapper = document.getElementById('qrWrapper');
    new QRCode(qrWrapper, {
        text: qrContent,
        width: 250,
        height: 250,
        colorDark: "#000000",
        colorLight: "#ffffff",
        correctLevel: QRCode.CorrectLevel.L   // Low error correction = smaller QR
    });
}

function startQRRefresh(code) {
    stopQRRefresh();   // Stop any existing timer
    _fetchAndRenderQR(code);                                        // Fetch token immediately
    qrRefreshInterval = setInterval(() => _fetchAndRenderQR(code), 5000);  // Then every 5 seconds
}

function stopQRRefresh() {
    if (qrRefreshInterval) {
        clearInterval(qrRefreshInterval);
        qrRefreshInterval = null;
    }
}

async function _fetchAndRenderQR(code) {
    // Request a fresh one-time token from the server
    try {
        const res = await fetch(`${API_BASE}/api/session/${code}/qr-token`);
        const data = await res.json();
        if (data.status === 'success' && data.token) {
            _renderQR(code, data.token, data.timestamp);
        } else if (data.code === 'SESSION_CLOSED' || data.code === 'SESSION_EXPIRED') {
            stopQRRefresh();
            showNotification('Session has ended. QR code is no longer valid.', 'error');
        }
    } catch (err) {
        console.warn('QR token refresh failed (will retry):', err);
    }
}


// ── Show Session Active UI ─────────────────────────────────
// Updates the UI to show that a session is currently running.
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
    courseSelect.disabled = true;       // Lock course selection during active session
    startBtn.style.display = 'none';   // Hide start button
}


// ══════════════════════════════════════════════════════════════
// CLOSE SESSION
//
// Ends the attendance session. After closing:
//   - No more students can mark attendance
//   - QR code stops refreshing
//   - Report polling stops
//   - UI resets to allow starting a new session
// ══════════════════════════════════════════════════════════════

closeBtn.addEventListener('click', async () => {
    if (!currentSessionCode) return;

    closeBtn.disabled = true;
    try {
        await fetch(`${API_BASE}/api/session/${currentSessionCode}/close`, { method: 'POST' });
        showNotification('Session closed', 'success');
    } catch (err) {
        console.error('Close session error:', err);
    }

    // Reset all state and UI back to initial
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


// ── Download QR Code as Image ──────────────────────────────
downloadBtn.addEventListener('click', () => {
    const canvas = qrDisplay.querySelector('canvas');
    if (canvas) {
        const link = document.createElement('a');
        link.download = `attendance-qr-${currentSessionCode}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
        showNotification('QR Code downloaded!', 'success');
    }
});


// ══════════════════════════════════════════════════════════════
// CSV EXPORT
//
// Exports the current attendance report as a CSV file.
// Includes UTF-8 BOM marker so Excel correctly displays
// Arabic characters and special text.
// ══════════════════════════════════════════════════════════════

const downloadCsvBtn = document.getElementById('downloadCsvBtn');
if (downloadCsvBtn) {
    downloadCsvBtn.addEventListener('click', () => {
        if (!currentReportData || currentReportData.length === 0) {
            return showNotification('No attendance data available to export.', 'error');
        }

        // UTF-8 BOM (Byte Order Mark) tells Excel to use UTF-8 encoding
        let csvContent = "\uFEFF";
        csvContent += "Index,Student ID,Student Name,Time\n";

        currentReportData.forEach((record, index) => {
            const studentId = record.student_code || record.student_id;
            const studentName = record.student_name ? `"${record.student_name}"` : "—";
            const time = record.time || record.timestamp || record.created_at || "—";
            const safeTime = `"${time.replace(/"/g, '""')}"`;  // Escape quotes in CSV

            csvContent += `${index + 1},${studentId},${studentName},${safeTime}\n`;
        });

        // Create a downloadable file and trigger the download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", `attendance_report_${currentSessionCode}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        showNotification('CSV Report downloaded!', 'success');
    });
}


// ══════════════════════════════════════════════════════════════
// LIVE ATTENDANCE REPORT
//
// Polls the server every 5 seconds to get the latest list of
// students who have marked attendance. Updates the table in
// real-time so the instructor can see who's present.
// ══════════════════════════════════════════════════════════════

function startReportPolling() {
    fetchReport();                              // Fetch immediately
    reportInterval = setInterval(fetchReport, 5000);  // Then every 5 seconds
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
            // Save for CSV export
            currentReportData = data.attendance;

            // Show the attendance table
            attendanceTable.style.display = 'block';
            attendanceBody.innerHTML = '';

            // Add a row for each student who marked attendance
            data.attendance.forEach((record, index) => {
                const row = document.createElement('tr');
                const studentId = record.student_code || record.student_id;
                const timeStr = record.time || record.timestamp || record.created_at || '—';
                row.innerHTML = `
                    <td>${index + 1}</td>
                    <td>${studentId}</td>
                    <td>${record.student_name || '—'}</td>
                    <td>${timeStr}</td>
                `;
                attendanceBody.appendChild(row);
            });

            // Update the student count badge
            const counter = document.getElementById('attendanceCount');
            if (counter) counter.textContent = data.attendance.length;
        }
    } catch (err) {
        console.error('Report fetch error:', err);
    }
}


// ── Page Initialization ────────────────────────────────────
// Load the list of courses when the page finishes loading
document.addEventListener('DOMContentLoaded', loadCourses);
