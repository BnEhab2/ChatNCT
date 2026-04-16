import os
import sys
import socket
import random
import string
import base64
import hashlib
import hmac
import time
import threading
import tempfile
from datetime import datetime, timedelta

import cv2
import numpy as np
import requests as http_requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load environment variables from project root
_WEB_DIR = os.path.dirname(__file__)           # mainAgent/web
_MAIN_AGENT_DIR = os.path.dirname(_WEB_DIR)     # mainAgent
_ROOT_DIR = os.path.dirname(_MAIN_AGENT_DIR)    # project root
_env_path = os.path.join(_ROOT_DIR, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

# Import database module from mainAgent.db
sys.path.insert(0, _ROOT_DIR)
from mainAgent.db.database import get_connection, release_connection
from mainAgent.web.face_verifier import FaceVerifier

# [DEBUG LAYER] Import debug flag and logger.
# To remove: delete these 3 lines and all 'if DEBUG_FACE_PIPELINE:' blocks below.
from mainAgent.web.face_verifier import DEBUG_FACE_PIPELINE
if DEBUG_FACE_PIPELINE:
    from mainAgent.web.face_debug_logger import debug_logger

# Initialize FaceVerifier once at startup
face_verifier = FaceVerifier()

app = Flask(__name__)

# ── Supabase Storage Config ────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_BUCKET = "students_image"

@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "service": "ChatNCT Attendance API",
        "message": "This is a backend API. Please use the main frontend on port 5000."
    })


# Temp directory for caching downloaded student photos
TEMP_PHOTOS_DIR = os.path.join(tempfile.gettempdir(), "chatnct_photos")
os.makedirs(TEMP_PHOTOS_DIR, exist_ok=True)

# Secret key for HMAC token generation
QR_SECRET = os.getenv("QR_SECRET", "chatnct-qr-secret-2026")

# ── Structured Error Codes (Feature 10) ───────────────────────────────
ERR_CODES = {
    "SESSION_NOT_FOUND": ("Session not found.", 404),
    "SESSION_EXPIRED": ("Session has expired.", 410),
    "SESSION_CLOSED": ("Session is closed.", 410),
    "STUDENT_NOT_FOUND": ("Student not found.", 404),
    "ATTENDANCE_DUPLICATE": ("Student already attended this session.", 409),
    "TOKEN_INVALID": ("QR token is invalid.", 403),
    "TOKEN_EXPIRED": ("QR token has expired.", 403),
    "TOKEN_USED": ("QR token has already been used.", 403),
    "RATE_LIMITED": ("Too many attempts. Please wait.", 429),
    "DEVICE_MISMATCH": ("Device mismatch. Use the same device.", 403),
    "FACE_NO_PHOTO": ("No registered photo for this student.", 400),
    "FACE_DECODE_ERROR": ("Failed to decode image.", 400),
    "FACE_VERIFY_FAILED": ("Face verification failed.", 403),
    "FACE_VERIFY_ERROR": ("Face verification error.", 500),
    "FACE_LOW_CONFIDENCE": ("Face confidence too low.", 403),
    "FACE_STATIC_IMAGE": ("Static image detected. Please use a live camera.", 403),
    "LIVENESS_FAILED": ("Liveness check failed.", 403),
    "MISSING_FIELDS": ("Required fields are missing.", 400),
    "COURSE_REQUIRED": ("course_id is required.", 400),
}


def _error(code, extra=None):
    """Return a structured error response."""
    msg, status = ERR_CODES.get(code, ("Unknown error.", 500))
    body = {"status": "error", "code": code, "message": msg}
    if extra:
        body.update(extra)
    return jsonify(body), status


def _get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


LAN_IP = _get_lan_ip()


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

