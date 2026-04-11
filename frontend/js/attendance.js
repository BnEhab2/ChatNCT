
// ══════════════════════════════════════════════════════════════
// ChatNCT — Student Attendance
// QR Scanner + Fast Identity Check + CLIENT-SIDE Liveness
//
// Liveness detection runs ENTIRELY in the browser using MediaPipe
// FaceLandmarker JS — zero network round-trips for pose detection.
// This gives instant (~60fps) head-pose tracking vs the old
// 300ms+ per-frame server round-trips.
// ══════════════════════════════════════════════════════════════

if (getRole() === 'instructor' || getRole() === 'admin') {
    window.location.href = 'instructor.html';
}

let html5QrCode = null;
let currentStream = null;
let currentQrToken = null;

const qrScanner = document.getElementById('qrScanner');
const qrPlaceholder = document.getElementById('qrPlaceholder');
const statusText = document.getElementById('statusText');
const cameraBtn = document.getElementById('cameraBtn');
const resultCard = document.getElementById('resultCard');


// ══════════════════════════════════════════════════════════════
// CLIENT-SIDE MEDIAPIPE FACE LANDMARKER
//
// Loads MediaPipe Face Landmarker directly in the browser.
// Once loaded, pose detection runs at 60fps with ZERO network
// latency. The model (~3.7 MB) is cached by the browser.
// ══════════════════════════════════════════════════════════════

let faceLandmarker = null;
let mpReady = false;
let mpLoadPromise = null;
let _lastMpTimestamp = -1;

async function initMediaPipe() {
    if (mpReady) return true;
    if (mpLoadPromise) return mpLoadPromise;

    mpLoadPromise = (async () => {
        try {
            console.log("[MP] Loading MediaPipe FaceLandmarker (client-side)...");
            const vision = await import(
                "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs"
            );
            const filesetResolver = await vision.FilesetResolver.forVisionTasks(
                "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
            );
            faceLandmarker = await vision.FaceLandmarker.createFromOptions(filesetResolver, {
                baseOptions: {
                    modelAssetPath:
                        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
                    delegate: "GPU",
                },
                runningMode: "VIDEO",
                numFaces: 1,
                minFaceDetectionConfidence: 0.4,
                minFacePresenceConfidence: 0.4,
            });
            mpReady = true;
            console.log("[OK] MediaPipe FaceLandmarker ready (GPU, client-side)");
            return true;
        } catch (e) {
            console.error("[WARN] MediaPipe load failed:", e);
            mpLoadPromise = null;
            return false;
        }
    })();
    return mpLoadPromise;
}

// Start loading MediaPipe immediately in the background
initMediaPipe();


/**
 * Detect head pose from a live video element using MediaPipe.
 * Runs 100% locally at ~60fps. No network calls.
 *
 * Returns { pose: string, yaw: number, pitch: number } or null.
 */
function detectPoseClientSide(videoElement, timestamp) {
    if (!faceLandmarker || !mpReady) return null;
    // Ensure monotonically increasing timestamps
    if (timestamp <= _lastMpTimestamp) timestamp = _lastMpTimestamp + 1;
    _lastMpTimestamp = timestamp;

    let results;
    try {
        results = faceLandmarker.detectForVideo(videoElement, timestamp);
    } catch (e) {
        return null;
    }

    if (!results.faceLandmarks || results.faceLandmarks.length === 0) return null;

    const lm = results.faceLandmarks[0];
    const nose = lm[1];    // nose tip
    const leftEye = lm[33];   // left eye outer (person's anatomical left)
    const rightEye = lm[263];  // right eye outer
    const forehead = lm[10];   // top of forehead
    const chin = lm[152];  // bottom of chin

    // ── YAW (left/right) ──
    const eyeWidth = rightEye.x - leftEye.x;
    if (Math.abs(eyeWidth) < 0.001) return null;

    const noseRatio = (nose.x - leftEye.x) / eyeWidth;
    const yaw = (noseRatio - 0.5) * 100;

    // ── PITCH (up/down) ──
    const faceHeight = chin.y - forehead.y;
    if (Math.abs(faceHeight) < 0.001) return null;

    const noseVRatio = (nose.y - forehead.y) / faceHeight;
    const pitch = (noseVRatio - 0.45) * 100;

    // ── Classify ──
    const YAW_THRESH = 5;     // Lowered from 8 — much more responsive
    const PITCH_THRESH = 8;

    let pose = 'center';
    if (Math.abs(yaw) < YAW_THRESH && Math.abs(pitch) < PITCH_THRESH) {
        pose = 'center';
    } else if (yaw < -YAW_THRESH) {
        pose = 'left';
    } else if (yaw > YAW_THRESH) {
        pose = 'right';
    } else if (pitch < -PITCH_THRESH) {
        pose = 'up';
    } else if (pitch > PITCH_THRESH) {
        pose = 'down';
    }

    return {
        pose,
        yaw: Math.round(yaw * 10) / 10,
        pitch: Math.round(pitch * 10) / 10,
    };
}


