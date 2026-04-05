let sessionCode = "";
let studentId = "";
let videoStream = null;
let livenessState = "idle"; // idle, center1, left, right, center2, done
let livenessTimer = null;
let holdStart = 0;
const HOLD_MS = 800; // Hold each position for 0.8 seconds
const POSE_TIMEOUT = 10000; // 10 seconds timeout per pose
let poseStartTime = 0; // Track when current pose started
let detectionLoop = null;
let centerFrameData = null; // Capture during first CENTER for best face match

// Models URL (CDN)
const MODEL_URL = "/static/models";

// Auto-fill code from URL query param
window.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    if (code) {
        document.getElementById("sessionCodeInput").value = code.toUpperCase();
    }
});

async function validateSession() {
    const code = document.getElementById("sessionCodeInput").value.trim().toUpperCase();
    const sid = document.getElementById("studentIdInput").value.trim();
    const msgEl = document.getElementById("step1Msg");

    if (!code || !sid) {
        msgEl.className = "msg error";
        msgEl.textContent = "Please enter both session code and student ID.";
        return;
    }

    document.getElementById("validateBtn").disabled = true;
    msgEl.innerHTML = '<span class="spinner"></span> Checking session...';
    msgEl.className = "msg";

    try {
        const res = await fetch(`/api/session/${code}`);
        const data = await res.json();

        if (data.status !== "success") {
            msgEl.className = "msg error";
            msgEl.textContent = data.message;
            document.getElementById("validateBtn").disabled = false;
            return;
        }

        sessionCode = code;
        studentId = sid;

        // Show session banner
        document.getElementById("bannerCourse").textContent =
            `${data.course_code} — ${data.course_name}`;
        document.getElementById("bannerInstructor").textContent =
            `Instructor: ${data.instructor_name}`;
        document.getElementById("sessionBanner").style.display = "block";

        // Move to step 2
        setStep(2);
        document.getElementById("step1Card").style.display = "none";
        document.getElementById("step2Card").style.display = "block";

        // Start camera + liveness
        startCamera();

    } catch (e) {
        msgEl.className = "msg error";
        msgEl.textContent = "Server error: " + e.message;
        document.getElementById("validateBtn").disabled = false;
    }
}

async function startCamera() {
    const instrEl = document.getElementById("livenessInstruction");
    instrEl.textContent = "Starting camera...";

    try {
        videoStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
            audio: false,
        });
        document.getElementById("video").srcObject = videoStream;

        // Wait for video to be ready
        const video = document.getElementById("video");
        await new Promise(resolve => {
            video.onloadeddata = resolve;
        });

        // Load face-api models
        instrEl.textContent = "Loading face detector...";
        await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL);
        await faceapi.nets.faceLandmark68TinyNet.loadFromUri(MODEL_URL);

        // Start liveness challenge
        startLiveness();

    } catch (e) {
        const msgEl = document.getElementById("step2Msg");
        msgEl.className = "msg error";
        if (e.name === "NotAllowedError") {
            msgEl.textContent = "📷 Camera permission denied. Please allow camera access and try again.";
        } else if (e.name === "NotFoundError") {
            msgEl.textContent = "📷 No camera found on this device.";
        } else if (window.location.protocol !== "https:") {
            msgEl.textContent = "🔒 Camera requires HTTPS. Please use the https:// link.";
        } else {
            msgEl.textContent = "📷 Cannot access camera: " + e.message;
        }
    }
}

function stopCamera() {
    if (videoStream) {
        videoStream.getTracks().forEach(t => t.stop());
        videoStream = null;
    }
    if (detectionLoop) {
        cancelAnimationFrame(detectionLoop);
        detectionLoop = null;
    }
}

// ── Liveness Detection ──────────────────────────────────────────────

function startLiveness() {
    livenessState = "center1";
    holdStart = 0;
    poseStartTime = Date.now();
    updateLivenessUI();
    detectFace();
}