def _generate_code(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def _decode_base64_image(data_url: str) -> np.ndarray:
    # [DEBUG] Save a snippet of the raw base64 input
    if DEBUG_FACE_PIPELINE:
        snippet = data_url[:200] if len(data_url) > 200 else data_url
        debug_logger.save_text("step_01_raw_base64",
                               f"length: {len(data_url)}\nfirst_200_chars:\n{snippet}")

    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    img_bytes = base64.b64decode(data_url)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    # [DEBUG] Save the decoded frame + grayscale version
    if DEBUG_FACE_PIPELINE:
        debug_logger.save_image("step_02_decoded_frame", frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        debug_logger.save_image("step_02_decoded_frame_gray", gray)

    return frame


# ── Supabase Photo Download ───────────────────────────────────────────
def _download_student_photo(student_code: str) -> str:
    """Download a student's photo from Supabase students_image bucket.
    
    Returns the local cached path, or None if not found.
    Tries common extensions: .png, .jpg, .jpeg
    """
    # Check cache first
    for ext in [".png", ".jpg", ".jpeg"]:
        cached = os.path.join(TEMP_PHOTOS_DIR, f"{student_code}{ext}")
        if os.path.exists(cached):
            return cached

    # Try downloading from Supabase
    for ext in [".png", ".jpg", ".jpeg"]:
        filename = f"{student_code}{ext}"
        url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}"
        try:
            resp = http_requests.get(url, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 100:
                local_path = os.path.join(TEMP_PHOTOS_DIR, filename)
                with open(local_path, "wb") as f:
                    f.write(resp.content)
                print(f" Downloaded photo for student {student_code} from Supabase")
                return local_path
        except Exception as e:
            print(f"[WARN] Failed to download {filename}: {e}")
            continue

    return None


# ── Feature 2: QR Token Generation (HMAC-based, 5s expiry) ───────────
def _generate_qr_token(session_id: int) -> dict:
    """Generate a single-use HMAC token bound to session + timestamp."""
    ts = int(time.time())
    payload = f"{session_id}:{ts}"
    token = hmac.new(QR_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Clean expired tokens (older than 180s)
        cur.execute("DELETE FROM qr_tokens WHERE created_at < now() - interval '180 seconds'")
        cur.execute(
            "INSERT INTO qr_tokens (session_id, token) VALUES (%s, %s)",
            (session_id, token)
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        release_connection(conn)

    return {"token": token, "timestamp": ts, "expires_in": 5}


def _validate_qr_token(session_id: int, token: str) -> tuple:
    """Validate a QR token. Returns (valid, error_code)."""
    if not token:
        return False, "TOKEN_INVALID"

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, session_id, used, created_at FROM qr_tokens WHERE token = %s",
            (token,)
        )
        row = cur.fetchone()

        if not row:
            return False, "TOKEN_INVALID"

        row = dict(row)

        if row["used"]:
            return False, "TOKEN_USED"

        if row["session_id"] != session_id:
            return False, "TOKEN_INVALID"

        # Mark as used (single-use)
        cur.execute("UPDATE qr_tokens SET used = true WHERE id = %s", (row["id"],))
        conn.commit()
        return True, None
    except Exception:
        conn.rollback()
        return False, "TOKEN_INVALID"
    finally:
        release_connection(conn)


# ── Feature 6: Rate Limiting ──────────────────────────────────────────
RATE_LIMITS = {
    "face_verify": {"max": 3, "block_seconds": 60},
    "qr_scan": {"max": 5, "block_seconds": 60},
}


def _check_rate_limit(student_id: str, session_id: int, action: str) -> tuple:
    """Check rate limit. Returns (allowed, error_response_or_None)."""
    limits = RATE_LIMITS.get(action)
    if not limits:
        return True, None

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT attempts, blocked_until, last_attempt FROM rate_limits
               WHERE student_id = %s AND session_id = %s AND action = %s""",
            (student_id, session_id, action)
        )
        row = cur.fetchone()

        now = datetime.now()

        if row:
            row = dict(row)
            blocked_until = row.get("blocked_until")
            if blocked_until and now < blocked_until.replace(tzinfo=None):
                remaining = int((blocked_until.replace(tzinfo=None) - now).total_seconds())
                return False, _error("RATE_LIMITED", {"retry_after": remaining})

            if row["attempts"] >= limits["max"]:
                block_until = now + timedelta(seconds=limits["block_seconds"])
                cur.execute(
                    """UPDATE rate_limits SET blocked_until = %s, attempts = 0, last_attempt = %s
                       WHERE student_id = %s AND session_id = %s AND action = %s""",
                    (block_until, now, student_id, session_id, action)
                )
                conn.commit()
                return False, _error("RATE_LIMITED", {"retry_after": limits["block_seconds"]})

            cur.execute(
                """UPDATE rate_limits SET attempts = attempts + 1, last_attempt = %s
                   WHERE student_id = %s AND session_id = %s AND action = %s""",
                (now, student_id, session_id, action)
            )
        else:
            cur.execute(
                """INSERT INTO rate_limits (student_id, session_id, action) VALUES (%s, %s, %s)""",
                (student_id, session_id, action)
            )

        conn.commit()
        return True, None
    except Exception:
        conn.rollback()
        return True, None
    finally:
        release_connection(conn)


# ── Feature 7: Device Binding ─────────────────────────────────────────
def _check_device_binding(student_id: str, session_id: int, req) -> tuple:
    """Check/create device binding. Returns (allowed, error_response_or_None)."""
    ip = req.headers.get("X-Forwarded-For", req.remote_addr)
    ua = req.headers.get("User-Agent", "")[:500]
    fp = req.headers.get("X-Device-Fingerprint", "")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT ip_address, user_agent FROM device_bindings WHERE student_id = %s AND session_id = %s",
            (student_id, session_id)
        )
        row = cur.fetchone()

        if row:
            row = dict(row)
            # Allow same IP or same user agent (loose binding)
            if row["ip_address"] != ip and row["user_agent"] != ua:
                return False, _error("DEVICE_MISMATCH")
        else:
            cur.execute(
                """INSERT INTO device_bindings (student_id, session_id, ip_address, user_agent, device_fingerprint)
                   VALUES (%s, %s, %s, %s, %s) ON CONFLICT (student_id, session_id) DO NOTHING""",
                (student_id, session_id, ip, ua, fp)
            )
            conn.commit()

        return True, None
    except Exception:
        conn.rollback()
        return True, None  # Fail open
    finally:
        release_connection(conn)


# ── Feature 3: Multi-Frame Face Verification ──────────────────────────
def _verify_multi_frame(images_data: list, photo_path: str) -> dict:
    """
    Verify identity using multiple frames.
    - Capture 5 frames
    - Compare all against registered photo
    - Average confidence > 0.7
    - Check for static image (face movement between frames)
    """
    if not images_data or len(images_data) < 3:
        return {"verified": False, "message": "Need at least 3 frames.", "avg_confidence": 0}

    frames = []
    for img_data in images_data[:5]:
        try:
            frame = _decode_base64_image(img_data)
            frames.append(frame)
        except Exception:
            continue

    if len(frames) < 3:
        return {"verified": False, "message": "Could not decode enough frames.", "avg_confidence": 0}

    # Check for static image (Feature 3: reject static)
    is_static = _is_static_image(frames)
    if is_static:
        return {"verified": False, "message": "Static image detected.", "avg_confidence": 0, "static": True}

    # [DEBUG] Save individual frames into subfolders
    if DEBUG_FACE_PIPELINE:
        for idx, fr in enumerate(frames[:3]):
            debug_logger.save_image(f"decoded_frame", fr, subfolder=f"frame_{idx+1}")

    # Verify each frame
    distances = []
    for i, frame in enumerate(frames):
        try:
            result = face_verifier.verifyIdentity(frame, photo_path)
            if result.get("distance") is not None:
                distances.append(result["distance"])
                # [DEBUG] Save per-frame distance
                if DEBUG_FACE_PIPELINE and i < 3:
                    debug_logger.save_text(
                        f"per_frame_distance",
                        f"distance: {result['distance']:.6f}\nverified: {result.get('verified')}",
                        subfolder=f"frame_{i+1}"
                    )
        except Exception:
            continue

    if len(distances) < 2:
        return {"verified": False, "message": "Face not detected in enough frames.", "avg_confidence": 0}

    avg_distance = sum(distances) / len(distances)
    avg_confidence = round(1.0 - avg_distance, 4)
    verified = avg_confidence >= 0.7

    # [DEBUG] Save multi-frame summary
    if DEBUG_FACE_PIPELINE:
        summary = (
            f"frames_total: {len(frames)}\n"
            f"frames_with_face: {len(distances)}\n"
            f"distances: {[round(d, 6) for d in distances]}\n"
            f"avg_distance: {avg_distance:.6f}\n"
            f"avg_confidence: {avg_confidence:.4f}\n"
            f"verified: {verified}\n"
            f"static_image: {is_static}\n"
        )
        debug_logger.save_text("multi_frame_summary", summary)

    return {
        "verified": verified,
        "avg_confidence": avg_confidence,
        "avg_distance": round(avg_distance, 4),
        "frames_checked": len(distances),
        "message": "Identity verified." if verified else f"Confidence too low ({avg_confidence:.2f} < 0.70).",
    }


def _is_static_image(frames: list) -> bool:
    """Detect if frames are from a static image (no movement)."""
    if len(frames) < 2:
        return False

    diffs = []
    for i in range(1, len(frames)):
        gray1 = cv2.cvtColor(frames[i - 1], cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray1, gray2)
        diffs.append(np.mean(diff))

    avg_diff = sum(diffs) / len(diffs)
    # If average pixel difference is < 2, it's likely the same static image
    return avg_diff < 2.0


# ── Feature 4: Liveness Challenge Generation ──────────────────────────
LIVENESS_CHALLENGES = [
    {"action": "look_left", "label": "Look Left"},
    {"action": "look_right", "label": "Look Right"},
    {"action": "look_up", "label": "Look Up"},
    {"action": "blink", "label": "Blink"},
    {"action": "smile", "label": "Smile"},
]


def _generate_liveness_challenges(count: int = 3) -> list:
    """Generate random liveness challenges for a session."""
    selected = random.sample(LIVENESS_CHALLENGES, min(count, len(LIVENESS_CHALLENGES)))
    return selected


# ── Feature 8: Session Auto-Close (Background Thread) ─────────────────
def _auto_close_sessions():
    """Background thread: close expired sessions every 30 seconds."""
    while True:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE attendance_sessions SET is_active = 0
                WHERE is_active = 1 AND expires_at < NOW()
            """)
            closed = cur.rowcount
            conn.commit()
            release_connection(conn)
            if closed > 0:
                print(f"[AUTO-CLOSE] Auto-closed {closed} expired session(s).")
        except Exception as e:
            print(f"Auto-close error: {e}")
        time.sleep(30)


# Start auto-close thread
_auto_close_thread = threading.Thread(target=_auto_close_sessions, daemon=True)
_auto_close_thread.start()


# ══════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════




# ── API: Courses List ─────────────────────────────────────────────────
@app.route("/api/courses", methods=["GET"])
def list_courses():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id AS course_id, c.course_code, c.name AS course_name,
                   i.id AS instructor_id, i.name AS instructor_name
            FROM courses c
            LEFT JOIN instructors i ON c.instructor_id = i.id
            ORDER BY c.course_code
        """)
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify(rows)
    finally:
        release_connection(conn)


# ── API: Create Session ──────────────────────────────────────────────
@app.route("/api/session/create", methods=["POST"])
def create_session():
    data = request.get_json()
    course_id = data.get("course_id")
    instructor_id = data.get("instructor_id")
    if instructor_id == 1 or instructor_id == "1":
        instructor_id = None
    duration = data.get("duration_minutes", 15)
    duration = max(5, min(120, int(duration)))

    if not course_id:
        return _error("COURSE_REQUIRED")

    code = _generate_code()
    now = datetime.utcnow()
    expires = now + timedelta(minutes=duration)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE attendance_sessions SET is_active = 0 WHERE course_id = %s AND is_active = 1", (course_id,))
        cur.execute("""
            INSERT INTO attendance_sessions (session_code, course_id, instructor_id, expires_at)
            VALUES (%s, %s, %s, %s) RETURNING session_id
        """, (code, course_id, instructor_id, expires.isoformat()))
        session_id = cur.fetchone()[0]
        conn.commit()

        cur.execute("SELECT course_code, name AS course_name FROM courses WHERE id = %s", (course_id,))
        course = dict(cur.fetchone())

        # Generate initial QR token
        initial_token = _generate_qr_token(session_id)

        return jsonify({
            "status": "success",
            "session_id": session_id,
            "session_code": code,
            "code": code,
            "course": course,
            "expires_at": expires.isoformat(),
            "duration_minutes": duration,
            "qr_token": initial_token,
        })
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "code": "DB_ERROR", "message": str(e)}), 500
    finally:
        release_connection(conn)


# ── Feature 2: API: Get Rotating QR Token ─────────────────────────────
@app.route("/api/session/<code>/qr-token", methods=["GET"])
def get_qr_token(code):
    """Generate a new rotating QR token for the session (called every 5s by instructor UI)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT session_id, is_active, expires_at FROM attendance_sessions WHERE session_code = %s", (code,))
        row = cur.fetchone()
        if not row:
            return _error("SESSION_NOT_FOUND")

        session = dict(row)
        now = datetime.utcnow()

        if not session["is_active"]:
            return _error("SESSION_CLOSED")

        expires_str = str(session["expires_at"]).replace("+00:00", "")
        if now > datetime.fromisoformat(expires_str):
            return _error("SESSION_EXPIRED")

        token_data = _generate_qr_token(session["session_id"])
        return jsonify({"status": "success", **token_data})
    finally:
        release_connection(conn)


# ── API: Check Session ────────────────────────────────────────────────
@app.route("/api/session/<code>", methods=["GET"])
def check_session(code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.*, c.course_code, c.name AS course_name, i.name AS instructor_name
            FROM attendance_sessions s
            JOIN courses c ON s.course_id = c.id
            LEFT JOIN instructors i ON s.instructor_id = i.id
            WHERE s.session_code = %s
        """, (code,))
        row = cur.fetchone()

        if not row:
            return _error("SESSION_NOT_FOUND")

        session = dict(row)
        now = datetime.utcnow()
        expires_str = str(session["expires_at"]).replace("+00:00", "")
        expires = datetime.fromisoformat(expires_str)
        is_expired = now > expires

        if not session["is_active"] or is_expired:
            return _error("SESSION_EXPIRED" if is_expired else "SESSION_CLOSED")

        return jsonify({
            "status": "success",
            "session_id": session["session_id"],
            "course_code": session["course_code"],
            "course_name": session["course_name"],
            "instructor_name": session["instructor_name"],
            "expires_at": session["expires_at"],
        })
    finally:
        release_connection(conn)


# ── Feature 4: API: Get Liveness Challenges ───────────────────────────
@app.route("/api/attendance/challenges", methods=["GET"])
def get_challenges():
    """Return 2 random liveness challenges for verification."""
    pool = [
        {"action": "left",   "label": "--> Look Right"},
        {"action": "right",  "label": "<-- Look Left"},
        {"action": "center", "label": "|  Look Straight"},
        {"action": "up",     "label": "^  Look Up"},
        {"action": "down",   "label": "v  Look Down"},
        {"action": "smile",  "label": ":) Smile"},
        {"action": "blink",  "label": "-- Blink"},
    ]
    selected = random.sample(pool, 2)
    return jsonify({"status": "success", "challenges": selected})


# ── API: Prepare Verification (Pre-cache embedding) ───────────────────
@app.route("/api/attendance/prepare", methods=["POST"])
def prepare_verification():
    """Pre-download student photo and cache its face embedding.

    Called BEFORE the camera opens so the first identity check is fast.
    Without this, the first call to check_identity has to download the
    photo AND compute the embedding, adding 1–3 seconds.
    """
    data = request.get_json()
    student_id = data.get("student_id", "").strip()

    if not student_id:
        return _error("MISSING_FIELDS")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT student_code FROM students WHERE student_code = %s OR id::text = %s",
            (student_id, student_id)
        )
        student = cur.fetchone()
        if not student:
            return _error("STUDENT_NOT_FOUND")

        student_code = dict(student).get("student_code", student_id)
        photo_path = _download_student_photo(student_code)
        if not photo_path:
            return _error("FACE_NO_PHOTO")

        # Pre-cache the embedding so check_identity is instant
        face_verifier.cache_embedding(photo_path)

        return jsonify({"status": "success", "message": "Ready for verification."})
    finally:
        release_connection(conn)


# ── API: Check Identity (Web Liveness Loop Phase 1) ───────────────────
@app.route("/api/attendance/check_identity", methods=["POST"])
def check_identity():
    data = request.get_json()
    student_id = data.get("student_id", "").strip()
    image_data = data.get("image", "")

    if not student_id or not image_data:
        return _error("MISSING_FIELDS")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT student_code FROM students WHERE student_code = %s OR id::text = %s", (student_id, student_id))
        student = cur.fetchone()
        if not student:
            return _error("STUDENT_NOT_FOUND")
            
        student_code = dict(student).get("student_code", student_id)
        photo_path = _download_student_photo(student_code)
        if not photo_path:
            return _error("FACE_NO_PHOTO")

        # [DEBUG] Start debug session BEFORE decoding so all steps go in the right folder
        if DEBUG_FACE_PIPELINE:
            global _pose_frame_counter
            _pose_frame_counter = 0  # Reset liveness frame counter for new attempt
            debug_logger.current_subfolder = None  # Identity phase saves to root folder
            debug_logger.start_session(student_code)
            debug_logger.save_registered_photo(photo_path)

        try:
            captured = _decode_base64_image(image_data)
        except Exception as e:
            return _error("FACE_DECODE_ERROR", {"detail": str(e)})

        print(f"[DEBUG] check_identity: student={student_code}, captured_shape={captured.shape}, photo={photo_path}")

        t0 = time.time()
        verification = face_verifier.verifyIdentity(captured, photo_path)
        elapsed = time.time() - t0

        print(f"[DEBUG] verification result: verified={verification.get('verified')}, "
              f"distance={verification.get('distance')}, message={verification.get('message')}, "
              f"faceBox={verification.get('faceBox')} | took {elapsed:.3f}s")
        
        # We need faceBox formatted cleanly for JSON: x, y, w, h
        fb = verification.get("faceBox")
        face_box_list = [int(v) for v in fb] if fb is not None else None

        # [DEBUG] Save frame with face bounding box drawn on it
        if DEBUG_FACE_PIPELINE and face_box_list:
            box_frame = captured.copy()
            x, y, w, h = face_box_list
            cv2.rectangle(box_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            label = f"dist={verification.get('distance', 0):.3f}"
            cv2.putText(box_frame, label, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            debug_logger.save_image("step_10_face_box_overlay", box_frame)

        return jsonify({
            "status": "success",
            "verified": verification.get("verified", False),
            "message": verification.get("message", ""),
            "distance": verification.get("distance", 0.0),
            "faceBox": face_box_list
        })
    finally:
        release_connection(conn)

# Counter for liveness frames (reset in check_identity via start_session)
_pose_frame_counter = 0

# ── API: Check Head Pose (Web Liveness Loop Phase 2) ──────────────────
@app.route("/api/attendance/check_pose", methods=["POST"])
def check_pose():
    global _pose_frame_counter
    data = request.get_json()
    image_data = data.get("image", "")
    face_box = data.get("faceBox", None)
    expected_action = data.get("expected", "")  # e.g. "left", "right", "up"

    if not image_data or not face_box or len(face_box) != 4:
        return jsonify({"status": "error", "message": "Missing image or faceBox"}), 400

    try:
        captured = _decode_base64_image(image_data)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Decode error: {str(e)}"}), 400

    # [DEBUG] Set up subfolder BEFORE calling getHeadPose so landmarks save to the right place
    if DEBUG_FACE_PIPELINE:
        _pose_frame_counter += 1
        subfolder = f"liveness_frame_{_pose_frame_counter:03d}"
        debug_logger.current_subfolder = subfolder
        debug_logger.save_image("raw_frame", captured, subfolder=subfolder)

    pose = face_verifier.getHeadPose(captured, face_box)

    # [DEBUG] Save annotated liveness frame with pose info
    if DEBUG_FACE_PIPELINE:

        # Save annotated frame with face box + pose label
        annotated = captured.copy()
        x, y, w, h = [int(v) for v in face_box]
        detected_pose = pose.get("pose", "unknown")
        yaw_val = pose.get("yaw", 0)
        pitch_val = pose.get("pitch", 0)

        # Draw face bounding box
        color = (0, 255, 0) if detected_pose != "unknown" else (0, 0, 255)
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)

        # Draw pose direction arrow on the frame
        cx, cy = x + w // 2, y + h // 2
        arrow_len = 60
        if detected_pose == "left":
            cv2.arrowedLine(annotated, (cx, cy), (cx - arrow_len, cy), (255, 0, 0), 3)
        elif detected_pose == "right":
            cv2.arrowedLine(annotated, (cx, cy), (cx + arrow_len, cy), (255, 0, 0), 3)
        elif detected_pose == "up":
            cv2.arrowedLine(annotated, (cx, cy), (cx, cy - arrow_len), (255, 0, 0), 3)
        elif detected_pose == "down":
            cv2.arrowedLine(annotated, (cx, cy), (cx, cy + arrow_len), (255, 0, 0), 3)
        else:
            cv2.circle(annotated, (cx, cy), 8, (0, 255, 0), -1)

        # Write pose text on the image
        label = f"Pose: {detected_pose} | Yaw: {yaw_val:.1f} | Pitch: {pitch_val:.1f}"
        cv2.putText(annotated, label, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        if expected_action:
            cv2.putText(annotated, f"Expected: {expected_action}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            match = "MATCH" if detected_pose == expected_action else "NO MATCH"
            match_color = (0, 255, 0) if detected_pose == expected_action else (0, 0, 255)
            cv2.putText(annotated, match, (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, match_color, 2)

        debug_logger.save_image("annotated_pose", annotated, subfolder=subfolder)

        # Save pose data as text
        debug_logger.save_text("pose_result", (
            f"frame: {_pose_frame_counter}\n"
            f"detected_pose: {detected_pose}\n"
            f"expected_action: {expected_action}\n"
            f"yaw: {yaw_val}\n"
            f"pitch: {pitch_val}\n"
            f"debug: {pose.get('debug', '')}\n"
        ), subfolder=subfolder)

    return jsonify({
        "status": "success",
        "pose": pose.get("pose", "unknown"),
        "yaw": pose.get("yaw", 0),
        "pitch": pose.get("pitch", 0),
        "debug": pose.get("debug", "")
    })



# ── API: Verify & Record Attendance (Features 2-7, 10) ────────────────
@app.route("/api/attendance/verify", methods=["POST"])
def verify_attendance():
    data = request.get_json()
    session_code = data.get("session_code", "").strip()
    student_id = data.get("student_id", "").strip()
    image_data = data.get("image", "")
    images_data = data.get("images", [])  # Feature 3: multi-frame
    qr_token = data.get("qr_token", "")  # Feature 2: rotating token
    liveness_passed = data.get("liveness_passed", False)  # Feature 4
    device_fingerprint = data.get("device_fingerprint", "")

    if not session_code or not student_id or (not image_data and not images_data):
        return _error("MISSING_FIELDS")

    # ── 1) Validate session ──────────────────────────────────────────
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Debug: log what we're looking for
        print(f"[VERIFY] Looking for session_code='{session_code}', is_active=1")

        cur.execute(
            "SELECT * FROM attendance_sessions WHERE session_code = %s AND is_active = 1",
            (session_code,)
        )
        session = cur.fetchone()
        if not session:
            # Debug: check if session exists at all (without is_active filter)
            cur.execute(
                "SELECT session_code, is_active, expires_at FROM attendance_sessions WHERE session_code = %s",
                (session_code,)
            )
            debug_row = cur.fetchone()
            if debug_row:
                debug_row = dict(debug_row)
                print(f"[VERIFY] Session EXISTS but is_active={debug_row['is_active']}, "
                      f"expires_at={debug_row['expires_at']}, now={datetime.now()}")
            else:
                print(f"[VERIFY] Session '{session_code}' does NOT exist in DB at all!")
            return _error("SESSION_NOT_FOUND")

        session = dict(session)
        now = datetime.utcnow()
        expires_str = str(session["expires_at"]).replace("+00:00", "")
        print(f"[VERIFY] Session found: is_active={session['is_active']}, "
              f"expires_at={expires_str}, now_utc={now}")
        if now > datetime.fromisoformat(expires_str):
            return _error("SESSION_EXPIRED")

        sid = session["session_id"]

        # ── Feature 6: Rate Limiting ─────────────────────────────────
        allowed, err_resp = _check_rate_limit(student_id, sid, "face_verify")
        if not allowed:
            return err_resp

        # ── Feature 2: Validate QR Token ─────────────────────────────
        if qr_token:
            valid, err_code = _validate_qr_token(sid, qr_token)
            if not valid:
                return _error(err_code)

        # ── 2) Get student info ──────────────────────────────────────
        cur.execute("SELECT id AS db_student_id, name, student_code FROM students WHERE student_code = %s OR id::text = %s", (student_id, student_id))
        student = cur.fetchone()
        if not student:
            return _error("STUDENT_NOT_FOUND")

        student = dict(student)
        db_student_id = student["db_student_id"]
        student_code = student.get("student_code", student_id)

        # ── Feature 5: Duplicate Protection ──────────────────────────
        cur.execute(
            "SELECT id FROM attendance WHERE student_id = %s AND session_id = %s",
            (db_student_id, sid)
        )
        if cur.fetchone():
            return _error("ATTENDANCE_DUPLICATE")

        # ── Feature 7: Device Binding ────────────────────────────────
        allowed, err_resp = _check_device_binding(student_id, sid, request)
        if not allowed:
            return err_resp

        # ── 3) Download photo from Supabase ──────────────────────────
        photo_path = _download_student_photo(student_code)
        if not photo_path:
            return _error("FACE_NO_PHOTO")

        # ── 4) Face Verification ─────────────────────────────────────
        # [DEBUG] Start debug session for this verification attempt
        if DEBUG_FACE_PIPELINE:
            debug_logger.start_session(student_code, session_code=session_code)
            debug_logger.save_registered_photo(photo_path)

        # Feature 3: Multi-frame verification
        if images_data and len(images_data) >= 3:
            result = _verify_multi_frame(images_data, photo_path)
            if result.get("static"):
                return _error("FACE_STATIC_IMAGE")
            if not result["verified"]:
                return _error("FACE_LOW_CONFIDENCE", {
                    "avg_confidence": result.get("avg_confidence", 0),
                    "frames_checked": result.get("frames_checked", 0),
                })
            distance = result.get("avg_distance", 0)
            verified = True
        else:
            # Single-frame fallback
            try:
                captured = _decode_base64_image(image_data)
            except Exception as e:
                return _error("FACE_DECODE_ERROR", {"detail": str(e)})

            try:
                verification = face_verifier.verifyIdentity(captured, photo_path)
                distance = round(verification["distance"], 4)
                verified = verification["verified"]
                if not verified:
                    return _error("FACE_VERIFY_FAILED", {"distance": distance})
            except Exception as e:
                return _error("FACE_VERIFY_ERROR", {"detail": str(e)})

        # ── 5) Record attendance ─────────────────────────────────────
        today = now.strftime("%Y-%m-%d")
        notes = "Verified via Face+QR"
        if liveness_passed:
            notes += " +Liveness"

        cur.execute("""
            INSERT INTO attendance (student_id, course_id, session_id, date, status, verified_by, notes)
            VALUES (%s, %s, %s, %s, 'Present', 'face', %s)
        """, (db_student_id, session["course_id"], sid, today, notes))
        conn.commit()

        return jsonify({
            "status": "success",
            "code": "ATTENDANCE_RECORDED",
            "verified": True,
            "distance": distance,
            "student_name": student["name"],
            "message": f"{student['name']} — Attendance recorded!",
        })
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "code": "SERVER_ERROR", "message": str(e)}), 500
    finally:
        release_connection(conn)


# ── API: Session Report ───────────────────────────────────────────────
@app.route("/api/session/<code>/report", methods=["GET"])
def session_report(code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM attendance_sessions WHERE session_code = %s", (code,))
        session = cur.fetchone()
        if not session:
            return _error("SESSION_NOT_FOUND")

        session = dict(session)
        cur.execute("""
            SELECT a.id AS attendance_id, a.student_id, s.student_code, s.name AS student_name,
                   a.date, a.status, a.verified_by, a.notes, a.created_at
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.session_id = %s
            ORDER BY a.created_at
        """, (session["session_id"],))

        records = [dict(r) for r in cur.fetchall()]
        # Make timestamps serializable
        for r in records:
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])
            if r.get("date"):
                r["date"] = str(r["date"])

        return jsonify({
            "status": "success",
            "session_code": code,
            "total_present": len(records),
            "attendance": records,
            "records": records,
        })
    finally:
        release_connection(conn)


# ── API: Close Session ────────────────────────────────────────────────
@app.route("/api/session/<code>/close", methods=["POST"])
def close_session(code):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE attendance_sessions SET is_active = 0 WHERE session_code = %s AND is_active = 1",
            (code,)
        )
        affected = cur.rowcount
        conn.commit()

        if affected == 0:
            return _error("SESSION_NOT_FOUND")

        return jsonify({"status": "success", "code": "SESSION_CLOSED", "message": "Session closed."})
    finally:
        release_connection(conn)


# ── Main ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import ssl
    from mainAgent.web.generate_cert import generate_self_signed_cert

    cert_dir = os.path.dirname(__file__)
    cert_path, key_path = generate_self_signed_cert(cert_dir)

    print(f"\n Face + QR Attendance Server (HTTPS)")
    print("=" * 55)
    print(f"  Local:      https://localhost:5000/")
    print(f"  Network:    https://{LAN_IP}:5000/")
    print("=" * 55)

    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(cert_path, key_path)
    app.run(host="0.0.0.0", port=5000, debug=True, ssl_context=ssl_ctx, use_reloader=False)
