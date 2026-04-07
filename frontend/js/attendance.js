// ══════════════════════════════════════════════════════════════
// ChatNCT — Student Attendance (QR Scanner + Multi-Frame Face + Liveness)
// Features: 2 (QR Token), 3 (Multi-Frame), 4 (Liveness), 7 (Device FP)
// ══════════════════════════════════════════════════════════════

if (getRole() === 'instructor' || getRole() === 'admin') {
    window.location.href = 'instructor.html';
}

let html5QrCode = null;
let currentStream = null;
let currentQrToken = null;  // Feature 2: rotating token

const qrScanner = document.getElementById('qrScanner');
const qrPlaceholder = document.getElementById('qrPlaceholder');
const statusText = document.getElementById('statusText');
const cameraBtn = document.getElementById('cameraBtn');
const resultCard = document.getElementById('resultCard');

// ── Feature 7: Device Fingerprint ─────────────────────────
function getDeviceFingerprint() {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.textBaseline = 'top';
    ctx.font = '14px Arial';
    ctx.fillText('fp', 2, 2);
    const fp = canvas.toDataURL().slice(-50) + navigator.language + screen.width + screen.height;
    let hash = 0;
    for (let i = 0; i < fp.length; i++) {
        hash = ((hash << 5) - hash) + fp.charCodeAt(i);
        hash |= 0;
    }
    return Math.abs(hash).toString(36);
}

// ── Start QR Scanner ──────────────────────────────────────
async function startQrScanner() {
    if (qrPlaceholder) qrPlaceholder.style.display = 'none';
    cameraBtn.textContent = 'Scanning...';
    cameraBtn.disabled = true;
    statusText.textContent = 'Scanning for QR code...';

    try {
        html5QrCode = new Html5Qrcode("qrReader");
        await html5QrCode.start(
            { facingMode: "environment" },
            { fps: 10 },
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
    alert("QR Detected! " + decodedText);
    
    if (html5QrCode) {
        try { await html5QrCode.stop(); } catch(e){ console.error(e); }
        html5QrCode = null;
    }

    statusText.textContent = 'QR Code found! Verifying session...';

    // Extract session code + token from URL (Feature 2)
    let sessionCode = decodedText.trim();
    currentQrToken = null;

    try {
        const url = new URL(sessionCode);
        const codeParam = url.searchParams.get('code');
        const tokenParam = url.searchParams.get('token');
        if (codeParam) sessionCode = codeParam;
        if (tokenParam) currentQrToken = tokenParam;
    } catch (_) {
        // Not a URL, use as-is
    }

    // Verify session
    try {
        const response = await fetch(`/api/session/${sessionCode}`);
        const data = await response.json();

        if (data.status === 'success' || data.status === 'active') {
            statusText.textContent = `Session: ${data.course_name || sessionCode} — Enter your Student ID`;
            showStudentIdForm(sessionCode, data.course_name || 'Unknown');
        } else {
            showResult('error', data.message || 'Session expired or invalid.');
            resetScanner();
        }
    } catch (err) {
        console.error('Session check error:', err);
        showResult('error', 'Cannot connect to server.');
        resetScanner();
    }
}

// ── Student ID Form ───────────────────────────────────────
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

// ── Feature 3+4: Multi-Frame Capture + Liveness ───────────
async function startFaceVerify(sessionCode) {
    const studentId = document.getElementById('studentIdInput')?.value.trim();
    if (!studentId) {
        showNotification('Please enter your Student ID', 'error');
        return;
    }

    statusText.textContent = 'Opening camera for liveness check...';

    const cameraModal = document.getElementById('cameraModal');
    const videoElement = document.getElementById('videoElement');

    try {
        cameraModal.classList.add('active');
        currentStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }
        });
        videoElement.srcObject = currentStream;

        // Feature 4: Run liveness challenges first, then multi-frame capture
        const captureBtn = document.getElementById('captureBtn');
        captureBtn.textContent = '📸 Starting liveness check...';
        captureBtn.disabled = true;
        captureBtn.style.display = 'flex';

        // Wait for video to be ready
        await new Promise(resolve => {
            videoElement.onloadedmetadata = resolve;
            setTimeout(resolve, 1000);
        });

        // Run liveness detection
        statusText.textContent = 'Performing liveness check...';
        const livenessResult = await runLivenessCheck(videoElement);

        if (!livenessResult.passed) {
            stopCamera();
            showResult('error', `Liveness check failed: ${livenessResult.reason}`);
            return;
        }

        statusText.textContent = 'Liveness passed! Capturing frames...';

        // Feature 3: Capture multiple frames
        const frames = await captureMultipleFrames(videoElement, 5);

        stopCamera();
        statusText.textContent = 'Verifying face...';

        // Submit verification
        try {
            const response = await fetch('/api/attendance/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_code: sessionCode,
                    student_id: studentId,
                    images: frames,
                    image: frames[0],  // Fallback single image
                    qr_token: currentQrToken || '',
                    liveness_passed: livenessResult.passed,
                    device_fingerprint: getDeviceFingerprint(),
                })
            });
            const data = await response.json();

            if (data.status === 'success') {
                showResult('success', `Attendance recorded!\nStudent: ${data.student_name || studentId}`);
            } else {
                showResult('error', `${data.message || 'Verification failed'}\n${data.code || ''}`);
            }
        } catch (err) {
            console.error('Verify error:', err);
            showResult('error', 'Server connection error');
        }
    } catch (err) {
        console.error('Camera error:', err);
        showNotification('Unable to access camera', 'error');
        cameraModal.classList.remove('active');
    }
}