function updateLivenessUI() {
    const instrEl = document.getElementById("livenessInstruction");
    const lsCenter1 = document.getElementById("ls-center1");
    const lsLeft = document.getElementById("ls-left");
    const lsRight = document.getElementById("ls-right");
    const lsCenter2 = document.getElementById("ls-center2");

    // Reset all
    lsCenter1.className = "liveness-step";
    lsLeft.className = "liveness-step";
    lsRight.className = "liveness-step";
    lsCenter2.className = "liveness-step";

    switch (livenessState) {
        case "center1":
            instrEl.textContent = "↑ Look straight AHEAD";
            lsCenter1.classList.add("active");
            break;
        case "left":
            instrEl.textContent = "← Turn your head LEFT";
            lsCenter1.classList.add("done");
            lsLeft.classList.add("active");
            break;
        case "right":
            instrEl.textContent = "→ Turn your head RIGHT";
            lsCenter1.classList.add("done");
            lsLeft.classList.add("done");
            lsRight.classList.add("active");
            break;
        case "center2":
            instrEl.textContent = "↑ Look straight AHEAD again";
            lsCenter1.classList.add("done");
            lsLeft.classList.add("done");
            lsRight.classList.add("done");
            lsCenter2.classList.add("active");
            break;
        case "done":
            instrEl.textContent = "✅ Capturing photo...";
            lsCenter1.classList.add("done");
            lsLeft.classList.add("done");
            lsRight.classList.add("done");
            lsCenter2.classList.add("done");
            break;
    }
}

function getHeadYaw(landmarks) {
    // Use nose tip and face edges to estimate yaw
    const nose = landmarks.getNose();
    const leftJaw = landmarks.getJawOutline()[0];
    const rightJaw = landmarks.getJawOutline()[16];

    const noseX = nose[3].x; // Nose tip
    const faceLeft = leftJaw.x;
    const faceRight = rightJaw.x;
    const faceWidth = faceRight - faceLeft;

    if (faceWidth === 0) return 0;

    // Normalize nose position: 0 = left edge, 1 = right edge
    // Center should be ~0.5
    const noseRelative = (noseX - faceLeft) / faceWidth;

    // Convert to yaw-like value: negative = looking left, positive = looking right
    // Center = 0, Left ≈ -0.15+, Right ≈ 0.15+
    return noseRelative - 0.5;
}

async function detectFace() {
    if (livenessState === "done" || livenessState === "idle") return;

    const video = document.getElementById("video");
    const overlay = document.getElementById("overlayCanvas");

    // Match overlay to video dimensions
    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;

    const detection = await faceapi
        .detectSingleFace(video, new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.55 }))
        .withFaceLandmarks(true); // true = use tiny model

    const ctx = overlay.getContext("2d");
    ctx.clearRect(0, 0, overlay.width, overlay.height);

    if (detection) {
        // Draw full-camera green border
        ctx.strokeStyle = "#00ff88";
        ctx.lineWidth = 4;
        ctx.strokeRect(0, 0, overlay.width, overlay.height);

        const yaw = getHeadYaw(detection.landmarks);
        const now = Date.now();

        let passed = false;
        switch (livenessState) {
            case "center1":
            case "center2":
                passed = Math.abs(yaw) < 0.07;
                break;
            case "left":
                // Note: camera is mirrored, so looking left in mirror = yaw positive
                passed = yaw > 0.12;
                break;
            case "right":
                passed = yaw < -0.12;
                break;
        }

        // Check pose timeout (10 seconds per pose)
        if (now - poseStartTime > POSE_TIMEOUT) {
            // Timeout — restart liveness from beginning
            livenessState = "center1";
            holdStart = 0;
            poseStartTime = now;
            centerFrameData = null;
            updateLivenessUI();
            const msgEl = document.getElementById("step2Msg");
            msgEl.className = "msg error";
            msgEl.textContent = "⏱ Pose timeout! Restarting challenge...";
            setTimeout(() => { msgEl.textContent = ""; }, 2000);
        }

        if (passed) {
            if (holdStart === 0) holdStart = now;
            const held = now - holdStart;

            // Show hold progress over entire camera
            const progress = Math.min(held / HOLD_MS, 1);
            ctx.fillStyle = `rgba(0, 255, 136, ${0.1 + progress * 0.15})`;
            ctx.fillRect(0, 0, overlay.width, overlay.height);

            // Progress bar at bottom of camera
            ctx.fillStyle = "#00ff88";
            ctx.fillRect(0, overlay.height - 6, overlay.width * progress, 6);

            if (held >= HOLD_MS) {
                // Step passed
                holdStart = 0;
                poseStartTime = now;
                if (livenessState === "center1") {
                    // Capture frame NOW — face is straight ahead, best for matching
                    const _c = document.getElementById("captureCanvas");
                    _c.width = video.videoWidth;
                    _c.height = video.videoHeight;
                    _c.getContext("2d").drawImage(video, 0, 0);
                    centerFrameData = _c.toDataURL("image/jpeg", 0.9);
                    livenessState = "left";
                }
                else if (livenessState === "left") livenessState = "right";
                else if (livenessState === "right") livenessState = "center2";
                else if (livenessState === "center2") {
                    livenessState = "done";
                    updateLivenessUI();
                    // Auto-capture after short delay
                    setTimeout(() => captureAndVerify(), 400);
                    return;
                }
                updateLivenessUI();
            }
        } else {
            holdStart = 0;
        }
    } else {
        holdStart = 0;
    }

    detectionLoop = requestAnimationFrame(detectFace);
}

