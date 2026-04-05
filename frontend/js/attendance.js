// ══════════════════════════════════════════════════════════════
// ChatNCT — Student Attendance (QR Scanner + Face Verify)
// ══════════════════════════════════════════════════════════════

let html5QrCode = null;
let currentStream = null;

const qrScanner = document.getElementById('qrScanner');
const qrPlaceholder = document.getElementById('qrPlaceholder');
const statusText = document.getElementById('statusText');
const cameraBtn = document.getElementById('cameraBtn');
const resultCard = document.getElementById('resultCard');

// ── Start QR Scanner ───────────────────────────────────────
async function startQrScanner() {
    // Hide placeholder, show scanner
    if (qrPlaceholder) qrPlaceholder.style.display = 'none';
    cameraBtn.textContent = 'Scanning...';
    cameraBtn.disabled = true;
    statusText.textContent = 'Scanning for QR code...';

    try {
        html5QrCode = new Html5Qrcode("qrReader");
        await html5QrCode.start(
            { facingMode: "environment" },
            { fps: 10, qrbox: { width: 250, height: 250 } },
            onQrCodeSuccess,
            onQrCodeError
        );
    } catch (err) {
        console.error('QR Scanner error:', err);
        statusText.textContent = 'Camera error. Please allow camera access.';
        cameraBtn.textContent = 'Try Again';
        cameraBtn.disabled = false;
        if (qrPlaceholder) qrPlaceholder.style.display = 'flex';
    }
}

function onQrCodeError(errorMessage) {
    // Silently ignore scan errors (normal during scanning)
}

async function onQrCodeSuccess(decodedText) {
    // Stop scanner
    if (html5QrCode) {
        await html5QrCode.stop();
        html5QrCode = null;
    }

    statusText.textContent = 'QR Code found! Verifying session...';
    const sessionCode = decodedText.trim();

    // Verify session
    try {
        const response = await fetch(`/api/session/${sessionCode}`);
        const data = await response.json();

        if (data.status === 'active') {
            statusText.textContent = `Session: ${data.course_name || sessionCode} — Enter your Student ID`;
            showStudentIdForm(sessionCode, data.course_name || 'Unknown');
        } else {
            showResult('error', 'Session expired or invalid.');
            resetScanner();
        }
    } catch (err) {
        console.error('Session check error:', err);
        showResult('error', 'Cannot connect to server.');
        resetScanner();
    }
}

// ── Student ID Form ────────────────────────────────────────
function showStudentIdForm(sessionCode, courseName) {
    const formHtml = `
        <div class="id-form" id="idForm">
            <h3 style="color:#e0d8fe; margin-bottom:10px; font-size:18px;">📚 ${courseName}</h3>
            <input type="text" id="studentIdInput" placeholder="Enter your Student ID"
                style="width:100%; padding:14px 20px; border-radius:15px; border:2px solid rgba(124,102,227,0.4);
                background:rgba(62,58,131,0.8); color:#fff; font-family:'Montserrat',sans-serif;
                font-size:16px; outline:none; margin-bottom:15px;">
            <button onclick="startFaceVerify('${sessionCode}')" class="camera-btn" style="width:100%;">
                <i class="fas fa-camera"></i> Take Selfie & Verify
            </button>
        </div>
    `;

    if (resultCard) {
        resultCard.innerHTML = formHtml;
        resultCard.style.display = 'block';
    }
}

// ── Face Verification ──────────────────────────────────────
async function startFaceVerify(sessionCode) {
    const studentId = document.getElementById('studentIdInput')?.value.trim();
    if (!studentId) {
        showNotification('Please enter your Student ID', 'error');
        return;
    }

    statusText.textContent = 'Opening camera for selfie...';

    const cameraModal = document.getElementById('cameraModal');
    const videoElement = document.getElementById('videoElement');

    try {
        cameraModal.classList.add('active');
        currentStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }
        });
        videoElement.srcObject = currentStream;

        // Add capture button
        const captureBtn = document.getElementById('captureBtn');
        captureBtn.onclick = () => captureAndVerify(sessionCode, studentId);
        captureBtn.style.display = 'flex';
    } catch (err) {
        console.error('Camera error:', err);
        showNotification('Unable to access camera', 'error');
        cameraModal.classList.remove('active');
    }
}

async function captureAndVerify(sessionCode, studentId) {
    const videoElement = document.getElementById('videoElement');
    const canvas = document.createElement('canvas');
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    canvas.getContext('2d').drawImage(videoElement, 0, 0);

    const imageData = canvas.toDataURL('image/jpeg', 0.8);

    // Stop camera
    stopCamera();
    statusText.textContent = 'Verifying face...';

    try {
        const response = await fetch('/api/attendance/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_code: sessionCode,
                student_id: studentId,
                image: imageData
            })
        });
        const data = await response.json();

        if (data.status === 'success') {
            showResult('success', `✅ Attendance recorded!\nStudent: ${data.student_name || studentId}`);
        } else {
            showResult('error', `❌ ${data.message || 'Verification failed'}`);
        }
    } catch (err) {
        console.error('Verify error:', err);
        showResult('error', 'Server connection error');
    }
}

function stopCamera() {
    if (currentStream) {
        currentStream.getTracks().forEach(track => track.stop());
        currentStream = null;
    }
    const cameraModal = document.getElementById('cameraModal');
    const videoElement = document.getElementById('videoElement');
    if (cameraModal) cameraModal.classList.remove('active');
    if (videoElement) videoElement.srcObject = null;
}

// ── Result Display ─────────────────────────────────────────
function showResult(type, message) {
    const icon = type === 'success' ? '✅' : '❌';
    const color = type === 'success' ? '#22c55e' : '#ef4444';
    if (resultCard) {
        resultCard.innerHTML = `
            <div style="text-align:center; padding:20px;">
                <div style="font-size:48px; margin-bottom:15px;">${icon}</div>
                <p style="color:${color}; font-size:18px; font-weight:600; white-space:pre-line;">${message}</p>
                <button onclick="resetScanner()" class="camera-btn" style="width:auto; margin-top:20px; padding:12px 30px;">
                    <i class="fas fa-redo"></i> Scan Again
                </button>
            </div>
        `;
        resultCard.style.display = 'block';
    }
    statusText.textContent = type === 'success' ? 'Attendance recorded!' : 'Verification failed';
}

function resetScanner() {
    if (resultCard) { resultCard.innerHTML = ''; resultCard.style.display = 'none'; }
    if (qrPlaceholder) qrPlaceholder.style.display = 'flex';
    statusText.textContent = 'Point your camera at the QR code';
    cameraBtn.textContent = 'Open Camera';
    cameraBtn.disabled = false;

    // Clear QR reader div
    const qrReader = document.getElementById('qrReader');
    if (qrReader) qrReader.innerHTML = '';
}

// ── Init ───────────────────────────────────────────────────
cameraBtn.addEventListener('click', startQrScanner);
document.getElementById('closeCamera')?.addEventListener('click', stopCamera);

document.getElementById('cameraModal')?.addEventListener('click', (e) => {
    if (e.target === document.getElementById('cameraModal')) stopCamera();
});