// ── Feature 3: Capture Multiple Frames ────────────────────
async function captureMultipleFrames(videoElement, count = 5) {
    const frames = [];
    for (let i = 0; i < count; i++) {
        const canvas = document.createElement('canvas');
        canvas.width = videoElement.videoWidth;
        canvas.height = videoElement.videoHeight;
        canvas.getContext('2d').drawImage(videoElement, 0, 0);
        frames.push(canvas.toDataURL('image/jpeg', 0.7));
        // Wait 300ms between frames to get movement
        if (i < count - 1) {
            await new Promise(r => setTimeout(r, 300));
        }
    }
    return frames;
}

// ── Feature 4: Client-Side Liveness Detection ─────────────
async function runLivenessCheck(videoElement) {
    // Fetch random challenges from backend
    let challenges;
    try {
        const res = await fetch('/api/attendance/challenges');
        const data = await res.json();
        challenges = data.challenges || [];
    } catch (e) {
        // Fallback challenges
        challenges = [
            { action: 'blink', label: 'Blink your eyes' },
            { action: 'smile', label: 'Smile' },
        ];
    }

    if (challenges.length === 0) {
        return { passed: true, reason: 'No challenges required' };
    }

    // Simple liveness: check for significant frame changes during each challenge
    for (const challenge of challenges) {
        statusText.textContent = `Liveness: ${challenge.label}`;

        // Show challenge instruction on the video overlay
        _showChallengeOverlay(challenge.label);

        // Wait for user to perform action (3 seconds)
        const moved = await _detectMovementDuring(videoElement, 3000);

        if (!moved) {
            _hideChallengeOverlay();
            return { passed: false, reason: `Failed: ${challenge.label} — no movement detected` };
        }
    }

    _hideChallengeOverlay();
    return { passed: true, reason: 'All challenges passed' };
}

function _showChallengeOverlay(text) {
    let overlay = document.getElementById('livenessOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'livenessOverlay';
        overlay.style.cssText = `
            position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.8); color: #fff; padding: 20px 40px;
            border-radius: 15px; font-size: 24px; font-weight: bold; z-index: 10002;
            font-family: 'Montserrat', sans-serif; text-align: center;
            border: 2px solid rgba(124,102,227,0.6);
        `;
        document.body.appendChild(overlay);
    }
    overlay.textContent = `${text}`;
    overlay.style.display = 'block';
}

function _hideChallengeOverlay() {
    const overlay = document.getElementById('livenessOverlay');
    if (overlay) overlay.style.display = 'none';
}

async function _detectMovementDuring(videoElement, durationMs) {
    const canvas = document.createElement('canvas');
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    const ctx = canvas.getContext('2d');

    // Capture initial frame
    ctx.drawImage(videoElement, 0, 0);
    const initialData = ctx.getImageData(0, 0, canvas.width, canvas.height).data;

    const startTime = Date.now();
    let maxDiff = 0;

    while (Date.now() - startTime < durationMs) {
        await new Promise(r => setTimeout(r, 200));
        ctx.drawImage(videoElement, 0, 0);
        const currentData = ctx.getImageData(0, 0, canvas.width, canvas.height).data;

        // Calculate pixel difference
        let totalDiff = 0;
        const sampleStep = 40;  // Sample every 40 pixels for performance
        let samples = 0;
        for (let i = 0; i < currentData.length; i += sampleStep * 4) {
            totalDiff += Math.abs(currentData[i] - initialData[i]);
            samples++;
        }
        const avgDiff = totalDiff / samples;
        if (avgDiff > maxDiff) maxDiff = avgDiff;

        // Early success if movement detected
        if (maxDiff > 8) return true;
    }

    return maxDiff > 5;
}

// ── Stop Camera ───────────────────────────────────────────
function stopCamera() {
    if (currentStream) {
        currentStream.getTracks().forEach(track => track.stop());
        currentStream = null;
    }
    const cameraModal = document.getElementById('cameraModal');
    const videoElement = document.getElementById('videoElement');
    if (cameraModal) cameraModal.classList.remove('active');
    if (videoElement) videoElement.srcObject = null;
    _hideChallengeOverlay();
}

// ── Result Display ────────────────────────────────────────
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
    currentQrToken = null;

    const qrReader = document.getElementById('qrReader');
    if (qrReader) qrReader.innerHTML = '';
}

// ── Init ──────────────────────────────────────────────────
cameraBtn.addEventListener('click', startQrScanner);
document.getElementById('closeCamera')?.addEventListener('click', stopCamera);

document.getElementById('cameraModal')?.addEventListener('click', (e) => {
    if (e.target === document.getElementById('cameraModal')) stopCamera();
});

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const token = params.get('token');
    if (code) {
        if (token) currentQrToken = token;
        onQrCodeSuccess(code);
    }
});