// ── Capture & Verify ────────────────────────────────────────────────

async function captureAndVerify() {
    const msgEl = document.getElementById("step2Msg");

    // Use the frame captured during CENTER position (face looking straight)
    const imageData = centerFrameData;

    msgEl.innerHTML = '<span class="spinner"></span> Verifying face...';
    msgEl.className = "msg";

    try {
        const res = await fetch("/api/attendance/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_code: sessionCode,
                student_id: studentId,
                image: imageData,
            }),
        });
        const data = await res.json();

        stopCamera();

        // Move to step 3
        setStep(3);
        document.getElementById("step2Card").style.display = "none";
        document.getElementById("step3Card").style.display = "block";

        const resultBox = document.getElementById("resultBox");
        resultBox.style.display = "block";

        if (data.status === "success" && data.verified) {
            resultBox.className = "result success";
            document.getElementById("resultIcon").textContent = "✅";
            document.getElementById("resultTitle").textContent = "Attendance Recorded!";
            document.getElementById("resultMsg").textContent = data.message;
        } else {
            resultBox.className = "result fail";
            document.getElementById("resultIcon").textContent = "❌";
            document.getElementById("resultTitle").textContent = "Verification Failed";
            document.getElementById("resultMsg").textContent = data.message;
        }

    } catch (e) {
        msgEl.className = "msg error";
        msgEl.textContent = "Server error: " + e.message;
    }
}

// ── Helpers ─────────────────────────────────────────────────────────

function setStep(n) {
    for (let i = 1; i <= 3; i++) {
        const el = document.getElementById(`step${i}`);
        el.className = i < n ? "step done" : (i === n ? "step active" : "step");
    }
}

function resetFlow() {
    stopCamera();
    sessionCode = "";
    studentId = "";
    livenessState = "idle";
    holdStart = 0;
    poseStartTime = 0;
    centerFrameData = null;

    setStep(1);
    document.getElementById("step1Card").style.display = "block";
    document.getElementById("step2Card").style.display = "none";
    document.getElementById("step3Card").style.display = "none";
    document.getElementById("sessionBanner").style.display = "none";
    document.getElementById("validateBtn").disabled = false;
    document.getElementById("step1Msg").textContent = "";
    document.getElementById("step2Msg").textContent = "";
    document.getElementById("resultBox").style.display = "none";
    document.getElementById("studentIdInput").value = "";
}