// ══════════════════════════════════════════════════════════════
// HELPERS
// ══════════════════════════════════════════════════════════════

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

function captureFastFrame(videoElement) {
    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = Math.floor(videoElement.videoHeight * (640 / videoElement.videoWidth));
    canvas.getContext('2d').drawImage(videoElement, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.85);
}


// ══════════════════════════════════════════════════════════════
// QR SCANNER
// ══════════════════════════════════════════════════════════════

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
        try { await html5QrCode.stop(); } catch (e) { console.error(e); }
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
        const response = await fetch(`${API_BASE}/api/session/${sessionCode}`);
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


// ══════════════════════════════════════════════════════════════
// STUDENT ID FORM
// ══════════════════════════════════════════════════════════════

function showStudentIdForm(sessionCode, courseName) {
    const formHtml = `
        <div class="id-form" id="idForm">
            <h3 style="color:#e0d8fe; margin-bottom:10px; font-size:18px;"> ${courseName}</h3>
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


// ══════════════════════════════════════════════════════════════
// FACE VERIFY + CLIENT-SIDE LIVENESS
//
// Flow:
//   1. /api/attendance/prepare   — pre-cache embedding (non-blocking)
//   2. Open camera
//   3. Phase 1: Identity check   — send frames to server (cached embedding = fast)
//   4. Phase 2: Liveness         — 100% client-side MediaPipe (60fps, zero latency)
//   5. Phase 3: Record           — send verified frame to server
// ══════════════════════════════════════════════════════════════

async function startFaceVerify(sessionCode) {
    const studentId = document.getElementById('studentIdInput')?.value.trim();
    if (!studentId) {
        showNotification('Please enter your Student ID', 'error');
        return;
    }

    // ── Step 0: Pre-warm server (download photo + cache embedding) ──
    statusText.textContent = 'Preparing verification...';
    try {
        await fetch(`${API_BASE}/api/attendance/prepare`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ student_id: studentId })
        });
    } catch (e) {
        console.warn("Prepare call failed (non-fatal):", e);
    }

    // ── Step 1: Open Camera ──────────────────────────────────
    const cameraModal = document.getElementById('cameraModal');
    const videoElement = document.getElementById('videoElement');

    try {
        cameraModal.classList.add('active');
        currentStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }
        });
        videoElement.srcObject = currentStream;

        document.getElementById('captureBtn').style.display = 'none';

        // Wait for video to be ready
        await new Promise(resolve => {
            videoElement.onloadedmetadata = resolve;
            setTimeout(resolve, 1000);
        });

        // Brief settle time for auto-exposure/focus
        await new Promise(r => setTimeout(r, 500));


        // ═══════════════════════════════════════════════════════
        // PHASE 1: IDENTITY CHECK (server-side, but fast with cached embedding)
        // ═══════════════════════════════════════════════════════
        statusText.textContent = 'Verifying identity...';
        _showChallengeOverlay('🔍 Verifying identity...\nLook at the camera');

        let identityPassed = false;
        let faceBox = null;
        let verifiedFrame = null;

        for (let attempt = 1; attempt <= 10; attempt++) {
            if (!currentStream) return;

            const frame = captureFastFrame(videoElement);
            try {
                const res = await fetch(`${API_BASE}/api/attendance/check_identity`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ student_id: studentId, image: frame })
                });
                const data = await res.json();

                if (data.status === 'success' && data.verified && data.faceBox) {
                    identityPassed = true;
                    faceBox = data.faceBox;
                    verifiedFrame = frame;
                    break;
                } else if (data.status === 'error' && data.code &&
                    !['FACE_VERIFY_FAILED', 'FACE_DECODE_ERROR'].includes(data.code) &&
                    data.message !== 'No face detected.') {
                    // Fatal error (e.g. Student not found, No photo)
                    stopCamera();
                    return showResult('error', data.message);
                } else {
                    const confidence = data.distance ? Math.round((1 - data.distance) * 100) : 0;
                    _showChallengeOverlay(
                        `🔍 Verifying... (${attempt}/10)\n` +
                        `${data.message || 'Looking for face...'}`
                    );
                }
            } catch (e) {
                console.error("Identity check error:", e);
            }

            // Wait 500ms between attempts
            await new Promise(r => setTimeout(r, 500));
        }

        if (!identityPassed) {
            stopCamera();
            return showResult('error', 'Identity verification failed.\nPlease try again with better lighting.');
        }


        // ═══════════════════════════════════════════════════════
        // PHASE 2: CLIENT-SIDE LIVENESS (MediaPipe in browser)
        //
        // This is the key optimisation: pose detection runs at
        // 60fps directly in the browser. No network calls.
        // Old approach: 300ms+ per frame server round-trip
        // New approach: ~16ms per frame (requestAnimationFrame)
        // ═══════════════════════════════════════════════════════
        statusText.textContent = 'Liveness check...';

        // Make sure MediaPipe is ready
        if (!mpReady) {
            _showChallengeOverlay('⏳ Loading face tracker...');
            const loaded = await initMediaPipe();
            if (!loaded) {
                // MediaPipe unavailable — fall back to server-side liveness
                console.warn("[WARN] MediaPipe unavailable, falling back to server-side");
                const serverLivenessOk = await _serverSideLiveness(videoElement, faceBox);
                if (!serverLivenessOk) return;
                // If server liveness passed, continue to Phase 3
                _hideChallengeOverlay();
                stopCamera();
                await _recordAttendance(sessionCode, studentId, verifiedFrame, true);
                return;
            }
        }

        // Get challenge from server
        let challenges = [];
        try {
            const res = await fetch(`${API_BASE}/api/attendance/challenges`);
            const data = await res.json();
            challenges = data.challenges || [];
        } catch (e) {
            challenges = [{ action: 'left', label: 'Look Left' }];
        }

        // Run each challenge with client-side detection
        for (let i = 0; i < challenges.length; i++) {
            const challenge = challenges[i];
            let matched = false;
            let matchCount = 0;
            const REQUIRED_MATCHES = 3;  // Need 3 consecutive frames matching
            const startTime = Date.now();

            _showChallengeOverlay(`👉 ${challenge.label}`);

            while (!matched) {
                if (!currentStream) return;

                if (Date.now() - startTime > 15000) {
                    stopCamera();
                    return showResult('error', `Timeout: ${challenge.label}.\nTry again.`);
                }

                // Wait for next animation frame (smooth 60fps loop)
                const timestamp = await new Promise(resolve => {
                    requestAnimationFrame(ts => resolve(ts));
                });

                const poseResult = detectPoseClientSide(videoElement, timestamp);

                if (poseResult) {
                    if (poseResult.pose === challenge.action) {
                        matchCount++;
                        if (matchCount >= REQUIRED_MATCHES) {
                            matched = true;
                            _showChallengeOverlay(`✅ ${challenge.label} — Passed!`);
                        } else {
                            _showChallengeOverlay(
                                `👉 ${challenge.label}  ✓ Hold... (${matchCount}/${REQUIRED_MATCHES})`
                            );
                        }
                    } else {
                        matchCount = 0;
                        _showChallengeOverlay(
                            `👉 ${challenge.label}\nDetected: ${poseResult.pose} | yaw: ${poseResult.yaw}`
                        );
                    }
                } else {
                    matchCount = 0;
                    _showChallengeOverlay(`👉 ${challenge.label}\n(No face detected — look at camera)`);
                }
            }

            // Brief pause after passing challenge
            await new Promise(r => setTimeout(r, 400));
        }


        // ═══════════════════════════════════════════════════════
        // PHASE 3: RECORD ATTENDANCE
        // ═══════════════════════════════════════════════════════
        _hideChallengeOverlay();
        stopCamera();
        await _recordAttendance(sessionCode, studentId, verifiedFrame, true);

    } catch (err) {
        console.error('Camera error:', err);
        showNotification('Unable to access camera', 'error');
        cameraModal.classList.remove('active');
    }
}


/**
 * Fallback: server-side liveness check (used when MediaPipe JS fails to load).
 * Returns true if liveness passed, false otherwise.
 */
async function _serverSideLiveness(videoElement, faceBox) {
    let challenges = [];
    try {
        const res = await fetch(`${API_BASE}/api/attendance/challenges`);
        const data = await res.json();
        challenges = data.challenges || [];
    } catch (e) {
        challenges = [{ action: 'left', label: 'Look Left' }];
    }

    for (let i = 0; i < challenges.length; i++) {
        const challenge = challenges[i];
        let poseMatched = false;
        let challengeStart = Date.now();
        _showChallengeOverlay(`${challenge.label} (server mode)`);

        while (!poseMatched) {
            await new Promise(r => setTimeout(r, 300));
            if (!currentStream) return false;

            if (Date.now() - challengeStart > 12000) {
                stopCamera();
                showResult('error', `Timeout: ${challenge.label}`);
                return false;
            }

            const frame = captureFastFrame(videoElement);
            try {
                const res = await fetch(`${API_BASE}/api/attendance/check_pose`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: frame, faceBox: faceBox })
                });
                const data = await res.json();
                _showChallengeOverlay(
                    `${challenge.label}\nDetected: ${data.pose} | yaw: ${data.yaw?.toFixed(1)}`
                );
                if (data.status === 'success' && data.pose === challenge.action) {
                    poseMatched = true;
                }
            } catch (e) {
                console.error("Pose check error:", e);
            }
        }
    }
    return true;
}


/**
 * Send the verified frame to the server to record attendance.
 */
async function _recordAttendance(sessionCode, studentId, imageFrame, livenessPassed) {
    statusText.textContent = 'Recording attendance...';
    try {
        const response = await fetch(`${API_BASE}/api/attendance/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_code: sessionCode,
                student_id: studentId,
                images: [],
                image: imageFrame,
                qr_token: currentQrToken || '',
                liveness_passed: livenessPassed,
                device_fingerprint: getDeviceFingerprint(),
            })
        });
        const data = await response.json();

        if (data.status === 'success') {
            showResult('success', `✅ Attendance recorded!\nStudent: ${data.student_name || studentId}`);
        } else {
            showResult('error', `${data.message || 'Verification failed'}\n${data.code || ''}`);
        }
    } catch (err) {
        console.error('Verify error:', err);
        showResult('error', 'Server connection error');
    }
}


// ══════════════════════════════════════════════════════════════
// UI HELPERS
// ══════════════════════════════════════════════════════════════

function _showChallengeOverlay(text) {
    let overlay = document.getElementById('livenessOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'livenessOverlay';
        overlay.style.cssText = `
            position: fixed; top: 75%; left: 50%; transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.85); color: #fff; padding: 20px 30px;
            border-radius: 15px; font-size: 20px; font-weight: bold; z-index: 10002;
            font-family: 'Montserrat', sans-serif; text-align: center;
            border: 2px solid rgba(124,102,227,0.6); width: 85%; max-width: 500px;
            white-space: pre-line; line-height: 1.4;
            backdrop-filter: blur(10px);
        `;
        document.body.appendChild(overlay);
    }
    overlay.textContent = text;
    overlay.style.display = 'block';
}

function _hideChallengeOverlay() {
    const overlay = document.getElementById('livenessOverlay');
    if (overlay) overlay.style.display = 'none';
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


// ══════════════════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════════════════

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
